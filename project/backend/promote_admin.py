"""Promote an existing account to administrator without changing its password.
Run inside the API container: python /app/backend/promote_admin.py EXISTING_USERNAME
"""
import sys
from common import db

if len(sys.argv) != 2:
    raise SystemExit("Usage: python /app/backend/promote_admin.py EXISTING_USERNAME")
username = sys.argv[1].strip()
result = db.users.update_one({"username": username}, {"$set": {"role": "admin", "active": True}})
if not result.matched_count:
    raise SystemExit(f"User '{username}' was not found. Create/sign in with the existing Lab 15 account first.")
print(f"Administrator role assigned to existing account: {username}")
