import subprocess, sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern

URI = "mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0"
NET = "replica-set_default"
client = MongoClient(URI, serverSelectionTimeoutMS=6000)


def try_insert(w):
    col = client.cti.get_collection("lab9_partition", write_concern=WriteConcern(w=w, wtimeout=5000))
    t0 = time.time()
    try:
        col.insert_one({"t": t0})
        print(f"   w={w!s:9} OK      {time.time() - t0:.1f}s")
    except Exception as e:
        print(f"   w={w!s:9} FAILED  {time.time() - t0:.1f}s  {type(e).__name__}")


def net(action, node):
    subprocess.run(["docker", "network", action, NET, node], check=True, capture_output=True)


deadline = time.monotonic() + 10
primary = client.primary
while primary is None and time.monotonic() < deadline:
    client.admin.command("ping")
    time.sleep(0.2)
    primary = client.primary
if primary is None:
    raise RuntimeError("Replica set has no discoverable primary.")
primary = primary[0]
secs = [n for n in ("mongo1", "mongo2", "mongo3") if n != primary]
print("primary:", primary, "| isolating:", secs)

print("\n1) cut", secs[0], "(majority still alive)")
net("disconnect", secs[0]); time.sleep(5)
try_insert(1); try_insert("majority")

print("\n2) cut", secs[1], "too (only the primary is left)")
net("disconnect", secs[1]); time.sleep(3)
try_insert(1); try_insert("majority")
print("   waiting 15s for the primary to step down...")
time.sleep(15)
try_insert(1)

print("\n3) reconnect both")
for n in secs:
    net("connect", n)
time.sleep(20)
print("primary now:", client.primary)