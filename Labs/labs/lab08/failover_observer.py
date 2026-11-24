import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

import time
from common import client, db # type: ignore

while True:
    try:
        n = db.threats.count_documents({})
        print(time.strftime("%H:%M:%S"), "OK   threats =", n, "| primary =", client.primary)
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "FAIL", type(e).__name__)
    time.sleep(1)