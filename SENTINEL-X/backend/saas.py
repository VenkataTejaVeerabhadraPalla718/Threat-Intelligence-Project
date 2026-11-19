"""Authentication, RBAC, login auditing and administration for SENTINEL-X."""
import csv
import io
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

import config
from common import db
from security_utils import (check_pw, csv_safe, hash_pw, is_locked_out, parse_day,  # noqa: F401
                            validate_password, validate_username, verify_pw)

log = logging.getLogger("sentinelx.auth")

SECRET = os.getenv("JWT_SECRET")
if not SECRET or SECRET == "dev-secret-change-me" or len(SECRET.encode("utf-8")) < 32:
    raise RuntimeError("Set JWT_SECRET to a unique random value of at least 32 bytes.")
RATE_LIMIT = config.RATE_LIMIT_PER_MINUTE
router = APIRouter(prefix="/api")
ROLES = ("user", "analyst", "professor", "admin")


def ensure_indexes(retries: int = 15, delay: float = 2.0):
    """Create indexes, retrying while MongoDB finishes electing a primary."""
    last = None
    for attempt in range(1, retries + 1):
        try:
            db.tasks.create_index([("tenant_id", 1), ("created_at", -1)])
            db.users.create_index("username", unique=True)
            db.users.create_index("role")
            db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
            db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
            db.login_activity.create_index([("created_at", -1)])
            db.login_activity.create_index([("username", 1), ("created_at", -1)])
            db.login_activity.create_index([("success", 1), ("created_at", -1)])
            db.login_activity.create_index([("ip_address", 1), ("created_at", -1)])
            return
        except PyMongoError as exc:
            last = exc
            log.warning("MongoDB not ready for index creation (attempt %s/%s): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Could not create indexes after {retries} attempts: {last}")


ensure_indexes()


