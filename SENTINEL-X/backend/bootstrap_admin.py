"""Create the first SENTINEL-X administrator or promote an existing account.

Run interactively inside the API container. Password input is not echoed.
"""
from datetime import datetime, timezone
from getpass import getpass

from common import db
from security_utils import hash_pw, validate_password, validate_username


def main():
    print("SENTINEL-X administrator setup")
    try:
        username = validate_username(input("Administrator username: "))
    except ValueError as exc:
        raise SystemExit(str(exc))

    existing = db.users.find_one({"username": username})
    if existing:
        db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": "admin", "active": True}})
        print(f"Existing account '{username}' promoted to admin. Password unchanged.")
        return

    password = getpass("New administrator password (minimum 12 characters): ")
    confirm = getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    try:
        validate_password(password, username)
    except ValueError as exc:
        raise SystemExit(str(exc))
    tenant = input("Tenant [sentinelx]: ").strip() or "sentinelx"
    db.users.insert_one({
        "username": username,
        "password": hash_pw(password),
        "tenant_id": tenant,
        "role": "admin",
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "registered_via": "bootstrap",
    })
    print(f"Administrator '{username}' created in tenant '{tenant}'.")
    print("Sign in using POST /api/auth/login. Keep this password private.")


if __name__ == "__main__":
    main()
