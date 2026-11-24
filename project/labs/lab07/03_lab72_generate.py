import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

import random
import time

import bson
from bson import ObjectId
from pymongo import ASCENDING

from common import INUSE, MAX, cache, db, fetch_readme, parse_reports

N = 100_000
TARGET = 2048        # bytes per document (BSON)
BATCH = 1000
random.seed(7)

CATEGORIES = ["Threat Landscape", "Incident Response", "Vulnerability", "Cloud Security", "Ransomware", "Identity"]
WORDS = ("attack threat actor malware phishing exploit patch breach credential endpoint network cloud "
         "ransomware vulnerability campaign indicator defense detection response intrusion payload "
         "lateral movement supply chain identity access report trend analysis").split()


def filler(n):
    out, length = [], 0
    while length < n:
        w = random.choice(WORDS)
        out.append(w)
        length += len(w) + 1
    return " ".join(out)[:n].ljust(n, "x")


def load_reports():
    try:
        text, _ = fetch_readme()
        items = list(parse_reports(text).items())
        if items:
            print(f"loaded {len(items)} real report entries from the GitHub list")
            return [(v[:60], u[:300]) for u, v in items]
    except Exception as e:
        print("GitHub list not available, using generic vendor names:", e)
    return [(f"Vendor-{i:02d}", f"https://example.com/report-{i}") for i in range(50)]


REPORTS = load_reports()


def make_doc(i):
    vendor, url = REPORTS[i % len(REPORTS)]
    year = random.randint(2018, 2026)
    doc = {
        "_id": ObjectId(), "seq": i, "vendor": vendor, "report_url": url,
        "title": f"{vendor} annual security report entry #{i}",
        "year": year, "category": random.choice(CATEGORIES),
        "note": "vendor/url from awesome-annual-security-reports; padding is synthetic filler",
        "padding": "",
    }
    doc["padding"] = filler(TARGET - len(bson.encode(doc)))
    return doc


if __name__ == "__main__":
    db.reports_test.drop()
    for k in range(20):
        assert len(bson.encode(make_doc(k))) == TARGET, "document is not exactly 2048 bytes"

    t0 = time.perf_counter()
    batch = []
    for i in range(N):
        batch.append(make_doc(i))
        if len(batch) == BATCH:
            db.reports_test.insert_many(batch, ordered=False)
            batch = []
    if batch:
        db.reports_test.insert_many(batch, ordered=False)
    db.reports_test.create_index([("seq", ASCENDING)], unique=True)
    print(f"inserted + indexed in {time.perf_counter() - t0:.1f} s\n")

    s = list(db.reports_test.aggregate([
        {"$project": {"s": {"$bsonSize": "$$ROOT"}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "total": {"$sum": "$s"},
                    "avg": {"$avg": "$s"}, "min": {"$min": "$s"}, "max": {"$max": "$s"}}}]))[0]
    print(f"count {s['count']:,} | avg {s['avg']:.1f} | min {s['min']} | max {s['max']} | total {s['total']:,} bytes")

    st = db.command("collStats", "reports_test")
    print(f"dataSize {st['size']:,} | on disk (compressed) {st['storageSize']:,} | indexes {st['totalIndexSize']:,}")
    c = cache()
    print(f"cache: {c[INUSE]:,} of {c[MAX]:,} bytes ({c[INUSE] / c[MAX] * 100:.1f}%)")
    print(f"data+index = {(st['size'] + st['totalIndexSize']) / c[MAX] * 100:.1f}% of the cache limit")