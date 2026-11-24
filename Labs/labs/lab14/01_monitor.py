import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
import argparse, os, sys, time
from datetime import datetime
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
import requests
from monitor import snapshot

LOG = Path(__file__).parent / "metrics.log"
WEBHOOK = os.getenv("WEBHOOK_URL")   # Slack or Discord webhook (optional)

ap = argparse.ArgumentParser()
ap.add_argument("--interval", type=int, default=30)
ap.add_argument("--cache-min", type=float, default=0.80)
ap.add_argument("--lag-max", type=float, default=10)
ap.add_argument("--once", action="store_true")
a = ap.parse_args()


def table(s):
    ops = " ".join(f"{k}={v}" for k, v in s["opcounters"].items() if k in ("insert", "query", "update", "delete"))
    lines = [f"--- {datetime.now():%Y-%m-%d %H:%M:%S} ---",
             f"{'connections':<22}{s['connections']}",
             f"{'cache hit ratio':<22}{s['cache_hit_ratio']:.2%}",
             f"{'opcounters':<22}{ops}"]
    lines += [f"{m['name']:<22}{m['state']:<11}lag={m['lag_s']:.0f}s" for m in s["members"]]
    return "\n".join(lines)


def alerts(s):
    out = []
    if s["cache_hit_ratio"] < a.cache_min:
        out.append(f"cache hit ratio {s['cache_hit_ratio']:.2%} is below {a.cache_min:.0%}")
    if s["max_lag_s"] > a.lag_max:
        out.append(f"replication lag {s['max_lag_s']:.0f}s is above {a.lag_max:.0f}s")
    return out


while True:
    s = snapshot()
    text = table(s)
    for msg in alerts(s):
        text += f"\nWARNING: {msg}"
        if WEBHOOK:
            try:
                requests.post(WEBHOOK, json={"text": msg, "content": msg}, timeout=5)
            except requests.RequestException as e:
                text += f"\n(webhook failed: {type(e).__name__})"
    print(text)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    if a.once:
        break
    time.sleep(a.interval)