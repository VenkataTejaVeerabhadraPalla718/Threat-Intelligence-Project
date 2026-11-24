import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

import csv
import random
import time

from common import INUSE, MAX, READ, REQ, cache, db

N = db.reports_test.estimated_document_count()
assert N == 100_000, f"reports_test has {N} documents, run 03_lab72_generate.py first"
random.seed(1)
OUT = Path(__file__).resolve().parent / "data" / "lab72_random_reads.csv"


def key(c, *needles):
    for k in c:
        if all(n in k.lower() for n in needles):
            return k


c = cache()
st = db.command("collStats", "reports_test")
data = st["size"] + st["totalIndexSize"]
mx = c[MAX]
ev_key, dirty_key = key(c, "evicted", "application"), key(c, "dirty", "bytes")
print("=== 1. WiredTiger cache (db.serverStatus) ===")
print(f"  cache size (max)     : {mx:,} bytes")
print(f"  cache in use         : {c[INUSE]:,} bytes = {c[INUSE] / mx * 100:.1f}% of max")
print(f"  data + index size    : {data:,} bytes = {data / mx * 100:.1f}% of max  (the working set if all docs are read)")
print(f"  dirty bytes          : {c[dirty_key]:,}" if dirty_key else "  dirty bytes          : field not found")
print(f"  pages evicted (app)  : {c[ev_key]:,}" if ev_key else "  eviction field       : not found")
print(f"  pages read into cache: {c[READ]:,}")

print("\n=== 2. Reading the start, middle and end of the collection (1,000 docs each) ===")
print(f"  {'part':<8} {'1st read ms':>12} {'2nd read ms':>12}")
for name, a, b in [("start", 0, 1000), ("middle", 49000, 50000), ("end", 99000, 100000)]:
    times = []
    for _ in range(2):
        t = time.perf_counter()
        n = len(list(db.reports_test.find({"seq": {"$gte": a, "$lt": b}})))
        times.append((time.perf_counter() - t) * 1000)
    print(f"  {name:<8} {times[0]:>12.1f} {times[1]:>12.1f}   ({n} docs)")

ROUNDS, READS = 10, 15_000
print(f"\n=== 3. Random reads across the whole collection ({ROUNDS} x {READS:,}) ===")
print(f"  {'rnd':>3} {'reads':>8} {'distinct%':>9} {'requests':>9} {'misses':>7} {'hit%':>7} {'cache MB':>9} {'%of max':>8} {'ms/read':>8}")
seen, rows = set(), []
for rnd in range(1, ROUNDS + 1):
    before = cache()
    t = time.perf_counter()
    for _ in range(READS):
        s = random.randrange(N)
        seen.add(s)
        assert db.reports_test.find_one({"seq": s}) is not None
    secs = time.perf_counter() - t
    after = cache()
    req, miss = after[REQ] - before[REQ], after[READ] - before[READ]
    row = {"round": rnd, "total_reads": rnd * READS, "distinct_pct": len(seen) / N * 100,
           "requests": req, "misses": miss, "hit_ratio_pct": (1 - miss / req) * 100 if req else 0.0,
           "cache_mb": after[INUSE] / 1048576, "cache_pct_of_max": after[INUSE] / mx * 100,
           "ms_per_read": secs / READS * 1000}
    rows.append(row)
    print(f"  {rnd:>3} {row['total_reads']:>8,} {row['distinct_pct']:>8.1f}% {req:>9,} {miss:>7,} "
          f"{row['hit_ratio_pct']:>6.2f}% {row['cache_mb']:>9.1f} {row['cache_pct_of_max']:>7.1f}% {row['ms_per_read']:>8.3f}")

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

c2 = cache()
print("\n  our hit ratio  = 1 - (pages read into cache / pages requested)")
if ev_key:
    print(f"  textbook-script style ratio = 1 - evicted/read = "
          f"{max(0, 1 - c2[ev_key] / c2[READ]) * 100:.1f}%  (different measure: counts evictions, not misses)")
print("  saved", OUT)