"""Overview dashboard analytics. Every number is computed from stored data."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query

from common import db
from saas import current_user

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
SEV = {"expr": {"$toLower": {"$ifNull": ["$classification.severity", "unclassified"]}}}


@router.get("/overview")
def overview(days: int = Query(30, ge=1, le=365), granularity: str = Query("day", pattern="^(day|week)$"),
             user=Depends(current_user)):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    sev = {x["_id"]: x["n"] for x in db.threats.aggregate([{"$group": {"_id": SEV["expr"], "n": {"$sum": 1}}}])}
    fmt = "%Y-%m-%d" if granularity == "day" else "%G-W%V"
    timeline = [{"bucket": x["_id"], "count": x["n"]} for x in db.threats.aggregate([
        {"$match": {"published_at": {"$gte": since}}},
        {"$group": {"_id": {"$dateToString": {"format": fmt, "date": "$published_at"}}, "n": {"$sum": 1}}},
        {"$sort": {"_id": 1}}])]
    categories = [{"label": x["_id"] or "Unclassified", "count": x["n"]} for x in db.threats.aggregate([
        {"$group": {"_id": "$classification.type", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 10}])]
    sources = [{"label": (x.get("src") or [{}])[0].get("name") or str(x["_id"] or "Unknown"), "count": x["n"]}
               for x in db.threats.aggregate([
                   {"$group": {"_id": "$source_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 10},
                   {"$lookup": {"from": "sources", "localField": "_id", "foreignField": "_id", "as": "src"}}])]
    origins = {(x["_id"] or "unknown"): x["n"] for x in db.threats.aggregate([{"$group": {"_id": "$record_origin", "n": {"$sum": 1}}}])}

    health = {"database": "unavailable", "replica_primary": None}
    try:
        db.command("ping"); health["database"] = "ok"
        from monitor import snapshot
        members = snapshot().get("members", [])
        health["replica_primary"] = any(m["state"] == "PRIMARY" for m in members) if members else None
        health["members_up"] = f"{sum(1 for m in members if m['state'] in ('PRIMARY', 'SECONDARY'))}/{len(members)}" if members else None
    except Exception as exc:  # health must never crash the dashboard
        health["detail"] = f"{type(exc).__name__}"

    activity = [{"bucket": x["_id"], "count": x["n"]} for x in db.experiment_runs.aggregate([
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {"_id": {"$dateToString": {"format": fmt, "date": "$ts"}}, "n": {"$sum": 1}}},
        {"$sort": {"_id": 1}}])]

    out = {
        "range_days": days, "granularity": granularity, "generated_at": now,
        "kpis": {"total": db.threats.count_documents({}), "critical": sev.get("critical", 0),
                 "high": sev.get("high", 0), "medium": sev.get("medium", 0), "low": sev.get("low", 0),
                 "sources": db.sources.count_documents({}),
                 "recent_24h": db.threats.count_documents({"published_at": {"$gte": now - timedelta(hours=24)}}),
                 "recent_7d": db.threats.count_documents({"published_at": {"$gte": now - timedelta(days=7)}}),
                 "in_range": db.threats.count_documents({"published_at": {"$gte": since}})},
        "health": health, "origins": origins,
        "severity": [{"label": k, "count": v} for k, v in sorted(sev.items(), key=lambda kv: -kv[1])],
        "categories": categories, "sources": sources, "timeline": timeline, "system_activity": activity,
    }
    if user.get("role") == "admin":
        out["kpis"]["users"] = db.users.count_documents({})
        out["kpis"]["users_active"] = db.users.count_documents({"active": {"$ne": False}})
        out["kpis"]["failed_logins_24h"] = db.login_activity.count_documents(
            {"success": False, "created_at": {"$gte": now - timedelta(hours=24)}})
        out["login_activity"] = [{"bucket": x["_id"], "success": x["ok"], "failed": x["bad"]} for x in db.login_activity.aggregate([
            {"$match": {"created_at": {"$gte": since}, "event_type": {"$nin": ["registration", "logout"]}}},
            {"$group": {"_id": {"$dateToString": {"format": fmt, "date": "$created_at"}},
                        "ok": {"$sum": {"$cond": ["$success", 1, 0]}}, "bad": {"$sum": {"$cond": ["$success", 0, 1]}}}},
            {"$sort": {"_id": 1}}])]
    return out
