"""Lab 14.2: isolated collection backup/restore verification using BSON snapshots.
Runs inside the API container without requiring Docker CLI or Docker socket access."""
import argparse, os, shutil, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from bson import BSON
from bson.json_util import dumps, loads
from pymongo import MongoClient
from pymongo.errors import PyMongoError

ROOT = Path(__file__).resolve().parents[2]
BACKUPS = ROOT / "labs" / "lab14" / "backups"
BACKUPS.mkdir(parents=True, exist_ok=True)
URI = os.getenv("MONGO_URI", "mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0")
DB_NAME = os.getenv("LAB14_DB", "cti")
COLL = os.getenv("LAB14_COLLECTION", "backup_test")
client = MongoClient(URI, serverSelectionTimeoutMS=8000)
col = client[DB_NAME][COLL]

def snapshot():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = BACKUPS / stamp
    folder.mkdir(parents=True, exist_ok=True)
    docs = list(col.find({}))
    payload = b"".join(BSON.encode(d) for d in docs)
    (folder / f"{COLL}.bson").write_bytes(payload)
    (folder / "manifest.json").write_text(dumps({"database": DB_NAME, "collection": COLL,
        "documents": len(docs), "created_at": datetime.now(timezone.utc)}), encoding="utf-8")
    return stamp, len(docs), folder

def restore(stamp):
    folder = BACKUPS / stamp
    raw = (folder / f"{COLL}.bson").read_bytes()
    docs, pos = [], 0
    while pos < len(raw):
        size = int.from_bytes(raw[pos:pos+4], "little")
        docs.append(BSON(raw[pos:pos+size]).decode()); pos += size
    col.delete_many({})
    if docs: col.insert_many(docs, ordered=False)
    return len(docs)

def retention(days=7):
    cutoff = time.time() - days * 86400
    for folder in BACKUPS.iterdir():
        if folder.is_dir() and folder.stat().st_mtime < cutoff: shutil.rmtree(folder)

def verify(n=1000):
    col.delete_many({})
    col.insert_many([{"i": i, "verified": False, "payload": "sentinelx-backup-check"} for i in range(n)])
    before = list(col.find({}).sort("i", 1))
    stamp, count, folder = snapshot()
    col.update_many({}, {"$set": {"verified": True}})
    restored = restore(stamp)
    after = list(col.find({}).sort("i", 1))
    ok = before == after
    print(f"Backup file: {folder / (COLL + '.bson')}", flush=True)
    print(f"Snapshot documents: {count}; restored: {restored}; identical: {ok}", flush=True)
    if not ok: raise SystemExit("RESTORE VERIFICATION FAILED")
    retention()
    print("LAB 14.2 PASSED", flush=True)

def benchmark():
    print(f"{'docs':>10} {'backup_s':>10} {'restore_s':>10}", flush=True)
    for n in (1000, 10000, 100000):
        col.delete_many({})
        for start in range(0, n, 5000):
            col.insert_many([{"i": i, "payload": "x"*100} for i in range(start, min(start+5000,n))])
        t = time.perf_counter(); stamp, count, _ = snapshot(); b = time.perf_counter()-t
        t = time.perf_counter(); r = restore(stamp); rs = time.perf_counter()-t
        print(f"{count:>10} {b:>10.3f} {rs:>10.3f}", flush=True)
    print("RPO = configured backup interval; RTO = measured restore duration.", flush=True)

parser=argparse.ArgumentParser()
parser.add_argument("mode", choices=["verify","benchmark","hourly"])
mode=parser.parse_args().mode
try:
    client.admin.command("ping")
    if mode=="verify": verify()
    elif mode=="benchmark": benchmark()
    else:
        while True:
            stamp,count,_=snapshot(); print(f"Backup {stamp}: {count} docs", flush=True)
            retention(); time.sleep(3600)
finally:
    client.close()
