"""Assistant core: controlled tool registry, response cache and prompt builder.

Tools are an explicit allow-list. There is no shell access and no arbitrary database command.
Read-only tools run for any signed-in user; experiment execution and security data are admin-only.
"""
import logging
import re
import random
import time
import threading
import hashlib
from collections import OrderedDict
from datetime import datetime, timezone

from pydantic import BaseModel

import config
import conversations
import knowledge
from assistant_tools import answer_data_question
from common import db
from dashboard import EXPERIMENTS, LAB_INTEGRATION, MANUAL, RUN_WARNINGS, run as run_experiment
from labs_api import _describe, _latest_by_lab
from monitor import snapshot

log = logging.getLogger("sentinelx.assistant")


class AssistantRequest(BaseModel):
    message: str
    lab: str | None = None
    history: list[dict] | None = None
    conversation_id: str | None = None


# ----------------------------------------------------------------- cache
_CACHE: "OrderedDict[tuple, tuple[float, str]]" = OrderedDict()
_CACHE_LOCK = threading.RLock()
_CACHE_MAX = 512


def cacheable_fast_query(message: str) -> bool:
    """Only cache standalone informational queries; never cache actions or contextual follow-ups."""
    q = strip_wake_word(message).lower().strip()
    if not q or len(q) > 500:
        return False
    if re.search(r"\b(run|execute|start|confirm|delete|remove|create|update|change|stop|restart)\b", q):
        return False
    if re.search(r"\b(it|that|those|these|them|same|instead|also|what about|and then)\b", q):
        return False
    return True


def cache_get(key):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < config.ASSISTANT_CACHE_TTL:
            _CACHE.move_to_end(key)
            return hit[1]
        _CACHE.pop(key, None)
        return None


def cache_put(key, value):
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


