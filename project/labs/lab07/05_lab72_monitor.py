import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

import argparse
import csv
import os
import time
from datetime import datetime, timezone

from common import INUSE, MAX, READ, REQ, cache, db, fetch_readme, parse_reports

INTERVAL = 10        # seconds between cache readings
GITHUB_EVERY = 6     # check GitHub every 6 ticks = 60 s
CSV_PATH = Path(__file__).resolve().parent / "data" / "lab72_monitor.csv"
etag = None


def github_check():
    global etag
    try:
        text, etag = fetch_readme(etag)
        if text is None:
            print("  [GitHub] README unchanged since last check (HTTP 304)")
            return
        reports = parse_reports(text)
        known = {d["_id"] for d in db.annual_reports.find({}, {"_id": 1})}
        new = {u: v for u, v in reports.items() if u not in known}
        print(f"  [GitHub] README lists {len(reports)} reports | in DB {len(known)} | NEW {len(new)}")
        for u, v in list(new.items())[:5]:
            print(f"      new: {v} | {u[:80]}")
        if len(new) > 5:
            print(f"      ... and {len(new) - 5} more")
        if new:
            db.annual_reports.insert_many(
                [{"_id": u, "vendor": v, "found_at": datetime.now(timezone.utc)} for u, v in new.items()],
                ordered=False)
    except Exception as e:
        print(f"  [GitHub] check failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run until Ctrl+C)")
    ap.add_argument("--forget", type=int, default=0, help="demo: remove N reports from the DB so they show as NEW")
    args = ap.parse_args()

    if args.forget:
        ids = [d["_id"] for d in db.annual_reports.aggregate([{"$sample": {"size": args.forget}}])]
        db.annual_reports.delete_many({"_id": {"$in": ids}})
        print(f"demo: removed {len(ids)} reports from the DB")

    first = prev = cache()
    mx = first[MAX]
    print(f"monitoring every {INTERVAL}s | cache max {mx:,} bytes | Ctrl+C to stop\n")
    github_check()

    new_file = not os.path.exists(CSV_PATH)
    f = open(CSV_PATH, "a", newline="")
    w = csv.writer(f)
    if new_file:
        w.writerow(["time", "requests", "misses", "interval_hit_pct", "total_hit_pct", "cache_bytes", "cache_pct_of_max"])

    print(f"{'time':>8} {'requests':>9} {'misses':>7} {'10s hit%':>14} {'total hit%':>10} {'cache MB':>9} {'%of max':>8}")
    tick = 0
    try:
        while args.ticks == 0 or tick < args.ticks:
            time.sleep(INTERVAL)
            tick += 1
            cur = cache()
            req, miss = cur[REQ] - prev[REQ], cur[READ] - prev[READ]
            treq, tmiss = cur[REQ] - first[REQ], cur[READ] - first[READ]
            hit = (1 - miss / req) * 100 if req > 0 else None
            thit = (1 - tmiss / treq) * 100 if treq > 0 else None
            now = datetime.now().strftime("%H:%M:%S")
            print(f"{now:>8} {req:>9,} {miss:>7,} {(f'{hit:.2f}%' if hit is not None else 'n/a (no reads)'):>14} "
                  f"{(f'{thit:.2f}%' if thit is not None else 'n/a'):>10} {cur[INUSE] / 1048576:>9.1f} "
                  f"{cur[INUSE] / mx * 100:>7.1f}%")
            w.writerow([now, req, miss, f"{hit:.2f}" if hit is not None else "",
                        f"{thit:.2f}" if thit is not None else "", cur[INUSE], f"{cur[INUSE] / mx * 100:.1f}"])
            f.flush()
            prev = cur
            if tick % GITHUB_EVERY == 0:
                github_check()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        f.close()