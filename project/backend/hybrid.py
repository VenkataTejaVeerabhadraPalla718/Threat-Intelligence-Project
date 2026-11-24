import os

from cassandra.cluster import Cluster
from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import GraphDatabase

from common import client
from rag import normalize_platform, normalize_status
from saas import current_user

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])


@router.get("/hybrid/search")
def hybrid_search(
    platform: str,
    status: str,
    limit: int = Query(10, ge=1, le=100),
):
    try:
        canonical_platform = normalize_platform(platform)
        canonical_status = normalize_status(status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    mongo_rows = list(
        client["cti_hybrid"]
        .threats.find(
            {"platform": canonical_platform, "status": canonical_status},
            {"platform": 1, "status": 1, "severity": 1, "ioc": 1},
        )
        .limit(limit)
    )
    mongo_ids = [str(row["_id"]) for row in mongo_rows]
    mongo_results = [
        {
            "id": str(row["_id"]),
            "platform": row["platform"],
            "status": row["status"],
            "severity": row["severity"],
            "ioc": row["ioc"],
        }
        for row in mongo_rows
    ]

    cassandra_cluster = Cluster(
        [os.getenv("CASSANDRA_HOST", "127.0.0.1")],
        port=int(os.getenv("CASSANDRA_PORT", "9042")),
    )
    cassandra_session = None
    try:
        cassandra_session = cassandra_cluster.connect("cti")
        cassandra_rows = cassandra_session.execute(
            "SELECT id, platform, status, severity FROM threats_by_platform "
            "WHERE platform=%s AND status=%s LIMIT %s",
            (canonical_platform, canonical_status, limit),
        )
        cassandra_results = [
            {
                "id": row.id,
                "platform": row.platform,
                "status": row.status,
                "severity": row.severity,
            }
            for row in cassandra_rows
        ]
    finally:
        if cassandra_session is not None:
            cassandra_session.shutdown()
        cassandra_cluster.shutdown()

    neo4j_driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )
    try:
        with neo4j_driver.session() as graph_session:
            graph_rows = graph_session.run(
                """
                MATCH (t:Threat)-[:TARGETS]->(:Platform {name: $platform})
                WHERE t.id IN $ids
                OPTIONAL MATCH (t)-[:HAS_IOC]->(i:IOC)
                RETURN t.id AS id, i.value AS ioc
                LIMIT $limit
                """,
                platform=canonical_platform,
                ids=mongo_ids,
                limit=limit,
            )
            neo4j_results = [
                {"id": row["id"], "ioc": row["ioc"]} for row in graph_rows
            ]
    finally:
        neo4j_driver.close()

    return {
        "platform": canonical_platform,
        "status": canonical_status,
        "mongo": mongo_results,
        "cassandra": cassandra_results,
        "neo4j": neo4j_results,
    }