def cache_key(message: str, lab):
    # Normalize harmless punctuation/spacing differences so equivalent queries share a cache entry.
    normalized = re.sub(r"[^\w\s.-]", " ", strip_wake_word(message).casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return (config.OLLAMA_LOCAL_MODEL, config.OLLAMA_CLOUD_MODEL if config.ASSISTANT_CLOUD_ENABLED else "", lab or "", digest)


# ----------------------------------------------------------------- history
def store_history(user, lab, message, reply, mode, shared=None, conversation_id=None):
    try:
        db.assistant_history.insert_one({"username": user["sub"], "lab": lab, "message": message, "reply": reply,
                                         "answer_mode": mode, "shared_state": shared, "conversation_id": conversation_id,
                                         "created_at": datetime.now(timezone.utc)})
    except Exception:
        log.exception("could not store assistant history")
        return
    if conversation_id:
        conversations.touch(conversation_id, message)


# ----------------------------------------------------------------- tools
def _format_run(result: dict, header: str) -> str:
    return f"{header}\nStatus: {result.get('status')}\nJob ID: {result.get('job_id', 'n/a')}\nThe website live console will display output as it is produced.\n{result.get('output', '(No output yet)')}"


def _reply(text, lab, mode="tool", **extra):
    return {"reply": text, "mode": mode, "lab": lab, "executed": False, "model": "SENTINEL-X tools", **extra}


def _tool_health(lab):
    snap = snapshot()
    members = snap.get("members", [])
    lines = [f"- {m.get('name', '?')}: {m.get('state', '?')}" for m in members] or ["- no replica-set members reported"]
    db.command("ping")
    return _reply("**System health** (live query)\nDatabase: reachable\nReplica set members:\n" + "\n".join(lines), lab)


def _tool_recent_threats(lab, count):
    rows = list(db.threats.find({}, {"title": 1, "classification": 1, "published_at": 1, "record_origin": 1})
                .sort("published_at", -1).limit(count))
    if not rows:
        return _reply("No threat records are stored yet.", lab)
    out = [f"- [{(r.get('classification') or {}).get('severity', '?')}] {r.get('title', 'Untitled')[:110]}"
           f" ({r.get('record_origin', 'unknown')})" for r in rows]
    return _reply(f"**{len(rows)} most recent threat records** (live query; unverified feed data)\n" + "\n".join(out), lab)


def _tool_lab_status(lab, n):
    d = _describe(n, _latest_by_lab())
    exps = ", ".join(e["id"] for e in d["experiments"]) or "none"
    return _reply(f"**Lab {n} status (live):** {d['status'].replace('_', ' ').upper()}\n"
                  f"Registered experiments: {exps}\nManual steps: {len(d['manual_steps'])}\n"
                  f"Last run: {d['last_run'] or 'never executed from this platform'}", lab)


def _tool_lab_output(lab, n):
    run = db.experiment_runs.find_one({"lab": {"$regex": rf"^{n}\."}}, sort=[("ts", -1)])
    if not run:
        return _reply(f"No recorded run exists for Lab {n} yet.", lab)
    return _reply(f"**Latest recorded output for {run.get('lab')} · {run.get('title')}** ({run.get('status')}, {run.get('seconds')}s)\n"
                  f"```\n{str(run.get('output', ''))[:1800]}\n```", lab)


def _tool_security(lab):
    from saas import admin_security
    s = admin_security(user={"role": "admin"})
    return _reply(f"**Security summary (live)**\nFailed logins (24h): {s['failed_logins_24h']}\nLockouts (24h): {s['lockouts_24h']}\n"
                  f"Repeated-failure alerts: {len(s['repeated_failures'])}\nPossible password spraying: {len(s['possible_password_spraying'])}\n"
                  f"Disabled accounts: {len(s['disabled_accounts'])}", lab)


ASSISTANT_NAME = "Boss"
_WAKE = re.compile(r"^\s*(?:(?:hey|hi|hello|ok|okay|yo)\s+)?boss\b[\s,:;!.\-–—]*", re.I)
_WHO = re.compile(r"^(who are you|what('?s| is) your name|what should i call you|what do i call you|your name)\b", re.I)


def strip_wake_word(message: str) -> str:
    """'Hey Boss, latest 5 threats' -> 'latest 5 threats' so the tools and knowledge base still match."""
    return _WAKE.sub("", message or "", count=1).strip()


def _identity(lab):
    return {"reply": f"I'm **{ASSISTANT_NAME}**, the AI assistant of SENTINEL-X. Call me by name any time, e.g. *\"Boss, latest 5 threats\"* or "
                     "*\"Hey Boss, explain lab 8\"*. I can explain Labs 1–4 and 7–18, MongoDB and Docker, help debug errors, summarise threat data "
                     "and run registered experiments (administrators only).", "mode": "greeting", "lab": lab, "executed": False, "model": "Boss"}


def try_tools(message: str, lab_context, user):
    """Return an instant structured answer from the knowledge base or a tool, or None to use the LLM."""
    is_admin = user.get("role") == "admin"
    addressed = strip_wake_word(message)
    if not addressed:  # just "Boss" / "Hey Boss"
        return {**_identity(lab_context), "reply": f"Yes, I'm {ASSISTANT_NAME}. What do you need?"}
    if _WHO.match(addressed.rstrip("?.! ")):
        return _identity(lab_context)
    message = addressed
    low = message.lower()

    # Live database facts must take precedence over static explanatory knowledge.
    data = answer_data_question(message, db)
    if data is not None:
        return {"reply": data, "mode": "database", "lab": lab_context, "executed": False, "model": "MongoDB query tools"}
    kb = knowledge.answer(message)
    if kb:
        return {"reply": kb, "mode": "knowledge", "lab": lab_context, "executed": False, "model": "Built-in knowledge base"}

    try:
        if re.search(r"\b(system|cluster|database|replica ?set|platform)\s+(health|status)\b|\bis (the )?(system|database|cluster) (up|healthy|ok)", low):
            return _tool_health(lab_context)
        m = re.search(r"\b(?:latest|recent|newest|last)\s+(\d+\s+)?threats?\b", low)
        if m:
            return _tool_recent_threats(lab_context, min(int((m.group(1) or "5").strip()), 10))
        m = re.search(r"\blab\s*(1[0-8]|[1-4])\s+(?:status|state)\b|\b(?:status|state)\s+of\s+lab\s*(1[0-8]|[1-4])\b", low)
        if m:
            return _tool_lab_status(lab_context, int(m.group(1) or m.group(2)))
        m = re.search(r"\b(?:output|result|log)s?\s+(?:of|for|from)\s+lab\s*(1[0-8]|[1-4])\b|\blab\s*(1[0-8]|[1-4])\s+(?:output|results?|logs?)\b", low)
        if m:
            return _tool_lab_output(lab_context, int(m.group(1) or m.group(2)))
        if re.search(r"\b(security\s+(alerts?|summary|status)|failed\s+logins?|login\s+alerts?)\b", low):
            if not is_admin:
                return _reply("Security and login-audit information is available to administrators only.", lab_context)
            return _tool_security(lab_context)
    except Exception as exc:
        log.exception("tool failed")
        return _reply(f"The tool could not complete: {type(exc).__name__}: {str(exc)[:160]}", lab_context, error=True)

    if re.search(r"\b(run|execute|start)\s+(?:a\s+)?random\s+lab\b|\brandomly\s+(?:run|execute)\s+(?:a\s+)?lab\b", low):
        if not is_admin:
            return _reply("Only administrators can run lab experiments.", lab_context)
        safe = [(k, v) for k, v in EXPERIMENTS.items() if k not in RUN_WARNINGS]
        if not safe:
            return _reply("No confirmation-free lab is currently registered.", lab_context)
        key, meta = random.choice(safe)
        result = run_experiment(key, confirmed=False, user=user)
        return {**_reply(_format_run(result, f"Randomly selected Lab {meta[0]} · {meta[1]}"), meta[0].split('.')[0]),
                "executed": True, "queued": True, "job_id": result.get("job_id"), "result": result}

    confirm = re.search(r"\bconfirm\s+(?:run\s+)?([a-z0-9-]+)\b", message, re.I)
    if confirm and confirm.group(1).lower() in EXPERIMENTS:
        if not is_admin:
            return _reply("Only administrators can run lab experiments.", lab_context)
        exp_id = confirm.group(1).lower()
        result = run_experiment(exp_id, confirmed=True, user=user)
        return {**_reply(_format_run(result, f"{result.get('lab')} · {result.get('title')}"), lab_context),
                "executed": True, "queued": True, "job_id": result.get("job_id"), "result": result}

    m = re.search(r"\b(?:run|execute|start)\s+(?:lab\s*)?(1[0-8]|[1-4])(?:\.(\d+))?\b", message, re.I)
    if m:
        lab, sub = m.group(1), m.group(2)
        if not is_admin:
            return _reply("Only administrators can run lab experiments. I can still explain the lab or show its latest recorded output.", lab)
        available = [(k, v) for k, v in EXPERIMENTS.items() if v[0].split(".")[0] == lab and (not sub or v[0] == f"{lab}.{sub}")]
        if not available:
            steps = [x for x in MANUAL if str(x["lab"]).split(".")[0] == lab]
            cmds = "\n".join(f"- {x['lab']} {x['title']}: {x['cmd']}" for x in steps)
            return _reply(f"Lab {lab} has no operation in the safe execution registry, so I did not run anything.\n"
                          f"Prerequisites: {', '.join(LAB_INTEGRATION[lab]['uses'])}.\nManual steps (run these yourself):\n{cmds or 'Review the lab workspace prerequisites.'}", lab)
        key, meta = available[0]
        if key in RUN_WARNINGS:
            return _reply(f"Confirmation required for {key}: {RUN_WARNINGS[key]}\nNothing has been run. After reviewing the warning, reply: confirm {key}",
                          lab, confirmation_required=True, experiment_id=key)
        result = run_experiment(key, confirmed=False, user=user)
        return {**_reply(_format_run(result, f"Lab {lab} · {meta[1]}"), lab), "executed": True, "queued": True, "job_id": result.get("job_id"), "result": result}
    return None


# ----------------------------------------------------------------- LLM prompt
SYSTEM = ("You are Boss, the AI assistant inside SENTINEL-X, an enterprise NoSQL threat-intelligence platform. If asked your name, say you are Boss. Answer any technical question, "
          "including MongoDB, replica sets, sharding, Docker, FastAPI, Python, security and Labs 1-4 and 7-18. Reply directly and concisely: "
          "lead with the answer, then short steps or a code block if useful. Use the supplied live state; never invent counts or claim "
          "an experiment passed or a command ran unless a tool result says so. You only generate instructions. Never request secrets.")


def build_messages(message: str, lab_context, user, body_history, conversation_id=None):
    try:
        # Avoid full collection counts on every LLM turn; explicit analytics tools fetch live counts.
        shared = {"data_access": "available through read-only tools"}
        scope = ({"username": user["sub"], "conversation_id": conversation_id} if conversation_id
                 else {"username": user["sub"], "lab": lab_context, "answer_mode": "llm"})
        prior = list(db.assistant_history.find(scope, {"_id": 0, "message": 1, "reply": 1}).sort("created_at", -1).limit(3))
    except Exception as exc:
        shared, prior = {"database": "temporarily unavailable", "detail": type(exc).__name__}, []
    lab_line = f"Workspace lab: {lab_context} {LAB_INTEGRATION.get(lab_context, {})}" if lab_context else "Workspace: general"
    msgs = [{"role": "system", "content": f"{SYSTEM}\n{lab_line}\nLive state: {shared}"}]
    seen = set()
    for item in (body_history or [])[-6:]:
        role, content = item.get("role"), str(item.get("content", ""))[:1500]
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content}); seen.add(content)
    if len(msgs) == 1:  # no client-side history: fall back to the saved conversation
        for item in reversed(prior):
            msgs += [{"role": "user", "content": item.get("message", "")[:1500]}, {"role": "assistant", "content": item.get("reply", "")[:1500]}]
    msgs.append({"role": "user", "content": message})
    return msgs, shared, len(msgs) == 2  # (messages, shared state, is_first_turn)


def ollama_options():
    return {"temperature": 0.25, "num_ctx": config.OLLAMA_NUM_CTX, "num_predict": config.OLLAMA_NUM_PREDICT}
