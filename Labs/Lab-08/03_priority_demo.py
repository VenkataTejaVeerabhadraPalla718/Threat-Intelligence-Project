import sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from common import client

PRIORITY = {"mongo1:27117": 1, "mongo2:27118": 5, "mongo3:27119": 3}
print("PREDICTION 1: mongo2 becomes primary (priority 5)")
conf = client.admin.command("replSetGetConfig")["config"]
for m in conf["members"]:
    if m["host"] in PRIORITY:
        m["priority"] = PRIORITY[m["host"]]
conf["version"] += 1
try:
    client.admin.command("replSetReconfig", conf)
except Exception as e:
    print("(reconfig closed the connection:", type(e).__name__, ")")
time.sleep(15)
print("ACTUAL 1:", client.primary)

print("PREDICTION 2: after stepDown, mongo3 wins (priority 3, mongo2 blocked 60s)")
try:
    client.admin.command("replSetStepDown", 60)
except Exception as e:
    print("(stepDown closed the connection:", type(e).__name__, ")")
time.sleep(15)
print("ACTUAL 2:", client.primary)