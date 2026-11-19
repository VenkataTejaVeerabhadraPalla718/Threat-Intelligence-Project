"""SENTINEL-X API entry point."""
import logging
import re
import threading
import time
import uuid
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import agent
import config
import conversations
from lab_jobs import recover_interrupted_jobs
from k8s_jobs import recover_k8s_workflows
from assistant_stream import router as stream_router
from chat import router as chat_router
from common import db
from dashboard import router as dashboard_router
from hybrid import router as hybrid_router
from labs_api import router as labs_router
from monitor import snapshot
from overview import router as overview_router
from saas import current_user, router as saas_router
from threats import router as threats_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sentinelx")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
app = FastAPI(title="SENTINEL-X API", version="3.0",
              description="Threat intelligence, NoSQL laboratory, security operations and AI-assistant platform.")
for r in (saas_router, threats_router, overview_router, labs_router, chat_router, dashboard_router, hybrid_router, stream_router, conversations.router):
    app.include_router(r)
app.mount("/assets", StaticFiles(directory=FRONTEND), name="assets")


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request ID and processing time to every response and add baseline security headers."""
    rid = re.sub(r"[^A-Za-z0-9_.-]", "", request.headers.get("x-request-id", ""))[:64] or uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Process-Time-ms"] = str(round((time.perf_counter() - started) * 1000))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _warm_model():
    """Load the Ollama model into memory at startup so the first question is not slow."""
    try:
        requests.post(f"{config.OLLAMA_URL}/api/generate", timeout=(3, 120),
                      json={"model": config.OLLAMA_MODEL, "prompt": "", "keep_alive": config.OLLAMA_KEEP_ALIVE})
        log.info("Ollama model %s warmed up", config.OLLAMA_MODEL)
    except Exception as exc:
        log.info("Ollama warm-up skipped (%s)", type(exc).__name__)


@app.on_event("startup")
def startup():
    threading.Thread(target=conversations.ensure_indexes, daemon=True, name="conversation-indexes").start()
    threading.Thread(target=recover_interrupted_jobs, daemon=True, name="lab-job-recovery").start()
    threading.Thread(target=recover_k8s_workflows, daemon=True, name="k8s-job-recovery").start()
    threading.Thread(target=_warm_model, daemon=True, name="ollama-warmup").start()


@app.get("/api/monitor")
def monitor(user=Depends(current_user)):
    return snapshot()


for _path in ("/", "/console", "/login", "/register", "/threats", "/chat", "/dashboard"):
    app.add_api_route(_path, lambda: FileResponse(FRONTEND / "enterprise.html"), methods=["GET"], include_in_schema=False)


@app.get("/health")
def health():
    try:
        db.command("ping")
        return {"status": "ok", "database": "connected", "project": "SENTINEL-X"}
    except Exception as exc:
        return {"status": "degraded", "database": "unavailable", "detail": type(exc).__name__}


# ----------------------------------------------------------------- assistant
@app.get("/api/assistant/status")
def assistant_status(user=Depends(current_user)):
    model = config.OLLAMA_MODEL
    try:
        response = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        response.raise_for_status()
        models = [item.get("name", "") for item in response.json().get("models", [])]
        available = any(n == model or n.split(":")[0] == model.split(":")[0] for n in models)
        return {"ok": True, "ollama": config.OLLAMA_URL, "model": model, "model_available": available, "models": models,
                "message": "Local model ready" if available else f"Run: ollama pull {model}"}
    except Exception as exc:
        return {"ok": False, "ollama": config.OLLAMA_URL, "model": model, "model_available": False, "models": [],
                "message": f"Ollama is unreachable: {type(exc).__name__}: {str(exc)[:180]}"}


@app.get("/api/assistant/history")
def assistant_history(lab: str | None = None, user=Depends(current_user)):
    rows = list(db.assistant_history.find({"username": user["sub"], "lab": lab},
                                          {"_id": 0, "message": 1, "reply": 1, "created_at": 1}).sort("created_at", -1).limit(40))
    return {"messages": list(reversed(rows))}


@app.delete("/api/assistant/history")
def clear_assistant_history(lab: str | None = None, user=Depends(current_user)):
    """Deletes only the signed-in user's own conversation for the given context."""
    return {"ok": True, "deleted": db.assistant_history.delete_many({"username": user["sub"], "lab": lab}).deleted_count}  # legacy endpoint; the UI now uses /api/conversations


@app.post("/api/assistant")
def local_assistant(body: agent.AssistantRequest, user=Depends(current_user)):
    """Non-streaming fallback (same tools, same safety rules as /api/assistant/stream)."""
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Enter a message")
    if len(message) > 6000:
        raise HTTPException(413, "Message is too long (limit 6000 characters).")
    lab = str(body.lab).strip() if body.lab else None
    cid = conversations.resolve(user, body.conversation_id, lab)["_id"]
    tool = agent.try_tools(message, lab, user)
    if tool:
        agent.store_history(user, lab, message, tool["reply"], tool["mode"], conversation_id=cid)
        return {**tool, "conversation_id": cid}
    msgs, shared, _ = agent.build_messages(message, lab, user, body.history, cid)
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=(8, 240),
                          json={"model": config.OLLAMA_MODEL, "messages": msgs, "stream": False,
                                "keep_alive": config.OLLAMA_KEEP_ALIVE, "options": agent.ollama_options()})
        if r.status_code == 404:
            raise RuntimeError(f"Model '{config.OLLAMA_MODEL}' not found. Run: ollama pull {config.OLLAMA_MODEL}")
        r.raise_for_status()
        answer = r.json().get("message", {}).get("content", "").strip() or "The model returned an empty response."
        agent.store_history(user, lab, message, answer, "llm", shared, cid)
        return {"reply": answer, "model": config.OLLAMA_MODEL, "lab": lab, "executed": False, "conversation_id": cid}
    except Exception as exc:
        return {"reply": f"The local assistant could not complete the request.\n{type(exc).__name__}: {str(exc)[:250]}\n"
                         f"Check `ollama list` and OLLAMA_URL ({config.OLLAMA_URL}).",
                "lab": lab, "model": config.OLLAMA_MODEL, "executed": False, "error": True}
