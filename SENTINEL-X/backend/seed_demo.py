"""Idempotently add 20,000 clearly labeled synthetic demonstration records."""
import hashlib
from datetime import datetime, timedelta, timezone
from common import db

TARGET = 20000
SOURCES = [
    {"_id": "demo-source-cisa", "name": "CISA (reference source)", "url": "https://www.cisa.gov/"},
    {"_id": "demo-source-nvd", "name": "NIST NVD (reference source)", "url": "https://nvd.nist.gov/"},
    {"_id": "demo-source-mitre", "name": "MITRE ATT&CK (reference source)", "url": "https://attack.mitre.org/"},
    {"_id": "demo-source-owasp", "name": "OWASP (reference source)", "url": "https://owasp.org/"},
]
TYPES = ["Malware", "Phishing", "Ransomware", "Vulnerability", "Data Breach", "DDoS"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
PLATFORMS = ["Windows", "Linux", "macOS", "Android", "Cloud", "Network"]
STATUSES = ["Active", "Investigating", "Contained", "Resolved"]

def main():
    db.sources.bulk_write([
        __import__("pymongo").UpdateOne({"_id": s["_id"]}, {"$set": s}, upsert=True)
        for s in SOURCES
    ], ordered=False)
    ops = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(TARGET):
        key = f"sentinelx-demo-threat-{i:05d}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        typ = TYPES[i % len(TYPES)]
        sev = SEVERITIES[(i * 7 + i // 13) % len(SEVERITIES)]
        source = SOURCES[i % len(SOURCES)]
        doc = {
            "_id": key,
            "title": f"[DEMO DATA] {typ} intelligence scenario {i+1:05d}",
            "content": f"Synthetic training scenario for dashboard, search, analytics and database lab demonstrations. This record is not a real incident or verified indicator. Scenario fingerprint {digest[:24]}.",
            "url": f"https://example.invalid/sentinelx/demo/{i:05d}",
            "source_id": source["_id"],
            "published_at": now - timedelta(minutes=i * 17),
            "classification": {"type": typ, "severity": sev},
            "iocs": [],
            "platform": PLATFORMS[i % len(PLATFORMS)],
            "status": STATUSES[i % len(STATUSES)],
            "record_origin": "synthetic_demo",
            "verification": {"status": "demo_only", "checks": ["schema_valid"], "note": "Synthetic demonstration record; not real-world threat intelligence."}
        }
        ops.append(__import__("pymongo").UpdateOne({"_id": key}, {"$setOnInsert": doc}, upsert=True))
        if len(ops) >= 1000:
            db.threats.bulk_write(ops, ordered=False); ops.clear()
    if ops: db.threats.bulk_write(ops, ordered=False)
    db.threats.create_index("url", unique=True, sparse=True)
    db.threats.create_index("classification.severity")
    db.threats.create_index("classification.type")
    db.threats.create_index("source_id")
    print(f"Threat documents: {db.threats.count_documents({})}")
    print("Synthetic demo records:", db.threats.count_documents({"record_origin":"synthetic_demo"}))
    print("Live RSS records:", db.threats.count_documents({"record_origin":"live_rss"}))

if __name__ == "__main__":
    main()
