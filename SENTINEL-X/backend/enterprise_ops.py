"""Safe enterprise operations API for SENTINEL-X.

Database query endpoints are read-only, bounded and audited. No arbitrary shell,
Docker socket, database write, or unrestricted Cypher/CQL execution is exposed.
"""
from __future__ import annotations
import os, re, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from saas import current_user, require_admin
from common import db
from dashboard import EXPERIMENTS

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"], dependencies=[Depends(current_user)])
ROOT = Path(__file__).resolve().parent.parent
ALLOWED_MONGO = {
    "threats": ("threats", {"title": 1, "classification": 1, "published_at": 1, "record_origin": 1}),
    "sources": ("sources", {"name": 1, "url": 1, "enabled": 1}),
    "transactions": ("lab10_transactions.records", {"transaction_id": 1, "account_id": 1, "amount_cents": 1, "currency": 1, "status": 1}),
}

def _audit(user, action, target, details=None):
    try:
        db.enterprise_audit.insert_one({
            "event_id": uuid.uuid4().hex, "username": user.get("sub", "unknown"),
            "role": user.get("role", "user"), "action": action, "target": target,
            "details": details or {}, "created_at": datetime.now(timezone.utc)
        })
    except Exception:
        # Audit failures must not silently authorize privileged actions.
        raise HTTPException(503, "Audit log unavailable; operation was not performed.")

def _is_admin(user):
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator role required.")

@router.get("/registry")
def registry(user=Depends(current_user)):
    labs = {}
    for exp_id, meta in EXPERIMENTS.items():
        lab, title, script, args = meta
        labs.setdefault(lab, []).append({"id": exp_id, "title": title, "script": script,
                                         "registered": (ROOT / script).is_file()})
    return {"labs": labs, "excluded_labs": ["5", "6"], "count": len(EXPERIMENTS),
            "note": "Only registered scripts are executable. Check prerequisites and data-impact warnings before launch."}

@router.get("/jobs")
def job_history(limit: int = 50, user=Depends(current_user)):
    limit = max(1, min(limit, 200))
    rows = list(db.lab_jobs.find({}, {"_id": 0, "job_id": 1, "exp": 1, "lab": 1, "title": 1,
        "status": 1, "created_at": 1, "started_at": 1, "finished_at": 1, "seconds": 1,
        "triggered_by": 1}).sort("created_at", -1).limit(limit))
    return {"jobs": rows}

@router.get("/audit")
def audit_history(limit: int = 100, user=Depends(current_user)):
    _is_admin(user)
    rows = list(db.enterprise_audit.find({}, {"_id": 0}).sort("created_at", -1).limit(max(1,min(limit,500))))
    return {"events": rows}

@router.post("/query/mongo")
def mongo_query(body: dict[str, Any], user=Depends(current_user)):
    key = str(body.get("dataset", ""))
    if key not in ALLOWED_MONGO:
        raise HTTPException(400, "Choose one of the supported datasets: threats, sources, transactions.")
    collection, projection = ALLOWED_MONGO[key]
    limit = max(1, min(int(body.get("limit", 20)), 100))
    coll = db
    for part in collection.split("."):
        coll = coll[part]
    try:
        rows = list(coll.find({}, projection).limit(limit))
        total = coll.count_documents({}, maxTimeMS=4000)
    except Exception as exc:
        raise HTTPException(503, f"MongoDB query failed: {type(exc).__name__}")
    _audit(user, "mongo.read", key, {"limit": limit, "returned": len(rows)})
    for row in rows:
        row.pop("_id", None)
    return {"dataset": key, "total": total, "returned": len(rows), "rows": rows}

