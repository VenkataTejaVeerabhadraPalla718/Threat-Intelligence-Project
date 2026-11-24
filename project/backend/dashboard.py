import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, HTTPException

import config
from common import db
from monitor import snapshot
from lab_jobs import start_job, get_job, latest_job
from saas import current_user, require_admin, require_lab_run, require_lab_view, can_view_lab

ROOT = Path(__file__).resolve().parent.parent
router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(current_user)])

# Data-resetting experiments require confirmation before they run.
EXPERIMENTS = {
    "l1-all": ("1", "Database classification and application mapping (4 activities)", "labs/lab01/run_all.py", []),
    "l2-all": ("2", "MongoDB environment and CRUD operations (4 activities)", "labs/lab02/run_all.py", []),
    "l3-all": ("3", "Embedded schema and blog migration (4 activities)", "labs/lab03/run_all.py", []),
    "l4-all": ("4", "Product queries and bulk upserts (4 activities)", "labs/lab04/run_all.py", []),
    "l5-aggregation": ("5.1", "Sales analytics aggregation pipeline", "labs/lab05/Activity_5.1/activity_5_1.py", []),
    "l5-bucket": ("5.1", "Try it yourself: order-value $bucket categories", "labs/lab05/Activity_5.1_Try_Yourself/activity_5_1_bucket.py", []),
    "l5-lookup": ("5.2", "$lookup joins and products never ordered", "labs/lab05/Activity_5.2/activity_5_2.py", []),
    "l5-lookup-pipeline": ("5.2", "Try it yourself: filtered $lookup pipeline", "labs/lab05/Activity_5.2_Try_Yourself/activity_5_2_lookup_pipeline.py", []),
    "l6-index-design": ("6.1", "50,000 products: explain before and after indexes", "labs/lab06/Activity_6.1/activity_6_1.py", []),
    "l6-index-stats": ("6.1", "Try it yourself: measure $indexStats usage", "labs/lab06/Activity_6.1_Try_Yourself/activity_6_1_index_stats.py", []),
    "l6-write-benchmark": ("6.2", "Compare insert throughput with five indexes", "labs/lab06/Activity_6.2/activity_6_2.py", []),
    "l6-covered-query": ("6.2", "Try it yourself: verify a covered query", "labs/lab06/Activity_6.2_Try_Yourself/activity_6_2_covered_query.py", []),
    "l7-analyze": ("7.1", "Embed vs reference, $bsonSize", "labs/lab07/02_lab71_analyze.py", []),
    "l7-reads": ("7.2", "Working set and random reads", "labs/lab07/04_lab72_reads.py", []),
    "l8-repl": ("8.1", "Replication check on 3 nodes", "labs/lab08/01_replication_check.py", []),
    "l8-priority": ("8.2", "Replica priority demonstration", "labs/lab08/03_priority_demo.py", []),
    "l9-wc": ("9.1", "Write concern latency", "labs/lab09/01_write_concern.py", []),
    "l10-transfer": ("10.1", "Bank transfer and rollback", "labs/lab10/01_transfer.py", []),
    "l10-inv": ("10.2", "Inventory reservation under contention", "labs/lab10/02_inventory.py", []),
    "l11-hotspot": ("11", "Shard-key hotspot analysis", "labs/lab11/02_hotspot.py", []),
    "l14-mon": ("14.1", "Monitoring snapshot", "labs/lab14/01_monitor.py", ["--once"]),
    "l14-backup": ("14.2", "Backup and restore verification", "labs/lab14/02_backup_verify.py", ["verify"]),
    "l15-seed": ("15.1", "Seed 5 tenants (windows, linux...)", "labs/lab15/01_seed.py", []),
    "l15-api": ("15.1", "Tenant, role and rate-limit test", "labs/lab15/02_test_api.py", []),
    "l15-migrate": ("15.2", "Isolation migration and benchmark", "labs/lab15/03_migrate.py", []),
    "l12-rbac": ("12.1", "RBAC and field-redaction demonstration", "labs/lab12/01_rbac_views.py", []),
    "l12-tls": ("12.2", "TLS connection verification", "labs/lab12/02_tls_test.py", []),
    "l13-authfail": ("13.1", "Authenticated failover observer", "labs/lab13/01_failover_auth.py", ["--seconds", "20"]),
    "l16-seed": ("16", "Seed shared MongoDB, Cassandra, and Neo4j data", "labs/lab16/01_model_and_seed.py", []),
    "l17-rag": ("17.1", "Atlas Local RAG pipeline", "labs/lab17/01_rag_pipeline.py", []),
    "l17-vector": ("17.2", "MongoDB vs Neo4j HNSW (same 5,000 vectors)", "labs/lab17/02_hnsw_vs_ivf.py", []),
    "l18-benchmark": ("18", "Cross-database benchmark (100,000 records)", "labs/lab18/01_benchmark.py", []),
}

