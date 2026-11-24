import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

import time

from common import LIMIT, db


def stats(name):
    r = list(db[name].aggregate([
        {"$project": {"s": {"$bsonSize": "$$ROOT"}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "total": {"$sum": "$s"},
                    "avg": {"$avg": "$s"}, "min": {"$min": "$s"}, "max": {"$max": "$s"}}}]))
    return r[0]


def over(name, threshold):
    r = list(db[name].aggregate([
        {"$project": {"s": {"$bsonSize": "$$ROOT"}}},
        {"$match": {"s": {"$gt": threshold}}}, {"$count": "n"}]))
    return r[0]["n"] if r else 0


def avg_ms(fn, n=200):
    fn()
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t) / n * 1000


LOOKUP = [{"$lookup": {"from": "sources", "localField": "source_id", "foreignField": "_id", "as": "source"}},
          {"$unwind": "$source"}]

print("=== 1. RELATIONSHIPS: embedded or referenced? ===")
print("  threat -> source          REFERENCED  (threats.source_id -> sources._id)")
print("  threat -> classification  EMBEDDED    (small object inside the threat)")
print("  threat -> iocs            EMBEDDED    (array inside the threat)")
print("\n  Why source is NOT embedded in the original design:")
print("  many threats share the same few sources, so embedding would copy the same")
print("  name/url into every threat, and renaming a source would mean updating all copies.")
print("  Embedded alternative: threat.source = {name, url}  (built below as threats_embedded)")

print(f"\n=== 2. DOCUMENT SIZE with $bsonSize (limit = {LIMIT:,} bytes) ===")
for name in ["threats", "sources"]:
    s = stats(name)
    print(f"\n  {name}: {s['count']} docs")
    print(f"    average  : {s['avg']:.1f} bytes   ({s['total']:,} / {s['count']})")
    print(f"    smallest : {s['min']:,} bytes")
    print(f"    largest  : {s['max']:,} bytes = {s['max'] / LIMIT * 100:.4f}% of 16 MB")
    print(f"    docs above 16 MB: {over(name, LIMIT)} | above 50% of 16 MB: {over(name, LIMIT * 0.5)}")
    print("    RESULT:", "PASS, no document approaches 16 MB" if s["max"] < LIMIT * 0.5 else "FAIL")

print("\n=== 3. ACTIVITY: redesign threat->source as EMBEDDED ===")
db.threats_embedded.drop()
db.threats.aggregate(LOOKUP + [
    {"$project": {"source_id": 0, "source._id": 0, "source.feed_url": 0}},
    {"$out": "threats_embedded"}])
ref, emb = stats("threats"), stats("threats_embedded")
print(f"  size   : reference avg {ref['avg']:.1f} B | embedded avg {emb['avg']:.1f} B "
      f"| difference {emb['avg'] - ref['avg']:+.1f} B per document")

t_ref = avg_ms(lambda: list(db.threats.aggregate(LOOKUP + [{"$project": {"title": 1, "source.name": 1}}])))
t_emb = avg_ms(lambda: list(db.threats_embedded.find({}, {"title": 1, "source.name": 1})))
print(f"  read   : 'list threats with source name' reference {t_ref:.2f} ms (join) | "
      f"embedded {t_emb:.2f} ms (plain find) -> {t_ref / t_emb:.1f}x faster")

top = next(db.threats.aggregate([{"$group": {"_id": "$source_id", "n": {"$sum": 1}}},
                                 {"$sort": {"n": -1}}, {"$limit": 1}]))
src = db.sources.find_one({"_id": top["_id"]})
old = src["name"]
r1 = db.sources.update_one({"_id": src["_id"]}, {"$set": {"name": old + " (renamed)"}})
db.sources.update_one({"_id": src["_id"]}, {"$set": {"name": old}})
r2 = db.threats_embedded.update_many({"source.name": old}, {"$set": {"source.name": old + " (renamed)"}})
db.threats_embedded.update_many({"source.name": old + " (renamed)"}, {"$set": {"source.name": old}})
print(f"  update : rename '{old}' -> reference changes {r1.modified_count} document, "
      f"embedded changes {r2.modified_count} documents")
print("  Faster with embedding: reading a threat together with its source (no join).")
print("  Harder with embedding: renaming/fixing a source, data duplicated, documents slightly bigger.")

print("\n=== 4. GROWTH TEST: what if one threat's embedded IOC array keeps growing? ===")
base = db.threats.find_one({}, {"_id": 0})


def size_with(n):
    d = dict(base)
    d["iocs"] = [{"type": "ip", "value": f"10.{(i >> 16) & 255}.{(i >> 8) & 255}.{i & 255}",
                  "first_seen": "2026-10-06"} for i in range(n)]
    db.tmp_growth.drop()
    try:
        db.tmp_growth.insert_one(d)
        return list(db.tmp_growth.aggregate([{"$project": {"s": {"$bsonSize": "$$ROOT"}}}]))[0]["s"]
    except Exception as e:
        return type(e).__name__
    finally:
        db.tmp_growth.drop()


sizes = {}
print(f"  {'IOCs inside':>12} {'size (bytes)':>14} {'% of 16 MB':>11}")
for n in [0, 10, 100, 1_000, 10_000, 100_000, 300_000]:
    s = sizes[n] = size_with(n)
    if isinstance(s, int):
        print(f"  {n:>12,} {s:>14,} {s / LIMIT * 100:>10.2f}%")
    else:
        print(f"  {n:>12,} {'REJECTED':>14}  ({s})")
per = (sizes[10_000] - sizes[1_000]) / 9_000
print(f"\n  one more IOC costs about {per:.1f} bytes -> about {(LIMIT - sizes[0]) / per:,.0f} IOCs fill 16 MB")
mx = next(db.threats.aggregate([{"$project": {"n": {"$size": "$iocs"}}}, {"$sort": {"n": -1}}, {"$limit": 1}]))["n"]
print(f"  our largest real threat has {mx} IOCs, so the IOC array is safe today,")
print("  but an unbounded array would be a risk; bounded embedded data (classification) is fine.")