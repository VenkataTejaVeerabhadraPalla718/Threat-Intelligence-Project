"""Server-Sent-Events assistant endpoint: instant tool/KB/cache answers, otherwise live token streaming."""
import json
import logging
import time

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

import agent
import config
import conversations
import model_router
from project_knowledge import augment_messages
from saas import current_user

router = APIRouter(prefix="/api")
log = logging.getLogger("sentinelx.assistant")


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, default=str) + "\n\n"


@router.post("/assistant/stream")
def assistant_stream(body: agent.AssistantRequest, user=Depends(current_user)):
    message = body.message.strip()
    if not message:
        raise HTTPException(400, "Enter a message")
    if len(message) > 6000:
        raise HTTPException(413, "Message is too long (limit 6000 characters).")
    lab = str(body.lab).strip() if body.lab else None
    conv = conversations.resolve(user, body.conversation_id, lab)   # 404 if it is not this user's conversation
    cid, is_new = conv["_id"], conv.get("message_count", 0) == 0

    def gen():
        t0 = time.perf_counter()
        ms = lambda: round((time.perf_counter() - t0) * 1000)  # noqa: E731
        yield _sse({"type": "meta", "conversation_id": cid})
        key = agent.cache_key(message, lab)
        # Cache standalone questions before touching MongoDB or Ollama. Contextual follow-ups
        # and state-changing commands are deliberately excluded by cacheable_fast_query().
        cache_allowed = agent.cacheable_fast_query(message)
        cached = agent.cache_get(key) if cache_allowed else None
        if cached is not None:
            agent.store_history(user, lab, message, cached, "cache", conversation_id=cid)
            yield _sse({"type": "final", "reply": cached, "mode": "cache", "lab": lab,
                        "executed": False, "model": "SENTINEL-X response cache", "cached": True, "ms": ms()})
            yield _sse({"type": "done", "ms": ms(), "first_token_ms": ms(), "cached": True, "instant": True})
            return
        tool = agent.try_tools(message, lab, user)
        if tool:
            agent.store_history(user, lab, message, tool["reply"], tool["mode"], conversation_id=cid)
            if cache_allowed and not tool.get("executed") and not tool.get("confirmation_required"):
                agent.cache_put(key, tool["reply"])
            yield _sse({"type": "final", **{k: v for k, v in tool.items() if k != "result"}, "ms": ms()})
            yield _sse({"type": "done", "ms": ms(), "instant": True})
            return
        msgs, shared, first_turn = agent.build_messages(message, lab, user, body.history, cid)
        msgs = augment_messages(msgs, message, lab)
        parts, first = [], None
        targets = model_router.candidates(message)
        used_target = targets[0]
        last_error = None
        for target_index, target in enumerate(targets):
            used_target = target
            payload = {
                "model": target["model"],
                "messages": msgs,
                "stream": True,
                "think": False,
                "options": agent.ollama_options()
            }
            if target["provider"] == "ollama-local":
                payload["keep_alive"] = config.OLLAMA_KEEP_ALIVE
            try:
                with requests.post(target["url"], headers=target["headers"], stream=True,
                                   timeout=(8, 240), json=payload) as r:
                    if r.status_code == 404 and target["provider"] == "ollama-local":
                        raise RuntimeError(f"Local model '{target['model']}' not found. Run: ollama pull {target['model']}")
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise RuntimeError(str(chunk["error"])[:200])
                        tok = (chunk.get("message") or {}).get("content", "")
                        if tok:
                            if first is None:
                                first = ms()
                            parts.append(tok)
                            yield _sse({"type": "token", "text": tok})
                        if chunk.get("done"):
                            break
                last_error = None
                break
            except GeneratorExit:
                if parts:
                    agent.store_history(user, lab, message, "".join(parts), "llm", shared, cid)
                raise
            except Exception as exc:
                last_error = exc
                # If cloud failed before emitting text, transparently fall back to local.
                if not parts and target_index + 1 < len(targets):
                    log.warning("assistant route %s failed; trying fallback route (%s)", target["provider"], type(exc).__name__)
                    continue
                log.warning("assistant stream failed (%s): %s", target["provider"], type(exc).__name__)
                yield _sse({"type": "error", "message": f"Assistant request failed using {target['provider']}: {type(exc).__name__}: {str(exc)[:180]}"})
                return
        if last_error is not None and not parts:
            yield _sse({"type": "error", "message": f"Assistant unavailable: {type(last_error).__name__}: {str(last_error)[:180]}"})
            return
        answer = "".join(parts).strip()
        if answer:
            agent.store_history(user, lab, message, answer, "llm", shared, cid)
            if first_turn and len(message) < 300 and agent.cacheable_fast_query(message):
                agent.cache_put(key, answer)
        yield _sse({"type": "done", "ms": ms(), "first_token_ms": first, "model": used_target["model"], "provider": used_target["provider"]})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
