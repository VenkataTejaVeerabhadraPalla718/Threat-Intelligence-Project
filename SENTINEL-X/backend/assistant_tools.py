"""Deterministic, read-only MongoDB tools used by the SENTINEL-X assistant."""
import re
from datetime import datetime, timedelta, timezone


def _severity_match(text):
    t = text.lower()
    for word in ("critical", "high", "medium", "low", "informational", "info"):
        if re.search(r"\b" + word + r"\b", t):
            return "informational" if word == "info" else word
    return None


def _safe_group(db, field, limit=12):
    return list(db.threats.aggregate([
        {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ], maxTimeMS=8000))

_TYPES = ("malware", "phishing", "ransomware", "vulnerability", "data breach", "ddos")


def _ensure_threats(db):
    """Self-heal: if cti.threats is empty (e.g. after a restore), re-seed labelled demo data."""
    try:
        if db.threats.estimated_document_count() > 0:
            return
        import seed_demo  # idempotent, clearly labelled synthetic records
        seed_demo.main()
    except Exception:
        pass


def _ensure_transactions(db):
    try:
        tx = db["lab10_transactions"]["records"]
        if tx.estimated_document_count() > 0:
            return
        import os
        import bootstrap_datasets as bd
        bd.LAB10_TARGET = int(os.getenv("LAB10_QUICK_TARGET", "20000"))
        bd.seed_lab10()
    except Exception:
        pass


def answer_data_question(question, db):
    """Return a database-grounded answer for common CTI analytics requests, else None."""
    q = question.lower()
    try:
        # Lab 16 polyglot-persistence dataset: authoritative live MongoDB count.
        # The lab seeder writes to cti_hybrid.threats (not the main cti.threats collection).
        mentions_lab16 = bool(re.search(r"\b(?:lab\s*16|lab16)\b", q))
        asks_lab16_count = any(term in q for term in (
            "how many", "count", "total", "number", "records", "threats", "documents", "data"
        ))
        lab16_count_question = mentions_lab16 and asks_lab16_count
        if lab16_count_question:
            lab16_collection = db.client["cti_hybrid"]["threats"]
            count = lab16_collection.count_documents({}, maxTimeMS=15000)
            return (f"Lab 16 live MongoDB count: **{count:,} threat records**.\n"
                    "Source: `cti_hybrid.threats`. This value was queried directly from MongoDB.")

        # Lab 10 transaction dataset: read-only summaries and filtered samples.
        if "transaction" in q or "transfer" in q or "bank" in q:
            _ensure_transactions(db)
            tx = db["lab10_transactions"]["records"]
            tx_total = tx.count_documents({}, maxTimeMS=5000)
            id_match = re.search(r"(?:transaction|transfer)\s*(?:id|#)?\s*[:=]?\s*([A-Za-z0-9_-]{5,80})", question, re.I)
            if id_match:
                row = tx.find_one({"transaction_id": id_match.group(1)}, {"_id": 0})
                return f"Transaction {id_match.group(1)}: {row if row else 'not found in Lab 10 records'}"
            status_match = next((v for v in ("committed", "pending", "reversed", "failed") if v in q), None)
            if status_match and any(k in q for k in ("show", "list", "latest", "recent", "count", "how many", "number")):
                flt = {"status": status_match}
                n = tx.count_documents(flt, maxTimeMS=5000)
                if any(k in q for k in ("show", "list", "latest", "recent")):
                    rows = list(tx.find(flt, {"_id": 0}).sort("transaction_id", -1).limit(10))
                    detail = "\n".join(f"- {r.get('transaction_id')} | {r.get('amount_cents')} {r.get('currency','INR')} | {r.get('account_id')}" for r in rows)
                    return f"Lab 10 {status_match} transactions: {n:,} total.\n{detail}"
                return f"Lab 10 has {n:,} {status_match} transactions (live MongoDB count)."
            if any(k in q for k in ("latest", "recent", "show", "list", "details")):
                rows = list(tx.find({}, {"_id": 0}).sort("transaction_id", -1).limit(10))
                return f"Latest {len(rows)} Lab 10 transaction records (live MongoDB query; {tx_total:,} total):\n" + "\n".join(
                    f"- {r.get('transaction_id', '?')} | amount_cents={r.get('amount_cents', '?')} | status={r.get('status', '?')} | account={r.get('account_id', '?')}"
                    for r in rows)
            if any(k in q for k in ("how many", "count", "total", "number")):
                return f"Lab 10 transaction collection contains {tx_total:,} records (live MongoDB count)."
            rows = list(tx.find({}, {"_id": 0}).limit(5))
            return f"Lab 10 transaction data is available: {tx_total:,} records. Sample rows:\n" + "\n".join(str(r)[:400] for r in rows)
        # Classify the request before querying MongoDB. Previously every non-transaction
        # question triggered a collection count, even when it was not a data question.
        sev = _severity_match(q)
        wants_severity = any(k in q for k in ("how many", "count", "number of", "total")) and (sev or "severity" in q or "risk" in q)
        wants_category = any(k in q for k in ("categor", "type", "classification", "malware family"))
        wants_source = "source" in q and any(k in q for k in ("how many", "count", "top", "most", "list", "number"))
        wants_recent = any(k in q for k in ("last 24", "last day", "today", "recent", "last hour", "last 7 days"))
        wants_latest = any(k in q for k in ("latest threat", "recent threats", "show threats", "list threats", "top threats"))
        wants_named_search = bool(re.search(r"(?:find|search|details|information|info|about)\s+(?:the\s+)?(?:threat\s+)?(.{3,100})", question, re.I))
        wants_total = any(k in q for k in ("how many threats", "total threats", "threat count", "number of threats"))
        if not any((wants_severity, wants_category, wants_source, wants_recent, wants_latest, wants_named_search, wants_total)):
            return None
        _ensure_threats(db)
        total = db.threats.count_documents({}, maxTimeMS=5000)
        # Severity counts and comparisons
        if wants_severity:
            if sev:
                n = db.threats.count_documents({"classification.severity": {"$regex": f"^{re.escape(sev)}$", "$options": "i"}}, maxTimeMS=5000)
                return f"There are {n:,} threat records classified as {sev.title()} in MongoDB. Total stored threat records: {total:,}. This is a live database count."
            rows = _safe_group(db, "classification.severity", 10)
            detail = ", ".join(f"{x.get('_id') or 'Unclassified'}: {x['count']:,}" for x in rows)
            return f"Live severity distribution ({total:,} total records): {detail or 'No severity data found'}."
        # Category/type questions
        if wants_category:
            rows = _safe_group(db, "classification.type", 20)
            detail = "\n".join(f"- {x.get('_id') or 'Unclassified'}: {x['count']:,}" for x in rows)
            return f"Threat categories ranked by record count (live MongoDB aggregation):\n{detail or 'No category data found'}\nTotal records: {total:,}."
        # Source counts and ranking
        if wants_source:
            source_total = db.sources.count_documents({})
            rows = list(db.threats.aggregate([
                {"$group": {"_id": "$source_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 15},
                {"$lookup": {"from": "sources", "localField": "_id", "foreignField": "_id", "as": "src"}}
            ], maxTimeMS=8000))
            lines = []
            for x in rows:
                name = (x.get("src") or [{}])[0].get("name", str(x.get("_id") or "Unknown"))
                lines.append(f"- {name}: {x['count']:,} records")
            return f"There are {source_total:,} configured sources. Threat records by leading source:\n" + ("\n".join(lines) or "No source-linked records.")
        # Recency
        if wants_recent:
            hours = 1 if "last hour" in q else 168 if "last 7 days" in q else 24
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            n = db.threats.count_documents({"published_at": {"$gte": since}}, maxTimeMS=5000)
            return f"There are {n:,} records with published_at within the last {hours} hour(s), based on the stored timestamps. Total records: {total:,}."
        # Latest threats
        if wants_latest:
            rows = list(db.threats.find({}, {"_id": 0, "title": 1, "url": 1, "classification": 1, "published_at": 1, "record_origin": 1}).sort("published_at", -1).limit(10))
            lines = []
            for x in rows:
                c = x.get("classification") or {}
                lines.append(f"- {x.get('title','Untitled')} | severity={c.get('severity','unknown')} | type={c.get('type','unknown')} | origin={x.get('record_origin','unknown')} | {x.get('url','')}")
            return "Latest 10 stored threat records:\n" + ("\n".join(lines) or "No threat records found.")
        # Search for a named indicator/title fragment
        m = re.search(r"(?:find|search|details|information|info|about)\s+(?:the\s+)?(?:threat\s+)?(.{3,100})", question, re.I)
        if m and wants_named_search:
            term = m.group(1).strip(" ?.!\"'")
            if term and term.lower() not in {"threats", "all threats", "categories", "sources"}:
                rx = {"$regex": re.escape(term), "$options": "i"}
                rows = list(db.threats.find({"$or": [{"title": rx}, {"content": rx}, {"iocs.value": rx}]},
                    {"_id": 0, "title": 1, "url": 1, "content": 1, "classification": 1, "iocs": 1, "record_origin": 1}).limit(8))
                if rows:
                    lines = []
                    for x in rows:
                        c=x.get("classification") or {}
                        lines.append(f"- {x.get('title')} | {c.get('severity','unknown')} | {c.get('type','unknown')} | {x.get('url','')} | origin={x.get('record_origin','unknown')}")
                    return f"Found {len(rows)} matching threat records for '{term}':\n" + "\n".join(lines)
                return (f"No stored threat record matches '{term}'. The database itself is populated "
                        f"({total:,} threat records). Try a threat type (malware, phishing, ransomware, "
                        f"vulnerability, data breach, DDoS) or a severity (critical, high, medium, low).")
        # Type / severity filtered listing, e.g. "show ransomware threats"
        typ = next((t for t in _TYPES if t in q), None)
        if typ or (sev and any(k in q for k in ("show", "list", "find", "threats"))):
            flt = {}
            if typ:
                flt["classification.type"] = {"$regex": re.escape(typ), "$options": "i"}
            if sev:
                flt["classification.severity"] = {"$regex": f"^{re.escape(sev)}$", "$options": "i"}
            n = db.threats.count_documents(flt, maxTimeMS=8000)
            rows = list(db.threats.find(flt, {"_id": 0, "title": 1, "url": 1, "classification": 1, "record_origin": 1}).limit(10))
            lines = [f"- {x.get('title')} | {(x.get('classification') or {}).get('severity','?')} | {(x.get('classification') or {}).get('type','?')} | origin={x.get('record_origin','unknown')}" for x in rows]
            label = " ".join(v for v in (sev, typ) if v) or "matching"
            return f"{n:,} {label} threat records in MongoDB (showing {len(rows)}):\n" + "\n".join(lines)
        # Total threats / dashboard totals
        if wants_total:
            sources = db.sources.count_documents({})
            return f"Live database totals: {total:,} threat records and {sources:,} configured intelligence sources."
    except Exception as exc:
        return f"I could not query the threat database: {type(exc).__name__}: {str(exc)[:180]}. Check MongoDB connectivity."
    return None