# ------------------------------------------------------------------ models
class Login(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    requested_role: str = "user"


class TaskIn(BaseModel):
    title: str
    threat_url: str = ""
    status: str = "open"


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserRoleUpdate(BaseModel):
    role: str
    active: bool = True


class UserPermissionUpdate(BaseModel):
    labs: list[int] = []
    assistant: bool = False
    can_run_labs: bool = False


# ------------------------------------------------------------------ audit
def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _correlation_id(request: Request) -> str:
    raw = request.headers.get("x-request-id", "")
    return re.sub(r"[^A-Za-z0-9_.-]", "", raw)[:64] or uuid.uuid4().hex


def record_login_event(username: str, success: bool, request: Request, reason: str = "",
                       event_type: str = "login", user: dict | None = None, session_id: str | None = None):
    """Persist an authentication event. Never blocks authentication if audit storage fails."""
    try:
        db.login_activity.insert_one({
            "event_type": event_type,
            "username": (username or "")[:80],
            "user_id": str(user["_id"]) if user and user.get("_id") else None,
            "role": (user or {}).get("role"),
            "success": bool(success),
            "reason": reason[:120],
            "ip_address": _client_ip(request),
            "user_agent": request.headers.get("user-agent", "")[:300],
            "correlation_id": _correlation_id(request),
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        log.exception("Failed to write login audit event")


def _recent_failures(username: str, ip: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
    try:
        return db.login_activity.count_documents({
            "username": username, "ip_address": ip, "success": False,
            "event_type": "login", "reason": {"$ne": "locked_out"}, "created_at": {"$gte": since}})
    except PyMongoError:
        return 0


# ------------------------------------------------------------------ auth
@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request):
    try:
        username = validate_username(body.username)
        validate_password(body.password, username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if db.users.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
        raise HTTPException(409, "Username already exists.")
    requested = body.requested_role if body.requested_role in ("user", "analyst", "professor") else "user"
    # Self-registration never grants privileged role or data access. Requested role is reviewed by an admin.
    doc = {"username": username, "password": hash_pw(body.password), "tenant_id": "sentinelx",
           "role": "user", "requested_role": requested, "permissions": {"labs": [], "assistant": False, "can_run_labs": False},
           "active": True, "approval_status": "pending", "created_at": datetime.now(timezone.utc),
           "registered_via": "self-service"}
    try:
        res = db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Username already exists.")
    record_login_event(username, True, request, "self-registration", "registration", {**doc, "_id": res.inserted_id})
    return {"ok": True, "username": username, "role": "user", "approval_status": "pending",
            "message": "Registration received. An administrator must approve your role and access before use."}


_DUMMY_HASH = None


def _dummy_verify(password: str):
    """Equalise timing for unknown usernames to blunt account enumeration."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_pw(uuid.uuid4().hex)
    verify_pw(password, _DUMMY_HASH)


@router.post("/auth/login")
def login(body: Login, request: Request):
    username = body.username.strip()[:80]
    ip = _client_ip(request)
    if is_locked_out(_recent_failures(username, ip), config.LOGIN_MAX_FAILURES):
        record_login_event(username, False, request, "locked_out")
        raise HTTPException(429, f"Too many failed attempts. Try again in {config.LOGIN_LOCKOUT_MINUTES} minutes.")
    u = db.users.find_one({"username": username})
    if not u:
        _dummy_verify(body.password)
        record_login_event(username, False, request, "unknown_user")
        raise HTTPException(401, "Invalid username or password.")
    ok, needs_rehash = verify_pw(body.password, u.get("password", ""))
    if not ok:
        record_login_event(username, False, request, "wrong_password", user=u)
        raise HTTPException(401, "Invalid username or password.")
    if not u.get("active", True):
        record_login_event(username, False, request, "account_disabled", user=u)
        raise HTTPException(403, "This account is disabled. Contact an administrator.")
    if needs_rehash:
        db.users.update_one({"_id": u["_id"]}, {"$set": {"password": hash_pw(body.password)}})
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    token = jwt.encode({"sub": u["username"], "uid": str(u["_id"]), "tenant": u["tenant_id"],
                        "role": u.get("role", "user"), "jti": jti, "iat": now,
                        "exp": now + timedelta(minutes=config.JWT_EXPIRE_MINUTES)},
                       SECRET, algorithm="HS256")
    record_login_event(u["username"], True, request, "login", user=u, session_id=jti)
    db.users.update_one({"_id": u["_id"]}, {"$set": {"last_login_at": now}})
    return {"access_token": token, "token_type": "bearer", "username": u["username"],
            "role": u.get("role", "user"), "expires_in": config.JWT_EXPIRE_MINUTES * 60}


def _decode(authorization: str) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Authentication required.")
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token.")


def current_user(authorization: str = Header("")):
    data = _decode(authorization)
    if data.get("jti") and db.revoked_tokens.find_one({"_id": data["jti"]}):
        raise HTTPException(401, "Session ended. Please sign in again.")
    account = db.users.find_one({"username": data["sub"], "tenant_id": data["tenant"]})
    if not account or not account.get("active", True):
        raise HTTPException(401, "Account is unavailable.")
    data["role"] = account.get("role", "user")  # role always comes from the database, never the token
    data["permissions"] = account.get("permissions", {"labs": [], "assistant": False, "can_run_labs": False})
    data["approval_status"] = account.get("approval_status", "approved")
    if data["approval_status"] == "pending" and data["role"] != "admin":
        raise HTTPException(403, "Your account is awaiting administrator approval.")
    data["uid"] = str(account["_id"])
    key = f"{data['sub']}:{int(time.time() // 60)}"
    r = db.rate_limits.find_one_and_update(
        {"_id": key},
        {"$inc": {"n": 1}, "$setOnInsert": {"expires_at": datetime.now(timezone.utc) + timedelta(minutes=2)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if r["n"] > RATE_LIMIT:
        raise HTTPException(429, "Rate limit exceeded.")
    return data


def require_admin(user=Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator permission required.")
    return user


def can_view_lab(user: dict, lab: int) -> bool:
    role = user.get("role")
    if role == "admin" or role == "professor":
        return True
    return int(lab) in set(user.get("permissions", {}).get("labs", []))

def require_lab_view(user: dict, lab: int):
    if not can_view_lab(user, lab):
        raise HTTPException(403, f"Access to Lab {lab} has not been granted by an administrator.")
    return user

def require_lab_run(user: dict, lab: int):
    if user.get("role") == "admin":
        return user
    if user.get("role") == "professor":
        raise HTTPException(403, "Professor accounts have read-only access to lab outputs.")
    perms = user.get("permissions", {})
    if not perms.get("can_run_labs") or int(lab) not in set(perms.get("labs", [])):
        raise HTTPException(403, f"Run permission for Lab {lab} has not been granted.")
    return user

def require_assistant_access(user: dict):
    if user.get("role") == "admin" or user.get("role") == "professor" or user.get("permissions", {}).get("assistant"):
        return user
    raise HTTPException(403, "Boss AI Assistant access has not been granted by an administrator.")


@router.post("/auth/logout")
def logout(request: Request, authorization: str = Header("")):
    data = _decode(authorization)
    if data.get("jti"):
        db.revoked_tokens.update_one({"_id": data["jti"]},
                                     {"$set": {"expires_at": datetime.fromtimestamp(data["exp"], timezone.utc)}},
                                     upsert=True)
    record_login_event(data["sub"], True, request, "logout", "logout", session_id=data.get("jti"))
    return {"ok": True}


@router.get("/auth/me")
def auth_me(user=Depends(current_user)):
    return {"username": user["sub"], "user_id": user["uid"], "tenant": user["tenant"],
            "role": user.get("role", "user"), "permissions": user.get("permissions", {}),
            "approval_status": user.get("approval_status", "approved")}


# ------------------------------------------------------------------ tasks (Lab 15)
def scope(user):
    q = {"tenant_id": user["tenant"]}          # tenant isolation on EVERY query
    if user["role"] != "admin":
        q["owner"] = user["sub"]               # RBAC: normal users see only their own
    return q


def oid(x):
    try:
        return ObjectId(x)
    except Exception:
        raise HTTPException(404, "not found")


@router.post("/tasks")
def create_task(t: TaskIn, user=Depends(current_user)):
    doc = {**t.model_dump(), "tenant_id": user["tenant"], "owner": user["sub"],
           "created_at": datetime.now(timezone.utc)}
    return {"id": str(db.tasks.insert_one(doc).inserted_id)}


@router.get("/tasks")
def list_tasks(user=Depends(current_user)):
    cur = db.tasks.find(scope(user)).sort("created_at", -1).limit(100)
    return [{**{k: v for k, v in t.items() if k != "_id"}, "id": str(t["_id"])} for t in cur]


@router.put("/tasks/{task_id}")
def update_task(task_id: str, t: TaskIn, user=Depends(current_user)):
    r = db.tasks.update_one({**scope(user), "_id": oid(task_id)}, {"$set": t.model_dump()})
    if r.matched_count == 0:
        raise HTTPException(404, "not found")
    return {"ok": True}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, user=Depends(current_user)):
    r = db.tasks.delete_one({**scope(user), "_id": oid(task_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "not found")
    return {"ok": True}


# ------------------------------------------------------------------ administration
def _public_user(x: dict, last_login=None) -> dict:
    return {"id": str(x["_id"]), "username": x["username"], "role": x.get("role", "user"),
            "active": x.get("active", True), "created_at": x.get("created_at"),
            "registered_via": x.get("registered_via", "admin" if x.get("created_by") else "legacy"),
            "requested_role": x.get("requested_role", x.get("role", "user")),
            "approval_status": x.get("approval_status", "approved" if x.get("role") == "admin" else "pending"),
            "permissions": x.get("permissions", {"labs": [], "assistant": False, "can_run_labs": False}),
            "last_login_at": last_login or x.get("last_login_at")}


def _active_admin_count(exclude: str | None = None) -> int:
    q = {"role": "admin", "active": {"$ne": False}}
    if exclude:
        q["username"] = {"$ne": exclude}
    return db.users.count_documents(q)


@router.get("/admin/summary")
def admin_summary(user=Depends(require_admin)):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    return {
        "users_total": db.users.count_documents({}),
        "users_active": db.users.count_documents({"active": {"$ne": False}}),
        "users_disabled": db.users.count_documents({"active": False}),
        "admins": db.users.count_documents({"role": "admin"}),
        "logins_success_total": db.login_activity.count_documents({"success": True, "reason": "login"}),
        "logins_failed_total": db.login_activity.count_documents({"success": False}),
        "logins_success_24h": db.login_activity.count_documents({"success": True, "reason": "login", "created_at": {"$gte": since}}),
        "logins_failed_24h": db.login_activity.count_documents({"success": False, "created_at": {"$gte": since}}),
    }


@router.get("/admin/users")
def admin_list_users(search: str = "", role: str = "", status: str = "",
                     skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                     user=Depends(require_admin)):
    q = {"tenant_id": user["tenant"]}
    if search:
        q["username"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    if role in ROLES:
        q["role"] = role
    if status == "active":
        q["active"] = {"$ne": False}
    elif status == "disabled":
        q["active"] = False
    total = db.users.count_documents(q)
    rows = list(db.users.find(q, {"password": 0}).sort("created_at", -1).skip(skip).limit(limit))
    last = {r["_id"]: r["last"] for r in db.login_activity.aggregate([
        {"$match": {"username": {"$in": [x["username"] for x in rows]}, "success": True, "reason": "login"}},
        {"$group": {"_id": "$username", "last": {"$max": "$created_at"}}}])}
    return {"total": total, "results": [_public_user(x, last.get(x["username"])) for x in rows]}


@router.get("/admin/users/{username}")
def admin_user_detail(username: str, user=Depends(require_admin)):
    x = db.users.find_one({"username": username, "tenant_id": user["tenant"]}, {"password": 0})
    if not x:
        raise HTTPException(404, "User not found.")
    events = list(db.login_activity.find({"username": username}, {"_id": 0}).sort("created_at", -1).limit(10))
    return {**_public_user(x), "tenant": x.get("tenant_id"), "recent_events": events,
            "failed_logins_total": db.login_activity.count_documents({"username": username, "success": False})}


@router.post("/admin/users", status_code=201)
def admin_create_user(body: UserCreate, user=Depends(require_admin)):
    try:
        username = validate_username(body.username)
        validate_password(body.password, username)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if body.role not in ROLES:
        raise HTTPException(400, "Role must be user, analyst, professor or admin.")
    if db.users.find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}):
        raise HTTPException(409, "Username already exists.")
    try:
        db.users.insert_one({"username": username, "password": hash_pw(body.password),
                             "tenant_id": user["tenant"], "role": body.role, "active": True, "approval_status": "approved",
                             "permissions": {"labs": list(range(1,19)) if body.role in ("admin","professor") else [], "assistant": body.role in ("admin","professor"), "can_run_labs": body.role == "admin"},
                             "created_at": datetime.now(timezone.utc), "created_by": user["sub"],
                             "registered_via": "admin"})
    except DuplicateKeyError:
        raise HTTPException(409, "Username already exists.")
    return {"ok": True, "username": username, "role": body.role}


@router.patch("/admin/users/{username}")
def admin_update_user(username: str, body: UserRoleUpdate, user=Depends(require_admin)):
    if body.role not in ROLES:
        raise HTTPException(400, "Role must be user, analyst, professor or admin.")
    if username == user["sub"] and (body.role != "admin" or not body.active):
        raise HTTPException(400, "You cannot remove your own administrator access or disable yourself.")
    target = db.users.find_one({"username": username, "tenant_id": user["tenant"]})
    if not target:
        raise HTTPException(404, "User not found.")
    if target.get("role") == "admin" and (body.role != "admin" or not body.active) and _active_admin_count(username) < 1:
        raise HTTPException(400, "At least one active administrator must remain.")
    db.users.update_one({"_id": target["_id"]}, {"$set": {"role": body.role, "active": body.active,
        "approval_status": "approved" if body.active else "disabled"}})
    return {"ok": True}


@router.delete("/admin/users/{username}")
def admin_delete_user(username: str, user=Depends(require_admin)):
    if username == user["sub"]:
        raise HTTPException(400, "You cannot delete your own account.")
    target = db.users.find_one({"username": username, "tenant_id": user["tenant"]})
    if not target:
        raise HTTPException(404, "User not found.")
    if target.get("role") == "admin" and _active_admin_count(username) < 1:
        raise HTTPException(400, "At least one active administrator must remain.")
    db.users.delete_one({"_id": target["_id"]})
    return {"ok": True}


@router.get("/admin/access-requests")
def admin_access_requests(user=Depends(require_admin)):
    rows = list(db.users.find({"approval_status": "pending"}, {"password": 0}).sort("created_at", -1).limit(500))
    return {"results": [_public_user(x) for x in rows]}

@router.put("/admin/users/{username}/permissions")
def admin_set_permissions(username: str, body: UserPermissionUpdate, user=Depends(require_admin)):
    target = db.users.find_one({"username": username, "tenant_id": user["tenant"]})
    if not target:
        raise HTTPException(404, "User not found.")
    labs = sorted(set(int(x) for x in body.labs if 1 <= int(x) <= 18))
    if target.get("role") in ("admin", "professor"):
        raise HTTPException(400, "Admin and professor access is role-defined; per-user grants are for users and analysts.")
    permissions = {"labs": labs, "assistant": bool(body.assistant), "can_run_labs": bool(body.can_run_labs)}
    db.users.update_one({"_id": target["_id"]}, {"$set": {"permissions": permissions, "approval_status": "approved"}})
    return {"ok": True, "username": username, "permissions": permissions}

def _activity_query(username, q, success, event_type, date_from, date_to) -> dict:
    query: dict = {}
    if username:
        query["username"] = username
    elif q:
        query["username"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    if success in ("true", "false"):
        query["success"] = success == "true"
    if event_type:
        query["event_type"] = event_type
    try:
        start, end = parse_day(date_from), parse_day(date_to, end_of_day=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if start or end:
        query["created_at"] = {k: v for k, v in (("$gte", start), ("$lte", end)) if v}
    return query


@router.get("/admin/login-activity")
def admin_login_activity(q: str = "", username: str = "", success: str = "", event_type: str = "",
                         date_from: str = "", date_to: str = "",
                         skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
                         user=Depends(require_admin)):
    query = _activity_query(username, q, success, event_type, date_from, date_to)
    rows = list(db.login_activity.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit))
    return {"total": db.login_activity.count_documents(query), "results": rows}


AUDIT_COLUMNS = ["created_at", "event_type", "username", "user_id", "role", "success", "reason",
                 "ip_address", "user_agent", "correlation_id", "session_id"]


@router.get("/admin/login-activity.csv")
def admin_login_activity_csv(q: str = "", username: str = "", success: str = "", event_type: str = "",
                             date_from: str = "", date_to: str = "", user=Depends(require_admin)):
    query = _activity_query(username, q, success, event_type, date_from, date_to)

    def stream():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(AUDIT_COLUMNS)
        yield buf.getvalue(); buf.seek(0); buf.truncate()
        for x in db.login_activity.find(query, {"_id": 0}).sort("created_at", -1).limit(100000):
            w.writerow([csv_safe(x.get(c)) for c in AUDIT_COLUMNS])
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    return StreamingResponse(stream(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=sentinelx-login-activity.csv"})


@router.get("/admin/security")
def admin_security(user=Depends(require_admin)):
    now = datetime.now(timezone.utc)
    hour, day = now - timedelta(hours=1), now - timedelta(hours=24)
    failed_hour = {"success": False, "event_type": {"$ne": "registration"}, "created_at": {"$gte": hour}}
    repeated = [{"username": r["_id"]["u"], "ip_address": r["_id"]["ip"], "failures": r["n"], "last": r["last"]}
                for r in db.login_activity.aggregate([
                    {"$match": failed_hour},
                    {"$group": {"_id": {"u": "$username", "ip": "$ip_address"}, "n": {"$sum": 1}, "last": {"$max": "$created_at"}}},
                    {"$match": {"n": {"$gte": config.ALERT_FAILURE_THRESHOLD}}},
                    {"$sort": {"n": -1}}, {"$limit": 20}])]
    spraying = [{"ip_address": r["_id"], "distinct_usernames": len(r["names"]), "failures": r["n"]}
                for r in db.login_activity.aggregate([
                    {"$match": failed_hour},
                    {"$group": {"_id": "$ip_address", "names": {"$addToSet": "$username"}, "n": {"$sum": 1}}},
                    {"$match": {"$expr": {"$gte": [{"$size": "$names"}, 3]}}},
                    {"$sort": {"n": -1}}, {"$limit": 20}])]
    disabled = [x["username"] for x in db.users.find({"active": False}, {"username": 1}).limit(50)]
    return {
        "window": "failures evaluated over the last 60 minutes",
        "failed_logins_24h": db.login_activity.count_documents({**failed_hour, "created_at": {"$gte": day}}),
        "lockouts_24h": db.login_activity.count_documents({"reason": "locked_out", "created_at": {"$gte": day}}),
        "repeated_failures": repeated,
        "possible_password_spraying": spraying,
        "disabled_accounts": disabled,
        "thresholds": {"repeated_failures": config.ALERT_FAILURE_THRESHOLD,
                       "lockout_after": config.LOGIN_MAX_FAILURES,
                       "lockout_minutes": config.LOGIN_LOCKOUT_MINUTES},
    }
