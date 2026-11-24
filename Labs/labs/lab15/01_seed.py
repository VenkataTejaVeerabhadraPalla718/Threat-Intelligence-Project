"""Idempotently seed Lab 15 tenant examples without deleting existing accounts/tasks."""
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from common import db
from saas import ensure_indexes, hash_pw

TENANTS = ["windows", "linux", "macos", "android", "ios"]


def main():
    ensure_indexes()
    now = datetime.now(timezone.utc)
    for tenant in TENANTS:
        for role in ("admin", "user"):
            username = f"{role}_{tenant}"
            db.users.update_one(
                {"username": username},
                {"$setOnInsert": {
                    "username": username,
                    "password": hash_pw("pass123"),
                    "tenant_id": tenant,
                    "role": role,
                    "active": True,
                    "created_at": now,
                    "demo_account": True,
                }},
                upsert=True,
            )
        for i in range(100):
            owner = f"admin_{tenant}" if i % 5 == 0 else f"user_{tenant}"
            db.tasks.update_one(
                {"tenant_id": tenant, "owner": owner, "title": f"Mitigate {tenant} threat #{i}"},
                {"$setOnInsert": {
                    "tenant_id": tenant,
                    "owner": owner,
                    "title": f"Mitigate {tenant} threat #{i}",
                    "status": random.choice(["open", "done"]),
                    "created_at": now - timedelta(minutes=i),
                }},
                upsert=True,
            )
    print("Lab 15 seed complete (non-destructive).")
    print("Tenants:", len(TENANTS), "| Users:", db.users.count_documents({}), "| Tasks:", db.tasks.count_documents({}))
    print("Demo credentials for lab-only accounts: pass123 (change before any shared deployment).")


if __name__ == "__main__":
    main()
