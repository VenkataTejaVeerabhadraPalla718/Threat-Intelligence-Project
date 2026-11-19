"""Lab 13: bounded authenticated replica-set failover observer."""
import argparse, os, time
from pymongo import MongoClient
from pymongo.errors import PyMongoError

p = argparse.ArgumentParser()
p.add_argument("--seconds", type=int, default=20)
p.add_argument("--interval", type=float, default=1.0)
a = p.parse_args()
URI = os.getenv("KEYFILE_MONGO_URI",
    "mongodb://admin:admin123@prod1:27317,prod2:27318,prod3:27319/?replicaSet=rs1&authSource=admin")
client = MongoClient(URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                     retryWrites=True, appname="SENTINELX-Lab13")
deadline = time.monotonic() + max(1, min(a.seconds, 300))
success = failures = 0
try:
    client.admin.command("ping")
    print("Authenticated connection established.", flush=True)
    while time.monotonic() < deadline:
        try:
            client.cti.failover_test.insert_one({"ts": time.time(), "source": "lab13"})
            print(time.strftime("%H:%M:%S"), "WRITE OK | primary =", client.primary, flush=True)
            success += 1
        except PyMongoError as exc:
            print(time.strftime("%H:%M:%S"), "WRITE RETRY/FAIL:", type(exc).__name__, str(exc)[:180], flush=True)
            failures += 1
        time.sleep(max(.2, a.interval))
finally:
    client.close()
print(f"Lab 13 completed: {success} successful writes, {failures} transient failures.", flush=True)
if not success:
    raise SystemExit("No authenticated writes succeeded. Check that the Lab 13 keyfile replica set is initialized.")
