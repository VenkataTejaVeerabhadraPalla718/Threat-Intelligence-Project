from common import client, REQ, READ


def snapshot():
    s = client.admin.command("serverStatus")
    c = s["wiredTiger"]["cache"]
    req, read = c[REQ], c[READ]
    snap = {
        "connections": s["connections"]["current"],
        "opcounters": dict(s["opcounters"]),
        "cache_hit_ratio": round(1 - read / req, 4) if req else 1.0,
        "members": [],
        "max_lag_s": 0,
    }
    try:
        st = client.admin.command("replSetGetStatus")
        primary = next(m for m in st["members"] if m["stateStr"] == "PRIMARY")
        for m in st["members"]:
            od = m.get("optimeDate")
            lag = (primary["optimeDate"] - od).total_seconds() if od else 0
            snap["members"].append({"name": m["name"], "state": m["stateStr"], "lag_s": lag})
        snap["max_lag_s"] = max(x["lag_s"] for x in snap["members"])
    except Exception:
        pass
    return snap