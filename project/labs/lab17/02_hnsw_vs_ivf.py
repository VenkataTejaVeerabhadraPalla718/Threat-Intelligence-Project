import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from neo4j import GraphDatabase
from pymongo import MongoClient, ReplaceOne

COUNT = int(os.getenv('LAB17_TARGET_RECORDS', '300000'))
DIM = 384
TOP_K = 10
QUERY_COUNT = 100
WARMUP_COUNT = 10
MONGO_COLLECTION = "vectors_cross_engine"
MONGO_INDEX = "lab17_hnsw"
NEO4J_INDEX = "lab17_2_vector"
BATCH_SIZE = 500

mongo_uri = os.getenv(
    "VECTOR_MONGO_URI",
    "mongodb://admin:pass123@localhost:27777/?authSource=admin&directConnection=true",
)
neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
neo4j_auth = (
    os.getenv("NEO4J_USER", "neo4j"),
    os.getenv("NEO4J_PASSWORD", "password"),
)


def ensure_mongo_index(collection):
    indexes = list(
        collection.aggregate([{"$listSearchIndexes": {"name": MONGO_INDEX}}])
    )
    if not indexes:
        collection.database.command(
            {
                "createSearchIndexes": collection.name,
                "indexes": [
                    {
                        "name": MONGO_INDEX,
                        "type": "vectorSearch",
                        "definition": {
                            "fields": [
                                {
                                    "type": "vector",
                                    "path": "embedding",
                                    "numDimensions": DIM,
                                    "similarity": "cosine",
                                    "hnswOptions": {
                                        "maxEdges": 16,
                                        "numEdgeCandidates": 100,
                                    },
                                }
                            ]
                        },
                    }
                ],
            }
        )

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        indexes = list(
            collection.aggregate([{"$listSearchIndexes": {"name": MONGO_INDEX}}])
        )
        index = next(
            (item for item in indexes if item.get("name") == MONGO_INDEX), None
        )
        if index and index.get("status") == "READY" and index.get("queryable"):
            return
        if index and index.get("status") == "FAILED":
            raise RuntimeError(f"MongoDB HNSW index build failed: {index}")
        time.sleep(2)
    raise TimeoutError("MongoDB HNSW index did not become queryable within 180 seconds.")


def seed_mongo(collection, vectors):
    collection.bulk_write(
        [
            ReplaceOne(
                {"_id": vector_id},
                {"_id": vector_id, "embedding": vector.tolist()},
                upsert=True,
            )
            for vector_id, vector in enumerate(vectors)
        ],
        ordered=False,
    )
    count = collection.count_documents({})
    if count != COUNT:
        raise RuntimeError(f"Expected {COUNT:,} MongoDB vectors; found {count:,}.")


def seed_neo4j(session, vectors):
    for start in range(0, COUNT, BATCH_SIZE):
        rows = [
            {"id": vector_id, "embedding": vector.tolist()}
            for vector_id, vector in enumerate(
                vectors[start : start + BATCH_SIZE], start=start
            )
        ]
        session.run(
            "UNWIND $rows AS row "
            "MERGE (v:Lab17Vector {id: row.id}) "
            "SET v.embedding = row.embedding",
            rows=rows,
        ).consume()

    count = session.run(
        "MATCH (v:Lab17Vector) RETURN count(v) AS count"
    ).single()["count"]
    if count != COUNT:
        raise RuntimeError(f"Expected {COUNT:,} Neo4j vectors; found {count:,}.")


def ensure_neo4j_index(session):
    session.run(
        f"CREATE VECTOR INDEX {NEO4J_INDEX} IF NOT EXISTS "
        "FOR (v:Lab17Vector) ON (v.embedding) "
        "OPTIONS {indexConfig: {"
        f"`vector.dimensions`: {DIM}, "
        "`vector.similarity_function`: 'cosine'}}"
    ).consume()

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        index = session.run(
            "SHOW VECTOR INDEXES YIELD name, state, populationPercent "
            "WHERE name = $name RETURN state, populationPercent",
            name=NEO4J_INDEX,
        ).single()
        if index and index["state"] == "ONLINE" and index["populationPercent"] == 100.0:
            return
        time.sleep(1)
    raise TimeoutError("Neo4j vector index did not become ONLINE within 180 seconds.")


def mongo_search(collection, query):
    return [
        row["_id"]
        for row in collection.aggregate(
            [
                {
                    "$vectorSearch": {
                        "index": MONGO_INDEX,
                        "path": "embedding",
                        "queryVector": query.tolist(),
                        "numCandidates": 100,
                        "limit": TOP_K,
                    }
                },
                {"$project": {"_id": 1}},
            ]
        )
    ]


def neo4j_search(session, query):
    return [
        row["id"]
        for row in session.run(
            "CALL db.index.vector.queryNodes($index, $limit, $vector) "
            "YIELD node, score RETURN node.id AS id",
            index=NEO4J_INDEX,
            limit=TOP_K,
            vector=query.tolist(),
        )
    ]


