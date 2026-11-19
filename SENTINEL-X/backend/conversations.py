"""Saved conversations for Boss, the SENTINEL-X assistant (ChatGPT-style chat history).

Every conversation belongs to exactly one user (and tenant). Messages are the existing
``assistant_history`` rows, now tagged with a ``conversation_id``, so nothing about how answers are
produced changes. Older rows without a conversation are adopted into "Earlier chat" conversations
automatically the first time the list is opened.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from common import db
from saas import current_user

log = logging.getLogger("sentinelx.conversations")
router = APIRouter(prefix="/api/conversations", tags=["conversations"])

DEFAULT_TITLE = "New chat"
_indexed = False


class ConversationPatch(BaseModel):
    title: str | None = None
    pinned: bool | None = None


# ----------------------------------------------------------------- helpers
def _now():
    return datetime.now(timezone.utc)


def ensure_indexes():
    """Create indexes once; never fatal (the database may still be starting)."""
    global _indexed
    if _indexed:
        return
    try:
        db.assistant_conversations.create_index([("username", 1), ("updated_at", -1)])
        db.assistant_history.create_index([("conversation_id", 1), ("created_at", 1)])
        _indexed = True
    except Exception as exc:  # pragma: no cover - depends on a live database
        log.warning("conversation indexes not created yet: %s", type(exc).__name__)


def make_title(message: str) -> str:
    """Short chat title taken from the first message (without a leading 'Hey Boss,')."""
    text = re.sub(r"^\s*(?:(?:hey|hi|hello|ok|okay|yo)\s+)?boss\b[\s,:;!.\-–—]*", "", message or "", flags=re.I)
    text = re.sub(r"\s+", " ", text).strip() or re.sub(r"\s+", " ", message or "").strip() or DEFAULT_TITLE
    if len(text) <= 48:
        return text
    cut = text[:48].rsplit(" ", 1)[0] or text[:48]
    return cut.rstrip(",.;: ") + "…"


def _owned(user) -> dict:
    return {"username": user["sub"], "tenant_id": user.get("tenant")}


def get_owned(user, cid: str) -> dict:
    doc = db.assistant_conversations.find_one({"_id": str(cid), **_owned(user)})
    if not doc:
        raise HTTPException(404, "Conversation not found.")
    return doc


def resolve(user, conversation_id, lab):
    """Return the conversation to use for a turn: the owned existing one, or a fresh one."""
    ensure_indexes()
    if conversation_id:
        return get_owned(user, conversation_id)
    now = _now()
    doc = {"_id": uuid.uuid4().hex, **_owned(user), "lab": lab, "title": DEFAULT_TITLE, "auto_title": True,
           "pinned": False, "message_count": 0, "created_at": now, "updated_at": now}
    db.assistant_conversations.insert_one(doc)
    return doc


def touch(conversation_id, message: str):
    """Called after a turn is saved: bump the counters and give the chat its title."""
    try:
        db.assistant_conversations.update_one({"_id": conversation_id},
                                              {"$set": {"updated_at": _now()}, "$inc": {"message_count": 1}})
        db.assistant_conversations.update_one({"_id": conversation_id, "auto_title": True, "title": DEFAULT_TITLE},
                                              {"$set": {"title": make_title(message)}})
    except Exception:
        log.exception("could not update conversation")


def _adopt_legacy(user):
    """One-time, idempotent: group pre-existing history rows into 'Earlier chat' conversations."""
    base = {"username": user["sub"], "conversation_id": None}
    if not db.assistant_history.find_one(base, {"_id": 1}):
        return
    groups = db.assistant_history.aggregate([
        {"$match": base},
        {"$group": {"_id": "$lab", "n": {"$sum": 1}, "first": {"$min": "$created_at"}, "last": {"$max": "$created_at"}}}])
    for g in groups:
        lab = g["_id"]
        cid = uuid.uuid4().hex
        db.assistant_conversations.insert_one({
            "_id": cid, **_owned(user), "lab": lab, "title": "Earlier chat" + (f" · Lab {lab}" if lab else ""),
            "auto_title": False, "pinned": False, "message_count": g["n"],
            "created_at": g["first"] or _now(), "updated_at": g["last"] or _now()})
        db.assistant_history.update_many({**base, "lab": lab}, {"$set": {"conversation_id": cid}})


def _public(c: dict) -> dict:
    return {"id": c["_id"], "title": c.get("title", DEFAULT_TITLE), "lab": c.get("lab"), "pinned": bool(c.get("pinned")),
            "message_count": c.get("message_count", 0), "created_at": c.get("created_at"), "updated_at": c.get("updated_at")}


def _messages(user, cid: str, limit: int = 500):
    rows = db.assistant_history.find({"conversation_id": cid, "username": user["sub"]},
                                     {"message": 1, "reply": 1, "answer_mode": 1, "created_at": 1}).sort("created_at", 1).limit(limit)
    return [{"id": str(r["_id"]), "message": r.get("message", ""), "reply": r.get("reply", ""),
             "mode": r.get("answer_mode"), "created_at": r.get("created_at")} for r in rows]


# ----------------------------------------------------------------- endpoints
@router.get("")
def list_conversations(q: str | None = None, lab: str | None = None, limit: int = 100, user=Depends(current_user)):
    ensure_indexes()
    _adopt_legacy(user)
    query = {**_owned(user), "message_count": {"$gt": 0}}
    if lab:
        query["lab"] = lab
    term = (q or "").strip()[:80]
    if term:
        rx = {"$regex": re.escape(term), "$options": "i"}
        hits = db.assistant_history.distinct("conversation_id", {"username": user["sub"], "$or": [{"message": rx}, {"reply": rx}]})
        query["$or"] = [{"title": rx}, {"_id": {"$in": [h for h in hits if h]}}]
    rows = list(db.assistant_conversations.find(query).sort([("pinned", -1), ("updated_at", -1)]).limit(max(1, min(limit, 200))))
    return {"conversations": [_public(c) for c in rows]}


@router.get("/{cid}")
def get_conversation(cid: str, user=Depends(current_user)):
    c = get_owned(user, cid)
    return {**_public(c), "messages": _messages(user, cid)}


@router.patch("/{cid}")
def update_conversation(cid: str, body: ConversationPatch, user=Depends(current_user)):
    get_owned(user, cid)
    changes = {}
    if body.title is not None:
        title = re.sub(r"\s+", " ", body.title).strip()
        if not title or len(title) > 80:
            raise HTTPException(400, "Title must be 1–80 characters.")
        changes.update(title=title, auto_title=False)
    if body.pinned is not None:
        changes["pinned"] = body.pinned
    if changes:
        db.assistant_conversations.update_one({"_id": cid}, {"$set": changes})
    return _public(get_owned(user, cid))


@router.delete("/{cid}")
def delete_conversation(cid: str, user=Depends(current_user)):
    get_owned(user, cid)
    removed = db.assistant_history.delete_many({"conversation_id": cid, "username": user["sub"]}).deleted_count
    db.assistant_conversations.delete_one({"_id": cid, **_owned(user)})
    return {"ok": True, "deleted_messages": removed}


@router.delete("")
def delete_all_conversations(lab: str | None = None, user=Depends(current_user)):
    """Deletes only the signed-in user's own conversations (optionally only for one lab context)."""
    query = _owned(user)
    if lab:
        query["lab"] = lab
    ids = [c["_id"] for c in db.assistant_conversations.find(query, {"_id": 1})]
    removed = db.assistant_history.delete_many({"username": user["sub"], "conversation_id": {"$in": ids}}).deleted_count if ids else 0
    db.assistant_conversations.delete_many({"_id": {"$in": ids}, **_owned(user)})
    return {"ok": True, "deleted_conversations": len(ids), "deleted_messages": removed}


