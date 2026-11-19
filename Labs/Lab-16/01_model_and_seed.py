"""Safe, repeatable Lab 16 polyglot seed.

Writes only to:
- MongoDB: cti_hybrid.lab16_threats
- Cassandra: cti.lab16_threat_by_id and cti.lab16_threats_by_platform
- Neo4j: Lab16Threat / Lab16Platform / Lab16IOC labels and Lab16_* relationships

It deliberately does NOT drop collections, truncate tables, or delete graph nodes.
"""
from __future__ import annotations

import os
import random
import time
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.concurrent import execute_concurrent_with_args
from neo4j import GraphDatabase
from pymongo import MongoClient, ASCENDING

TARGET = int(os.getenv("LAB16_TARGET_RECORDS", "300000"))
BATCH = int(os.getenv("LAB16_BATCH_SIZE", "1000"))
MONGO_URI = os.getenv("LAB16_MONGO_URI") or os.getenv("MONGO_URI")
MONGO_HOST = os.getenv("MONGO_HOST", "host.docker.internal")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27118"))
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "host.docker.internal")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://host.docker.internal:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "change-this-local")

if TARGET < 1 or BATCH < 1:
    raise ValueError("LAB16_TARGET_RECORDS and LAB16_BATCH_SIZE must be positive")

print(f"[Lab16] Target={TARGET:,}; batch={BATCH:,}", flush=True)

# The current rs0 primary is mongo2:27118. directConnection prevents the
# driver from following Docker-only replica-set hostnames that pods cannot resolve.
mongo = MongoClient(
    MONGO_URI or f"mongodb://{MONGO_HOST}:{MONGO_PORT}/?directConnection=true",
    serverSelectionTimeoutMS=15000,
)
mongo.admin.command("ping")
collection = mongo["cti_hybrid"]["lab16_threats"]

print("[Lab16] Connecting to Cassandra...", flush=True)
cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
session = None
for attempt in range(20):
    try:
        session = cluster.connect()
        break
    except NoHostAvailable:
        if attempt == 19:
            raise
        time.sleep(5)
session.execute(
    "CREATE KEYSPACE IF NOT EXISTS cti "
    "WITH replication = {'class':'SimpleStrategy','replication_factor':1}"
)
session.set_keyspace("cti")
session.execute("""
CREATE TABLE IF NOT EXISTS lab16_threat_by_id (
    id text PRIMARY KEY, platform text, status text, severity int, ioc text
)
""")
session.execute("""
CREATE TABLE IF NOT EXISTS lab16_threats_by_platform (
    platform text, status text, id text, severity int, ioc text,
    PRIMARY KEY ((platform, status), id)
)
""")
by_id = session.prepare(
    "INSERT INTO lab16_threat_by_id (id, platform, status, severity, ioc) VALUES (?, ?, ?, ?, ?)"
)
by_platform = session.prepare(
    "INSERT INTO lab16_threats_by_platform (platform, status, id, severity, ioc) VALUES (?, ?, ?, ?, ?)"
)

print("[Lab16] Connecting to Neo4j...", flush=True)
neo = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
neo.verify_connectivity()
with neo.session() as s:
    s.run("CREATE CONSTRAINT lab16_threat_id IF NOT EXISTS FOR (n:Lab16Threat) REQUIRE n.id IS UNIQUE").consume()
    s.run("CREATE CONSTRAINT lab16_platform_name IF NOT EXISTS FOR (n:Lab16Platform) REQUIRE n.name IS UNIQUE").consume()
    s.run("CREATE CONSTRAINT lab16_ioc_value IF NOT EXISTS FOR (n:Lab16IOC) REQUIRE n.value IS UNIQUE").consume()

platforms = ["Windows", "Linux", "MacOS", "Android", "iOS"]
statuses = ["Anticipated", "Active", "Evolving", "Resolved"]
rng = random.Random(160018)
inserted = 0

def write_graph(tx, rows):
    tx.run("""
    UNWIND $rows AS row
    MERGE (t:Lab16Threat {id: row.id})
      SET t.platform = row.platform, t.status = row.status,
          t.severity = row.severity, t.ioc = row.ioc
    MERGE (p:Lab16Platform {name: row.platform})
    MERGE (i:Lab16IOC {value: row.ioc})
    MERGE (t)-[:LAB16_TARGETS]->(p)
    MERGE (t)-[:LAB16_HAS_IOC]->(i)
    """, rows=rows).consume()

with neo.session() as graph:
    for start in range(0, TARGET, BATCH):
        mongo_docs, cass_id_rows, cass_platform_rows, graph_rows = [], [], [], []
        stop = min(start + BATCH, TARGET)
        for index in range(start, stop):
            # Stable IDs make retries idempotent and avoid duplicating records.
            threat_id = f"lab16-{index + 1:09d}"
            platform = platforms[index % len(platforms)]
            status = statuses[(index // len(platforms)) % len(statuses)]
            severity = (index % 10) + 1
            ioc = f"192.168.{(index // 250) % 256}.{(index % 250) + 1}"
            doc = {
                "_id": threat_id, "dataset": "lab16", "platform": platform,
                "status": status, "severity": severity, "ioc": ioc,
            }
            mongo_docs.append(doc)
            cass_id_rows.append((threat_id, platform, status, severity, ioc))
            cass_platform_rows.append((platform, status, threat_id, severity, ioc))
            graph_rows.append({
                "id": threat_id, "platform": platform, "status": status,
                "severity": severity, "ioc": ioc,
            })

        # Replace only matching Lab16 IDs; unrelated MongoDB documents are untouched.
        collection.bulk_write(
            [
                __import__("pymongo").ReplaceOne({"_id": d["_id"]}, d, upsert=True)
                for d in mongo_docs
            ],
            ordered=False,
        )
        execute_concurrent_with_args(session, by_id, cass_id_rows, concurrency=64, raise_on_first_error=True)
        execute_concurrent_with_args(session, by_platform, cass_platform_rows, concurrency=64, raise_on_first_error=True)
        graph.execute_write(write_graph, graph_rows)
        inserted = stop
        if inserted % 10000 == 0 or inserted == TARGET:
            print(f"[Lab16] Upserted {inserted:,}/{TARGET:,}", flush=True)

collection.create_index([("platform", ASCENDING), ("status", ASCENDING)])
collection.create_index([("ioc", ASCENDING)])
with neo.session() as s:
    neo_count = s.run("MATCH (t:Lab16Threat) RETURN count(t) AS n").single()["n"]
mongo_count = collection.count_documents({"dataset": "lab16"})
print(
    f"[Lab16] COMPLETE | MongoDB={mongo_count:,} | "
    f"Neo4j={neo_count:,} | Cassandra upserts={inserted:,}",
    flush=True,
)
if mongo_count < TARGET or neo_count < TARGET:
    raise RuntimeError("Lab16 verification failed: one or more stores are below target")

neo.close()
cluster.shutdown()
mongo.close()