def recall_at_k(result_ids, exact_ids):
    return len(set(result_ids) & exact_ids) / TOP_K


def measure_searches(mongo_collection, neo4j_session, queries, vectors):
    mongo_times = []
    neo4j_times = []
    mongo_recalls = []
    neo4j_recalls = []

    for query_number, query in enumerate(queries):
        exact_ids = set(
            np.argpartition(vectors @ query, -TOP_K)[-TOP_K:].tolist()
        )
        searches = (
            (mongo_search, mongo_collection, mongo_times, mongo_recalls),
            (neo4j_search, neo4j_session, neo4j_times, neo4j_recalls),
        )
        if query_number % 2:
            searches = tuple(reversed(searches))

        for search, target, times, recalls in searches:
            started = time.perf_counter()
            result_ids = search(target, query)
            times.append((time.perf_counter() - started) * 1000)
            if len(result_ids) != TOP_K:
                raise RuntimeError(
                    f"{search.__name__} returned {len(result_ids)} results, "
                    f"expected {TOP_K}."
                )
            recalls.append(recall_at_k(result_ids, exact_ids))

    return mongo_times, neo4j_times, mongo_recalls, neo4j_recalls


def main():
    rng = np.random.default_rng(42)
    vectors = rng.normal(size=(COUNT, DIM)).astype(np.float32)
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
    query_ids = rng.choice(COUNT, size=QUERY_COUNT, replace=False)
    queries = vectors[query_ids] + rng.normal(
        scale=0.05, size=(QUERY_COUNT, DIM)
    ).astype(np.float32)
    queries /= np.maximum(np.linalg.norm(queries, axis=1, keepdims=True), 1e-12)

    mongo = MongoClient(mongo_uri, serverSelectionTimeoutMS=10_000)
    neo4j = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
    try:
        mongo.admin.command("ping")
        neo4j.verify_connectivity()
        collection = mongo["cti_lab17"][MONGO_COLLECTION]
        seed_mongo(collection, vectors)

        with neo4j.session() as session:
            seed_neo4j(session, vectors)
            ensure_neo4j_index(session)

            print(
                f"Loaded the same {COUNT:,} normalized {DIM}-dimensional vectors "
                "into MongoDB and Neo4j."
            )
            ensure_mongo_index(collection)

            for query in queries[:WARMUP_COUNT]:
                mongo_search(collection, query)
                neo4j_search(session, query)

            print(
                f"Running {QUERY_COUNT} measured queries per engine "
                f"after {WARMUP_COUNT} warmups..."
            )
            mongo_times, neo4j_times, mongo_recalls, neo4j_recalls = (
                measure_searches(collection, session, queries, vectors)
            )

            neo4j_version = session.run(
                "CALL dbms.components() YIELD versions "
                "RETURN versions[0] AS version"
            ).single()["version"]

        mongo_version = mongo.server_info()["version"]
        report = "\n".join(
            [
                "# Lab 17.2: Cross-Engine HNSW Vector Search",
                "",
                f"Run time (UTC): {datetime.now(timezone.utc).isoformat()}",
                f"Dataset: {COUNT:,} identical normalized vectors | dimensions: {DIM}",
                f"Queries: {QUERY_COUNT} measured per engine, plus {WARMUP_COUNT} warmups",
                f"Top K: {TOP_K} | metric: cosine similarity",
                f"MongoDB version: {mongo_version}",
                f"Neo4j version: {neo4j_version}",
                "",
                "| Engine | Index | Median latency | P95 latency | Mean recall@10 |",
                "|---|---|---:|---:|---:|",
                f"| MongoDB Atlas Local | HNSW (maxEdges=16; numCandidates=100) | "
                f"{statistics.median(mongo_times):.2f} ms | "
                f"{np.percentile(mongo_times, 95):.2f} ms | "
                f"{statistics.mean(mongo_recalls) * 100:.1f}% |",
                f"| Neo4j | HNSW (native vector index defaults) | "
                f"{statistics.median(neo4j_times):.2f} ms | "
                f"{np.percentile(neo4j_times, 95):.2f} ms | "
                f"{statistics.mean(neo4j_recalls) * 100:.1f}% |",
                "",
                "Method: both engines received the same deterministic vector dataset and "
                "query vectors. Exact cosine top-10 from NumPy is used only as the recall "
                "reference, not as a competing search engine. Query latency includes the "
                "client round trip and result transfer; both engines were warmed and query "
                "order was alternated. Engine-specific HNSW implementations and defaults "
                "differ, so timings describe this host and configuration rather than a "
                "hardware-independent ranking.",
                "",
                "The script upserts records in dedicated Lab 17.2 collections/labels and "
                "does not drop collections, delete graph nodes, or reset database volumes.",
            ]
        )
        print("\n" + report)
        report_path = Path(__file__).with_name("vector_benchmark_report.md")
        report_path.write_text(report + "\n", encoding="utf-8")
        print(f"Saved report: {report_path}")
    finally:
        mongo.close()
        neo4j.close()


if __name__ == "__main__":
    main()
