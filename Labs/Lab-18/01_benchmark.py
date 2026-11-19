"""Read-only Lab 18 benchmark for the isolated Lab16 dataset."""
from __future__ import annotations

import os
import statistics
import time
from pathlib import Path
from cassandra.cluster import Cluster
from neo4j import GraphDatabase
from pymongo import MongoClient

REQUIRED = int(os.getenv("LAB18_REQUIRED_RECORDS", "300000"))
RUNS = int(os.getenv("LAB18_RUNS", "10"))
LIMIT = 100
MONGO_URI = os.getenv("LAB16_MONGO_URI") or os.getenv("MONGO_URI")
MONGO_HOST = os.getenv("MONGO_HOST", "host.docker.internal")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27118"))
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "host.docker.internal")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://host.docker.internal:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "change-this-local")

mongo = MongoClient(
    MONGO_URI or f"mongodb://{MONGO_HOST}:{MONGO_PORT}/?directConnection=true",
    serverSelectionTimeoutMS=15000,
)
mongo.admin.command("ping")
collection = mongo["cti_hybrid"]["lab16_threats"]
mongo_count = collection.count_documents({"dataset": "lab16"})
if mongo_count < REQUIRED:
    raise RuntimeError(f"Lab18 requires {REQUIRED:,} Lab16 MongoDB records; found {mongo_count:,}")

cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
cass = cluster.connect("cti")
cass_sample = cass.execute("SELECT id, platform, status, severity, ioc FROM lab16_threat_by_id LIMIT 1").one()
if cass_sample is None:
    raise RuntimeError("Lab16 Cassandra table is empty")
# Full COUNT(*) is intentionally not used as a preflight on Cassandra: it can
# trigger a costly full-table scan. Verify the deterministic first/last IDs.
first = cass.execute("SELECT id FROM lab16_threat_by_id WHERE id=%s", ("lab16-000000001",)).one()
last = cass.execute("SELECT id FROM lab16_threat_by_id WHERE id=%s", (f"lab16-{REQUIRED:09d}",)).one()
if first is None or last is None:
    raise RuntimeError("Lab18 Cassandra boundary-record verification failed")

neo = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
neo.verify_connectivity()
with neo.session() as s:
    neo_count = s.run("MATCH (t:Lab16Threat) RETURN count(t) AS n").single()["n"]
    neo_first = s.run("MATCH (t:Lab16Threat {id:'lab16-000000001'}) RETURN count(t) AS n").single()["n"]
    neo_last = s.run("MATCH (t:Lab16Threat {id:$id}) RETURN count(t) AS n", id=f"lab16-{REQUIRED:09d}").single()["n"]
if neo_count < REQUIRED or not neo_first or not neo_last:
    raise RuntimeError(f"Lab18 Neo4j validation failed: count={neo_count:,}")

sample = collection.find_one({"_id": "lab16-000000001"})
if not sample:
    raise RuntimeError("Lab18 MongoDB sample record is missing")
sample_id, sample_ioc, sample_platform = sample["_id"], sample["ioc"], sample["platform"]

def median_ms(fn):
    values = []
    for _ in range(RUNS):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000)
    return statistics.median(values)

def q1_mongo():
    collection.find_one({"_id": sample_id})
def q1_cassandra():
    cass.execute("SELECT * FROM lab16_threat_by_id WHERE id=%s", (sample_id,)).one()
def q2_mongo():
    list(collection.find({"platform": "Windows", "status": "Active"}).limit(LIMIT))
def q2_cassandra():
    list(cass.execute(
        "SELECT * FROM lab16_threats_by_platform WHERE platform=%s AND status=%s LIMIT 100",
        ("Windows", "Active"),
    ))
def q3_mongo():
    list(collection.find({"ioc": sample_ioc}).limit(LIMIT))
def q3_neo4j():
    with neo.session() as s:
        list(s.run(
            "MATCH (t:Lab16Threat {id:$id})-[:LAB16_HAS_IOC]->(i:Lab16IOC)"
            "<-[:LAB16_HAS_IOC]-(other:Lab16Threat) RETURN other.id LIMIT 100",
            id=sample_id,
        ))
def q4_mongo():
    list(collection.find({"platform": sample_platform}).limit(LIMIT))
def q4_neo4j():
    with neo.session() as s:
        list(s.run(
            "MATCH (p:Lab16Platform {name:$platform})"
            "<-[:LAB16_TARGETS]-(t:Lab16Threat) RETURN t.id LIMIT 100",
            platform=sample_platform,
        ))

results = {
    "q1_mongo": median_ms(q1_mongo), "q1_cassandra": median_ms(q1_cassandra),
    "q2_mongo": median_ms(q2_mongo), "q2_cassandra": median_ms(q2_cassandra),
    "q3_mongo": median_ms(q3_mongo), "q3_neo4j": median_ms(q3_neo4j),
    "q4_mongo": median_ms(q4_mongo), "q4_neo4j": median_ms(q4_neo4j),
}
report = "\n".join([
    "# Lab 18: Cross-Database Benchmark",
    "",
    f"Lab16 target: {REQUIRED:,} records | MongoDB={mongo_count:,} | Neo4j={neo_count:,}",
    "Cassandra validation: deterministic first and last Lab16 IDs found; full COUNT(*) omitted to avoid a full-table scan.",
    f"Method: median of {RUNS} runs; result cap {LIMIT} where applicable.",
    "",
    "| Query pattern | MongoDB | Cassandra | Neo4j |",
    "|---|---:|---:|---:|",
    f"| Q1: Threat lookup by ID | {results['q1_mongo']:.2f} ms | {results['q1_cassandra']:.2f} ms | N/A |",
    f"| Q2: Platform and status | {results['q2_mongo']:.2f} ms | {results['q2_cassandra']:.2f} ms | N/A |",
    f"| Q3: Shared IOC neighbors | {results['q3_mongo']:.2f} ms | N/A | {results['q3_neo4j']:.2f} ms |",
    f"| Q4: Threats by platform | {results['q4_mongo']:.2f} ms | N/A | {results['q4_neo4j']:.2f} ms |",
    "",
    "## Isolation and safety",
    "- MongoDB collection: cti_hybrid.lab16_threats",
    "- Cassandra tables: cti.lab16_threat_by_id and cti.lab16_threats_by_platform",
    "- Neo4j labels: Lab16Threat, Lab16Platform, Lab16IOC",
    "- This benchmark is read-only.",
    "",
    "## Limitations",
    "Local benchmark medians are workload-specific and are not production capacity claims.",
])
out = Path(os.getenv("LAB18_REPORT_PATH", "/reports/benchmark_report.md"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(report + "\n", encoding="utf-8")
print(report, flush=True)
print(f"[Lab18] Report saved: {out}", flush=True)

neo.close()
cluster.shutdown()
mongo.close()
