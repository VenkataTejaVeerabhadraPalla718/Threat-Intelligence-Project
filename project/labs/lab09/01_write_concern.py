import csv, sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from pymongo.write_concern import WriteConcern
from common import db

N = 1000
rows = []
for w in (1, "majority", 3):          # 3 = all data nodes
    for j in (False, True):
        col = db.get_collection("lab9_wc", write_concern=WriteConcern(w=w, j=j))
        col.drop()
        t0 = time.perf_counter()
        for i in range(N):
            col.insert_one({"i": i, "payload": "x" * 100})
        total = time.perf_counter() - t0
        rows.append((str(w), j, round(total, 2), round(total / N * 1000, 2)))

print(f"{'w':10}{'j':8}{'total s':10}{'avg ms/write'}")
for r in rows:
    print(f"{r[0]:10}{str(r[1]):8}{r[2]:<10}{r[3]}")
with open(Path(__file__).parent / "results.csv", "w", newline="") as f:
    csv.writer(f).writerows([("w", "j", "total_s", "avg_ms")] + rows)