RUN_WARNINGS = {
    "l2-all": "Rebuilds the isolated nosql_exercise_2.books collection. Existing data in that lab collection will be replaced.",
    "l3-all": "Recreates isolated Lab 3 courses/posts/comments collections. Existing data in those lab collections will be replaced.",
    "l4-all": "Recreates isolated Lab 4 products collection for the query/upsert exercise.",
    "l5-aggregation": "Recreates only the isolated Lab 5 orders collection in lab5_sales_analytics.",
    "l5-bucket": "Recreates only the isolated Lab 5 orders collection in lab5_sales_analytics.",
    "l5-lookup": "Recreates only the isolated Lab 5 products and orders collections in lab5_sales_analytics.",
    "l5-lookup-pipeline": "Recreates only the isolated Lab 5 products and orders collections in lab5_sales_analytics.",
    "l6-index-design": "Recreates only lab6_indexing.products and creates its query indexes. The 50,000 generated documents are isolated from SENTINEL-X threat data.",
    "l6-index-stats": "Runs the Lab 6 workload repeatedly and reads index usage statistics from lab6_indexing.products.",
    "l6-write-benchmark": "Recreates only lab6_indexing.write_benchmark and inserts 20,000 benchmark records.",
    "l6-covered-query": "Creates a compound index in the isolated lab6_indexing.products collection.",
    "l11-hotspot": "Drops and recreates the isolated lab11 database. Requires the dedicated sharded cluster to be running.",
    "l12-rbac": "Drops and recreates users, roles, views and collections in the isolated cti_auth database. Requires the dedicated RBAC MongoDB stack.",
    "l12-tls": "Writes a test document to the isolated TLS test database. Requires the dedicated TLS MongoDB stack and generated certificates.",
    "l13-authfail": "Connects to the separate keyfile-protected replica set. Requires the Lab 13 stack and KEYFILE_MONGO_URI; runs for 20 seconds.",
    "l7-analyze": "Recreates the Lab 7 embedded-document experiment collection. Do not run if you need to preserve prior lab7.threats_embedded results.",
    "l9-wc": "Drops and recreates the Lab 9 write-concern test collection. This is isolated test data, not the main threat collection.",
    "l16-seed": "This resets the Lab 16 MongoDB threats and deletes all Neo4j nodes before reseeding. "
                "It also truncates the two Lab 16 Cassandra tables. Continue only if this lab data is disposable.",
}

RUN_NOTES = {
    "l11-hotspot": "Requires the dedicated sharded cluster; only the isolated lab11 database is reset.",
    "l12-rbac": "Requires the dedicated RBAC stack at localhost:27200; only the isolated cti_auth database is changed.",
    "l12-tls": "Requires the dedicated TLS stack at localhost:27201 and generated docker/tls/certs.",
    "l13-authfail": "Requires the keyfile-protected rs1 stack and KEYFILE_MONGO_URI. Bounded 20-second observation.",
    "l16-seed": "Requires the replica set, Cassandra, and Neo4j. Replaces cti_hybrid.threats, truncates the Lab 16 Cassandra tables, and clears every node in Neo4j's default database.",
    "l17-rag": "Requires Atlas Local and Ollama. Adds/updates labeled chunks without deleting existing data.",
    "l17-vector": "Requires Atlas Local and Neo4j. Upserts the same 5,000 vectors into dedicated Lab 17.2 datasets; it does not delete existing data.",
    "l18-benchmark": "Read-only benchmark; requires 100,000 Lab 16 records in MongoDB, Cassandra, and Neo4j. Measures four query patterns using the median of 10 runs.",
    "l6-index-stats": "Run Lab 6.1 index design first so the products collection and its indexes exist.",
    "l6-covered-query": "Run Lab 6.1 index design first so the products collection exists; this activity adds a covered-query compound index.",
}

# Experiments that change containers or need extra stacks: shown as commands, not run from the page.
MANUAL = [
    {"lab": "9.2", "title": "Network partition", "cmd": "Requires Docker network control; intentionally not exposed through the web API. Use the documented isolated network experiment."},
    {"lab": "11", "title": "Sharding stack prerequisite", "cmd": "Start docker/sharding/docker-compose.yml with its init profile before running the registered Lab 11 hotspot analysis."},
    {"lab": "12.1", "title": "RBAC stack prerequisite", "cmd": "Start docker/tls/docker-compose.yml before running the registered Lab 12.1 RBAC exercise."},
    {"lab": "12.2", "title": "TLS certificate prerequisite", "cmd": "Generate docker/tls/certs with docker/tls/gen_certs.py and start the TLS stack before running Lab 12.2."},
    {"lab": "13.1", "title": "Keyfile replica-set prerequisite", "cmd": "Start docker/replica-set/docker-compose.prod.yml and set KEYFILE_MONGO_URI before running the bounded Lab 13 observer."},
]


