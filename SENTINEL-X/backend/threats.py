"""Threat intelligence APIs: list, detail, facets, stats, sources and CSV export (authenticated)."""
import csv
import io
import re

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from common import db
from saas import current_user
from security_utils import csv_safe, parse_day

router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
SORTS = {"published_at": "published_at", "title": "title", "type": "classification.type",
         "severity": "classification.severity", "source": "source_id"}


def _match(q="", type="", severity="", source="", origin="", ioc="", date_from="", date_to=""):
    m: dict = {}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        m["$or"] = [{"title": rx}, {"content": rx}, {"iocs.value": rx}]
    if type:
        m["classification.type"] = type
    if severity:
        m["classification.severity"] = {"$regex": f"^{re.escape(severity)}$", "$options": "i"}
    if source:
        m["source_id"] = source
    if origin:
        m["record_origin"] = origin
    if ioc:
        m["iocs.value"] = {"$regex": re.escape(ioc), "$options": "i"}
    try:
        start, end = parse_day(date_from), parse_day(date_to, end_of_day=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if start or end:
        m["published_at"] = {k: v for k, v in (("$gte", start), ("$lte", end)) if v}
    return m


def _serialise(x: dict, full=False) -> dict:
    out = {"id": str(x["_id"]), "title": x.get("title"), "url": x.get("url"),
           "published_at": x.get("published_at"), "classification": x.get("classification") or {},
           "iocs": x.get("iocs") or [], "source": x.get("source_name") or x.get("source_id"),
           "source_id": x.get("source_id"), "origin": x.get("record_origin", "unknown"),
           "verification": (x.get("verification") or {}).get("status", "unverified")}
    if full:
        out["description"] = x.get("content")
        out["verification_detail"] = x.get("verification")
        out["platform"] = x.get("platform")
        out["status"] = x.get("status")
    return out


def _with_source(match, sort_field, direction, skip, limit):
    return [{"$match": match}, {"$sort": {sort_field: direction, "_id": 1}}, {"$skip": skip}, {"$limit": limit},
            {"$lookup": {"from": "sources", "localField": "source_id", "foreignField": "_id", "as": "src"}},
            {"$addFields": {"source_name": {"$ifNull": [{"$arrayElemAt": ["$src.name", 0]}, "$source_id"]}}},
            {"$project": {"src": 0}}]


@router.get("/threats")
def threats(q: str = "", type: str = "", severity: str = "", source: str = "", origin: str = "",
            ioc: str = "", date_from: str = "", date_to: str = "",
            sort: str = "published_at", order: str = "desc",
            limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0)):
    match = _match(q, type, severity, source, origin, ioc, date_from, date_to)
    total = db.threats.count_documents(match)
    rows = db.threats.aggregate(_with_source(match, SORTS.get(sort, "published_at"),
                                             1 if order == "asc" else -1, skip, limit))
    return {"total": total, "skip": skip, "limit": limit, "results": [_serialise(x) for x in rows]}


@router.get("/threats/facets")
def facets():
    sev = [x["_id"] for x in db.threats.aggregate([{"$group": {"_id": "$classification.severity"}}, {"$sort": {"_id": 1}}]) if x["_id"]]
    typ = [x["_id"] for x in db.threats.aggregate([{"$group": {"_id": "$classification.type"}}, {"$sort": {"_id": 1}}]) if x["_id"]]
    org = [x["_id"] for x in db.threats.aggregate([{"$group": {"_id": "$record_origin"}}, {"$sort": {"_id": 1}}]) if x["_id"]]
    src = [{"id": x["_id"], "name": x.get("name", x["_id"])} for x in db.sources.find({}, {"name": 1}).sort("name", 1)]
    return {"severities": sev, "types": typ, "origins": org, "sources": src}


@router.get("/threats/{threat_id}")
def threat_detail(threat_id: str):
    ids = [threat_id] + ([ObjectId(threat_id)] if ObjectId.is_valid(threat_id) else [])
    rows = list(db.threats.aggregate(_with_source({"_id": {"$in": ids}}, "published_at", -1, 0, 1)))
    if not rows:
        raise HTTPException(404, "Threat record not found.")
    return _serialise(rows[0], full=True)


@router.get("/stats")
def stats():
    by_type = list(db.threats.aggregate([{"$group": {"_id": "$classification.type", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    by_severity = list(db.threats.aggregate([{"$group": {"_id": "$classification.severity", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
    return {"total": db.threats.count_documents({}), "sources": db.sources.count_documents({}),
            "by_type": by_type, "by_severity": by_severity}


@router.get("/sources")
def sources():
    return list(db.sources.find({}, {"name": 1, "url": 1, "feed_url": 1}))


@router.get("/export/threats.csv")
def export_threats(q: str = "", type: str = "", severity: str = "", source: str = "", origin: str = "",
                   ioc: str = "", date_from: str = "", date_to: str = ""):
    match = _match(q, type, severity, source, origin, ioc, date_from, date_to)
    cols = ["title", "type", "severity", "source", "url", "published_at", "iocs", "record_origin", "verification_status"]

    def stream():
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(cols); yield buf.getvalue(); buf.seek(0); buf.truncate()
        for x in db.threats.aggregate(_with_source(match, "published_at", -1, 0, 50000)):
            c, v = x.get("classification") or {}, x.get("verification") or {}
            iocs = "; ".join(str(i.get("value", i)) if isinstance(i, dict) else str(i) for i in (x.get("iocs") or []))
            w.writerow([csv_safe(z) for z in (x.get("title"), c.get("type"), c.get("severity"), x.get("source_name"),
                                              x.get("url"), x.get("published_at"), iocs, x.get("record_origin"), v.get("status"))])
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    return StreamingResponse(stream(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=sentinelx-threats.csv"})
