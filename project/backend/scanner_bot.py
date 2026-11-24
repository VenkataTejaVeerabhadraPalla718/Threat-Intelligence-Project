import re

from bson import ObjectId

from common import db
from rag import normalize_platform


def run_scan(platform: str = None):
    query = {"status": {"$ne": "Resolved"}}
    if platform:
        canonical_platform = normalize_platform(platform)
        pattern = {"$regex": rf"\b{re.escape(canonical_platform)}\b", "$options": "i"}
        query["$or"] = [
            {"platform": canonical_platform},
            {"title": pattern},
            {"content": pattern},
        ]

    total = db.threats.count_documents(query)
    threats = list(
        db.threats.find(query, {"title": 1, "url": 1, "source_id": 1})
        .sort("published_at", -1)
        .limit(5)
    )
    source_ids = {threat["source_id"] for threat in threats if threat.get("source_id")}
    sources = {
        source["_id"]: source.get("name", "Unknown source")
        for source in db.sources.find({"_id": {"$in": list(source_ids)}}, {"name": 1})
    }

    return {
        "total": total,
        "records": [
            {
                "id": str(threat["_id"]),
                "title": threat.get("title", "Untitled threat report"),
                "source": sources.get(threat.get("source_id"), "Unknown source"),
            }
            for threat in threats
        ],
    }


def apply_fix(vuln_id: str):
    matching_ids = [vuln_id]
    if ObjectId.is_valid(vuln_id):
        matching_ids.append(ObjectId(vuln_id))

    result = db.threats.update_one(
        {"_id": {"$in": matching_ids}, "status": {"$ne": "Resolved"}},
        {"$set": {"status": "Resolved", "mitigated": True}},
    )

    if result.modified_count > 0:
        return (
            f"Threat {vuln_id} marked 'Resolved' in MongoDB. "
            "No host remediation was performed."
        )
    return "Failed to apply fix. Threat ID not found or already resolved."