# Shared integration map: all labs report execution evidence to the same MongoDB
# experiment_runs collection; threat-intelligence views use the shared cti.threats
# and cti.sources collections. Infrastructure-specific labs remain gated.
LAB_INTEGRATION = {
    "1": {"title": "Database foundations", "uses": ["offline classification and application mapping"], "feeds": ["2", "3", "4"]},
    "2": {"title": "MongoDB environment & CRUD", "uses": ["MongoDB replica set", "isolated nosql_exercise_2 database"], "feeds": ["3", "4"]},
    "3": {"title": "Document modeling & migration", "uses": ["MongoDB replica set", "isolated nosql_exercise_3 database"], "feeds": ["4", "7"]},
    "4": {"title": "Queries, updates & bulk operations", "uses": ["MongoDB replica set", "isolated nosql_exercise_4 database"], "feeds": ["5", "7", "9"]},
    "5": {"title": "Aggregation pipelines & joins", "uses": ["MongoDB replica set", "isolated lab5_sales_analytics database", "$group, $project, $bucket and $lookup"], "feeds": ["6", "7"]},
    "6": {"title": "Index design & performance", "uses": ["MongoDB replica set", "isolated lab6_indexing database", "explain(), $indexStats and covered queries"], "feeds": ["7", "18"]},
    "7": {"title": "Data modeling & performance", "uses": ["shared MongoDB replica set", "cti.threats", "experiment_runs"], "feeds": ["8", "14", "18"]},
    "8": {"title": "Replication & failover", "uses": ["MongoDB rs0 nodes", "replica health"], "feeds": ["9", "13", "14"]},
    "9": {"title": "Write concern & partitions", "uses": ["MongoDB rs0", "write concern measurements"], "feeds": ["10", "14", "18"]},
    "10": {"title": "Transactions & consistency", "uses": ["MongoDB transaction-capable replica set", "transaction evidence"], "feeds": ["14", "18"]},
    "11": {"title": "Sharding & shard keys", "uses": ["dedicated sharding stack", "shard distribution and hotspot metrics"], "feeds": ["14", "18"]},
    "12": {"title": "RBAC & TLS", "uses": ["dedicated secured MongoDB stack", "role and TLS test results"], "feeds": ["13", "14"]},
    "13": {"title": "Authenticated failover", "uses": ["keyfile-protected replica set", "failover evidence"], "feeds": ["14"]},
    "14": {"title": "Monitoring & backup", "uses": ["replica-set health", "metrics and backup evidence"], "feeds": ["all labs"]},
    "15": {"title": "Multi-tenant isolation", "uses": ["tenant collections", "API role and isolation tests"], "feeds": ["16", "18"]},
    "16": {"title": "Polyglot persistence", "uses": ["MongoDB", "Cassandra", "Neo4j"], "feeds": ["17", "18"]},
    "17": {"title": "Vector search & RAG", "uses": ["Atlas Local vector store", "Ollama embeddings and LLM"], "feeds": ["18", "assistant"]},
    "18": {"title": "Cross-database benchmark", "uses": ["Lab 16 datasets", "MongoDB/Cassandra/Neo4j query timings"], "feeds": ["executive overview"]},
}


@router.get("/integration")
def integration():
    """Return lab dependencies, shared evidence counts, and latest run summaries."""
    latest = list(db.experiment_runs.aggregate([
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$lab", "last_status": {"$first": "$status"},
                     "last_ts": {"$first": "$ts"}, "runs": {"$sum": 1}}}
    ]))
    by_lab = {str(x["_id"]).split('.')[0]: x for x in latest}
    items = []
    for lab, meta in LAB_INTEGRATION.items():
        item = dict(meta)
        item.update({"lab": int(lab), "latest": by_lab.get(lab, {}),
                     "registered_experiments": sum(1 for v in EXPERIMENTS.values() if v[0].split('.')[0] == lab),
                     "manual_steps": sum(1 for v in MANUAL if str(v["lab"]).split('.')[0] == lab)})
        items.append(item)
    return {"labs": items, "shared": {"threat_records": db.threats.count_documents({}),
            "sources": db.sources.count_documents({}), "execution_records": db.experiment_runs.count_documents({})},
            "note": "Interconnection is through shared MongoDB intelligence/evidence and the central assistant. Some labs use isolated infrastructure and require their documented prerequisites; they are not one continuously shared database."}