@router.delete("/{cid}/messages/last")
def delete_last_message(cid: str, expect: str | None = None, user=Depends(current_user)):
    """Removes the newest exchange (used by Regenerate and Edit).

    If ``expect`` (the user message the browser believes is last) does not match, nothing is deleted,
    so a stale screen can never remove the wrong exchange.
    """
    get_owned(user, cid)
    last = db.assistant_history.find_one({"conversation_id": cid, "username": user["sub"]}, sort=[("created_at", -1)])
    if not last:
        raise HTTPException(404, "This conversation has no messages.")
    if expect is not None and last.get("message", "") != expect:
        return {"ok": True, "removed": False, "message": last.get("message", "")}
    db.assistant_history.delete_one({"_id": last["_id"]})
    db.assistant_conversations.update_one({"_id": cid, "message_count": {"$gt": 0}}, {"$inc": {"message_count": -1}})
    return {"ok": True, "removed": True, "message": last.get("message", "")}


@router.get("/{cid}/export")
def export_conversation(cid: str, user=Depends(current_user)):
    c = get_owned(user, cid)
    lines = [f"# {c.get('title', DEFAULT_TITLE)}", f"*Exported from Boss · SENTINEL-X · {_now():%Y-%m-%d %H:%M} UTC*", ""]
    for m in _messages(user, cid):
        lines += [f"**You:** {m['message']}", "", f"**Boss:** {m['reply']}", "", "---", ""]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", c.get("title", "chat"))[:40] or "chat"
    return PlainTextResponse("\n".join(lines), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="boss-{name}.md"'})
