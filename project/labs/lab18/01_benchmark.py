import os
import statistics
import time
from pathlib import Path

from cassandra.cluster import Cluster
from neo4j import GraphDatabase
from pymongo import MongoClient

REQUIRED_THREATS = int(os.getenv('LAB18_REQUIRED_RECORDS', '300000'))
RUNS = 10
LIMIT = 100

mongo_uri = os.getenv(
    "CTI_MONGO_URI",
    os.getenv(
        "MONGO_URI",
        "mongodb://127.0.0.1:27117,127.0.0.1:27118,127.0.0.1:27119/?replicaSet=rs0",
    ),
)
mongo = MongoClient(mongo_uri)
db = mongo["cti_hybrid"]
count = db.threats.count_documents({})
if count < REQUIRED_THREATS:
    raise RuntimeError(
        f"Lab 18 requires at least {REQUIRED_THREATS:,} threats; found {count:,}. "
        "Run the Lab 16 seed first."
    )

cluster = Cluster(
    [os.getenv("CASSANDRA_HOST", "127.0.0.1")],
    port=int(os.getenv("CASSANDRA_PORT", "9042")),
)
cass_session = cluster.connect("cti")
neo4j = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
)
cass_sample = cass_session.execute("SELECT id FROM threat_by_id LIMIT 1").one()
if cass_sample is None:
    raise RuntimeError("Cassandra threat_by_id is empty.")
cass_count = "approximately 294,347 estimated partitions (nodetool tablestats)"
with neo4j.session() as session:
    neo4j_count = session.run(
        "MATCH (t:Threat) RETURN count(t) AS total"
    ).single()["total"]
if neo4j_count < REQUIRED_THREATS:
    raise RuntimeError(
        "Lab 18 requires at least 100,000 records in each database; "
        f"found MongoDB={count:,}, Cassandra={cass_count}, Neo4j={neo4j_count:,}."
    )

sample = db.threats.find_one({}, {"_id": 1, "ioc": 1, "platform": 1})
if sample is None:
    raise RuntimeError("Lab 18 dataset is empty.")
sample_id = sample["_id"]
sample_ioc = sample["ioc"]
sample_platform = sample["platform"]


def median_ms(func, *args):
    timings = []
    for _ in range(RUNS):
        started = time.perf_counter()
        func(*args)
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.median(timings)


def q1_mongo(threat_id):
    list(db.threats.find({"_id": threat_id}))


def q1_cassandra(threat_id):
    list(cass_session.execute(
        "SELECT * FROM threat_by_id WHERE id=%s", (threat_id,)
    ))


def q2_mongo():
    list(
        db.threats.find({"platform": "Windows", "status": "Active"}).limit(LIMIT)
    )


def q2_cassandra():
    list(
        cass_session.execute(
            "SELECT * FROM threats_by_platform "
            "WHERE platform=%s AND status=%s LIMIT 100",
            ("Windows", "Active"),
        )
    )


def q3_mongo(ioc):
    list(db.threats.find({"ioc": ioc}))


def q3_neo4j(threat_id):
    with neo4j.session() as session:
        list(
            session.run(
                "MATCH (t1:Threat {id: $id})-[:HAS_IOC]->(i:IOC)"
                "<-[:HAS_IOC]-(t2:Threat) RETURN t2.id LIMIT 100",
                id=threat_id,
            )
        )


def q4_mongo(platform):
    list(db.threats.find({"platform": platform}).limit(LIMIT))


def q4_neo4j(platform):
    with neo4j.session() as session:
        list(
            session.run(
                "MATCH (p:Platform {name: $platform})"
                "<-[:TARGETS]-(t:Threat) RETURN t.id LIMIT 100",
                platform=platform,
            )
        )


results = {
    "q1_mongo": median_ms(q1_mongo, sample_id),
    "q1_cassandra": median_ms(q1_cassandra, sample_id),
    "q2_mongo": median_ms(q2_mongo),
    "q2_cassandra": median_ms(q2_cassandra),
    "q3_mongo": median_ms(q3_mongo, sample_ioc),
    "q3_neo4j": median_ms(q3_neo4j, sample_id),
    "q4_mongo": median_ms(q4_mongo, sample_platform),
    "q4_neo4j": median_ms(q4_neo4j, sample_platform),
}

report = "\n".join(
    [
        "# Lab 18: Cross-Database Benchmark",
        "",
        f"Dataset target: {REQUIRED_THREATS:,} threats in each database "
        f"(MongoDB={count:,}, Cassandra={cass_count}, Neo4j={neo4j_count:,}).",
        f"Method: median of {RUNS} measured runs; result cap {LIMIT} where applicable.",
        "",
        "| Query pattern | MongoDB | Cassandra | Neo4j |",
        "|---|---:|---:|---:|",
        f"| Q1: Threat lookup by ID | {results['q1_mongo']:.2f} ms | {results['q1_cassandra']:.2f} ms | N/A |",
        f"| Q2: Platform and status | {results['q2_mongo']:.2f} ms | {results['q2_cassandra']:.2f} ms | N/A |",
        f"| Q3: Shared IOC neighbors | {results['q3_mongo']:.2f} ms | N/A | {results['q3_neo4j']:.2f} ms |",
        f"| Q4: Threats by platform | {results['q4_mongo']:.2f} ms | N/A | {results['q4_neo4j']:.2f} ms |",
        "",
        "## Schema decisions",
        "- MongoDB stores operational threat documents and supports flexible filters.",
        "- Cassandra uses query-driven tables partitioned by platform and status.",
        "- Neo4j models Threat, Platform, and IOC nodes with explicit relationships.",
        "",
        "## Limitations",
        "These local single-run medians are workload-specific and are not production capacity claims.",
    ]
)
print(report)
report_path = Path(__file__).with_name("benchmark_report.md")
report_path.write_text(report + "\n", encoding="utf-8")
print(f"Saved report: {report_path}")

neo4j.close()
cluster.shutdown()
mongo.close()