@router.post("/query/cassandra")
def cassandra_query(body: dict[str, Any], user=Depends(current_user)):
    table = str(body.get("table", ""))
    allowed = {"threat_by_id": "SELECT * FROM cti.threat_by_id LIMIT 50",
               "threats_by_platform": "SELECT * FROM cti.threats_by_platform LIMIT 50"}
    if table not in allowed:
        raise HTTPException(400, "Allowed tables: threat_by_id, threats_by_platform.")
    try:
        from cassandra.cluster import Cluster
        cluster = Cluster([os.getenv("CASSANDRA_HOST", "cassandra")], port=int(os.getenv("CASSANDRA_PORT","9042")))
        session = cluster.connect()
        rows = [dict(r._asdict()) for r in session.execute(allowed[table])]
        cluster.shutdown()
    except Exception as exc:
        raise HTTPException(503, f"Cassandra unavailable/query failed: {type(exc).__name__}")
    _audit(user, "cassandra.read", table, {"returned": len(rows)})
    return {"table": table, "returned": len(rows), "rows": rows}

@router.post("/query/neo4j")
def neo4j_query(body: dict[str, Any], user=Depends(current_user)):
    query_id = str(body.get("query_id", ""))
    queries = {
      "threat_counts": "MATCH (t:Threat) RETURN count(t) AS threats",
      "top_types": "MATCH (t:Threat) RETURN t.type AS type, count(*) AS count ORDER BY count DESC LIMIT 20",
      "sample": "MATCH (t:Threat) RETURN t LIMIT 25"
    }
    if query_id not in queries:
        raise HTTPException(400, "Allowed query_id values: threat_counts, top_types, sample.")
    try:
        from neo4j import GraphDatabase
        uri=os.getenv("NEO4J_URI","bolt://neo4j:7687")
        driver=GraphDatabase.driver(uri, auth=("neo4j",os.getenv("NEO4J_PASSWORD","change-this-local")))
        with driver.session() as session:
            rows=[r.data() for r in session.run(queries[query_id], timeout=8)]
        driver.close()
    except Exception as exc:
        raise HTTPException(503, f"Neo4j unavailable/query failed: {type(exc).__name__}")
    _audit(user, "neo4j.read", query_id, {"returned":len(rows)})
    return {"query_id":query_id,"rows":rows}

@router.get("/infrastructure")
def infrastructure(user=Depends(current_user)):
    # Read-only service reachability. Container lifecycle control intentionally stays
    # outside the API until a separately hardened host agent is deployed.
    checks = {"api": True, "mongo": False, "ollama": False, "cassandra": False, "neo4j": False}
    try: db.command("ping"); checks["mongo"] = True
    except Exception: pass
    try:
        import requests
        checks["ollama"] = requests.get(os.getenv("OLLAMA_URL","http://host.docker.internal:11434")+"/api/tags", timeout=2).ok
    except Exception: pass
    try:
        from cassandra.cluster import Cluster
        c=Cluster([os.getenv("CASSANDRA_HOST","cassandra")], port=int(os.getenv("CASSANDRA_PORT","9042")))
        c.connect().shutdown(); c.shutdown(); checks["cassandra"]=True
    except Exception: pass
    try:
        from neo4j import GraphDatabase
        d=GraphDatabase.driver(os.getenv("NEO4J_URI","bolt://neo4j:7687"),auth=("neo4j",os.getenv("NEO4J_PASSWORD","change-this-local")))
        d.verify_connectivity(); d.close(); checks["neo4j"]=True
    except Exception: pass
    return {"services":checks,"checked_at":datetime.now(timezone.utc).isoformat(),
            "container_control":"disabled: deploy a separately authenticated host agent for lifecycle actions"}

@router.get("/reports/labs.csv")
def export_labs_csv(user=Depends(current_user)):
    from fastapi.responses import StreamingResponse
    import csv, io
    _is_admin(user)
    buf=io.StringIO(); writer=csv.writer(buf)
    writer.writerow(["job_id","lab","experiment","title","status","seconds","created_at","triggered_by"])
    for r in db.lab_jobs.find({}, {"_id":0}).sort("created_at",-1).limit(5000):
        writer.writerow([r.get("job_id"),r.get("lab"),r.get("exp"),r.get("title"),r.get("status"),
                         r.get("seconds"),r.get("created_at"),r.get("triggered_by")])
    _audit(user,"report.export","lab_jobs",{"format":"csv"})
    from fastapi.responses import Response
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":"attachment; filename=sentinelx-lab-history.csv"})