@router.get("/status")
def status():
    out = {"threats": db.threats.count_documents({}), "vectors": db.threat_vectors.count_documents({})}
    try:
        out["mongo"] = snapshot()
    except Exception as e:
        out["mongo"] = {"error": str(e)}
    try:
        ollama_url = config.OLLAMA_URL
        tags = requests.get(f"{ollama_url}/api/tags", timeout=2).json()
        out["ollama"] = [m["name"] for m in tags["models"]]
    except Exception:
        out["ollama"] = None
    return out


@router.get("/experiments")
def experiments(user=Depends(current_user)):
    last = {r["_id"]: r for r in db.experiment_runs.aggregate([
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$exp", "ok": {"$first": "$ok"}, "seconds": {"$first": "$seconds"},
                    "status": {"$first": "$status"}, "ts": {"$first": "$ts"},
                    "output": {"$first": "$output"}}}])}
    allowed = [i for i, v in EXPERIMENTS.items() if can_view_lab(user, int(v[0].split(".")[0]))]
    return {"experiments": [{"id": i, "lab": EXPERIMENTS[i][0], "title": EXPERIMENTS[i][1], "last": last.get(i),
                             "warning": RUN_WARNINGS.get(i), "note": RUN_NOTES.get(i),
                             "can_run": user.get("role") == "admin" or (user.get("role") != "professor" and user.get("permissions", {}).get("can_run_labs") and int(EXPERIMENTS[i][0].split(".")[0]) in user.get("permissions", {}).get("labs", []))}
                            for i in allowed],
            "manual": [m for m in MANUAL if can_view_lab(user, int(str(m["lab"]).split(".")[0]))]}


@router.post("/run/{exp_id}")
def run(exp_id: str, confirmed: bool = False, user=Depends(current_user)):
    """Run a registered experiment only when the user's per-lab run permission allows it."""
    if exp_id not in EXPERIMENTS:
        raise HTTPException(404, "unknown experiment")
    require_lab_run(user, int(EXPERIMENTS[exp_id][0].split(".")[0]))
    if exp_id in RUN_WARNINGS and not confirmed:
        raise HTTPException(409, "Explicit confirmation is required to run this experiment.")
    meta = EXPERIMENTS[exp_id]
    try:
        job = start_job(exp_id, meta, (user or {}).get("sub") if isinstance(user, dict) else None)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    return {"job_id": job["job_id"], "exp": exp_id, "lab": job["lab"], "title": job["title"],
            "status": job["status"], "output": job["output"], "seconds": 0, "queued": True}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user=Depends(current_user)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Lab job not found")
    require_lab_view(user, int(str(job.get("lab", "0")).split(".")[0]))
    return job


@router.get("/jobs/latest/{lab}")
def latest_lab_job(lab: int, user=Depends(current_user)):
    if not 1 <= lab <= 18:
        raise HTTPException(404, "Lab not found")
    require_lab_view(user, lab)
    job = latest_job(lab)
    return {"job": job}

# User-selectable scheduler settings. Values are seconds: 10s, 30s, 1m, 5m, 10m, 30m.
ALLOWED_SYNC_INTERVALS = {10, 30, 60, 300, 600, 1800}

@router.get("/settings/sync")
def get_sync_settings():
    doc = db.platform_settings.find_one({"_id": "sync"}) or {}
    return {"interval_seconds": int(doc.get("interval_seconds", 900))}

@router.post("/settings/sync", dependencies=[Depends(require_admin)])
def set_sync_settings(body: dict):
    try:
        seconds = int(body.get("interval_seconds"))
    except (TypeError, ValueError):
        raise HTTPException(400, "interval_seconds must be one of 10, 30, 60, 300, 600, 1800")
    if seconds not in ALLOWED_SYNC_INTERVALS:
        raise HTTPException(400, "Choose 10s, 30s, 1m, 5m, 10m or 30m")
    db.platform_settings.update_one({"_id": "sync"}, {"$set": {"interval_seconds": seconds, "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    return {"ok": True, "interval_seconds": seconds}

@router.post("/sync/now", dependencies=[Depends(require_admin)])
def sync_now():
    try:
        from ingest import sync_once
        result = sync_once()
        return result
    except Exception as exc:
        raise HTTPException(503, f"Threat sync failed: {type(exc).__name__}: {str(exc)[:250]}")

@router.get("/export/experiments.csv")
def export_experiments():
    import csv, io
    from fastapi.responses import StreamingResponse
    rows = list(db.experiment_runs.find({}, {"_id": 0}).sort("ts", -1).limit(5000))
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["lab", "experiment", "status", "seconds", "timestamp", "output"])
    for x in rows: w.writerow([x.get("lab"), x.get("title"), x.get("status"), x.get("seconds"), x.get("ts"), x.get("output", "")])
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sentinelx-lab-runs.csv"})
