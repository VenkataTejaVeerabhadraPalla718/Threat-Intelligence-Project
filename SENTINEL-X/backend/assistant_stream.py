
"""SENTINEL-X Boss assistant: instant tools/cache + Gemini/Ollama streaming."""

import base64
import binascii
import json
import logging
import mimetypes
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


def _gemini_payload(messages: list[dict], image_parts: list[dict] | None = None) -> dict:
    """Convert the existing agent message format into Gemini REST format."""
    contents = []
    system_parts = []
    last_user_index = max((i for i, item in enumerate(messages) if item.get("role") == "user"), default=-1)

    for message_index, item in enumerate(messages):
        role = item.get("role", "user")
        content = str(item.get("content", ""))

        if not content:
            continue

        if role == "system":
            system_parts.append(content)
        elif role in ("user", "assistant"):
            parts = [{"text": content}]
            if role == "user" and message_index == last_user_index and image_parts:
                parts.extend(image_parts)
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": parts,
            })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": config.OLLAMA_NUM_PREDICT,
        },
    }

    if system_parts:
        payload["systemInstruction"] = {
            "parts": [{"text": "\n\n".join(system_parts)}]
        }

    return payload


def _stream_gemini(response):
    """Yield text chunks from Gemini's server-sent-event response."""
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")

        line = line.strip()

        if not line.startswith("data:"):
            continue

        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue

        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if chunk.get("error"):
            raise RuntimeError(
                str(chunk["error"].get("message", chunk["error"]))[:200]
            )

        candidates = chunk.get("candidates") or []
        if not candidates:
            continue

        content = candidates[0].get("content") or {}
        for part in content.get("parts", []):
            token = part.get("text", "")
            if token:
                yield token


def _stream_ollama(response):
    """Yield text chunks from Ollama's newline-delimited JSON response."""
    for line in response.iter_lines():
        if not line:
            continue

        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")

        chunk = json.loads(line)

        if chunk.get("error"):
            raise RuntimeError(str(chunk["error"])[:200])

        token = (chunk.get("message") or {}).get("content", "")
        if token:
            yield token



_ALLOWED_TEXT = {
    "text/plain", "text/markdown", "text/csv", "application/json",
    "application/xml", "text/xml", "text/html",
}
_MAX_FILE_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_BYTES = 20 * 1024 * 1024
_MAX_FILES = 8


def _extract_text_file(filename: str, mime: str, raw: bytes) -> str:
    """Extract common text/document formats; optional parsers fail clearly."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if mime in _ALLOWED_TEXT or suffix in {"txt", "md", "csv", "json", "xml", "html", "log", "py", "js", "sql", "yaml", "yml"}:
        return raw.decode("utf-8-sig", errors="replace")
    if suffix == "pdf" or mime == "application/pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise ValueError("PDF reading requires pypdf. Install it with: pip install pypdf")
    if suffix == "docx":
        try:
            from docx import Document
            import io
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise ValueError("DOCX reading requires python-docx. Install it with: pip install python-docx")
    if suffix in {"xlsx", "xlsm"}:
        try:
            from openpyxl import load_workbook
            import io
            wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"[Sheet: {ws.title}]")
                for row in ws.iter_rows(values_only=True):
                    lines.append(", ".join("" if v is None else str(v) for v in row))
            return "\n".join(lines)
        except ImportError:
            raise ValueError("Excel reading requires openpyxl. Install it with: pip install openpyxl")
    raise ValueError(f"Unsupported file type for {filename}. Supported: text, CSV, JSON, PDF, DOCX, XLSX, and images.")


def _decode_attachments(items):
    if not items:
        return "", []
    if len(items) > _MAX_FILES:
        raise ValueError(f"Attach no more than {_MAX_FILES} files at once.")
    total = 0
    docs, images = [], []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid attachment data.")
        name = str(item.get("name") or "attachment")[:180]
        mime = str(item.get("mime_type") or mimetypes.guess_type(name)[0] or "application/octet-stream").lower()
        encoded = str(item.get("data") or "")
        if "," in encoded and encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError(f"Could not read attachment: {name}")
        if not raw:
            raise ValueError(f"Attachment is empty: {name}")
        if len(raw) > _MAX_FILE_BYTES:
            raise ValueError(f"{name} exceeds the 8 MB per-file limit.")
        total += len(raw)
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("Attachments exceed the 20 MB total limit.")
        if mime.startswith("image/"):
            if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                raise ValueError(f"Unsupported image format: {mime}")
            images.append({"name": name, "mime_type": mime, "data": base64.b64encode(raw).decode("ascii")})
        else:
            text = _extract_text_file(name, mime, raw)
            docs.append(f"\n\n--- Attached file: {name} ---\n{text[:50000]}")
    return "".join(docs), images


@router.post("/assistant/stream")
def assistant_stream(body: agent.AssistantRequest, user=Depends(current_user)):
    message = (body.message or "").strip()

    try:
        attachment_text, image_attachments = _decode_attachments(body.attachments)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if not message and not attachment_text and not image_attachments:
        raise HTTPException(400, "Enter a message or attach a file.")

    if len(message) > 6000:
        raise HTTPException(
            413, "Message is too long (limit 6000 characters)."
        )

    lab = str(body.lab).strip() if body.lab else None

    # Resolve only a conversation owned by the signed-in user.
    conv = conversations.resolve(user, body.conversation_id, lab)
    cid = conv["_id"]
    is_new = conv.get("message_count", 0) == 0

    def gen():
        t0 = time.perf_counter()

        def ms():
            return round((time.perf_counter() - t0) * 1000)

        yield _sse({"type": "meta", "conversation_id": cid})

        # 1. Return cached standalone questions immediately.
        key = agent.cache_key(message, lab)
        cache_allowed = not body.attachments and agent.cacheable_fast_query(message)
        cached = agent.cache_get(key) if cache_allowed else None

        if cached is not None:
            agent.store_history(
                user, lab, message, cached, "cache",
                conversation_id=cid
            )
            yield _sse({
                "type": "final",
                "reply": cached,
                "mode": "cache",
                "lab": lab,
                "executed": False,
                "model": "SENTINEL-X response cache",
                "cached": True,
                "ms": ms(),
            })
            yield _sse({
                "type": "done",
                "ms": ms(),
                "first_token_ms": ms(),
                "cached": True,
                "instant": True,
            })
            return

        # 2. Try registered tools and the built-in knowledge base.
        try:
            tool_result = None if body.attachments else agent.try_tools(message, lab, user)
        except Exception as exc:
            log.exception("Assistant tool lookup failed")
            yield _sse({
                "type": "error",
                "message": (
                    f"Assistant tool lookup failed: "
                    f"{type(exc).__name__}: {str(exc)[:160]}"
                ),
            })
            return

        if tool_result:
            reply = tool_result.get("reply", "")
            mode = tool_result.get("mode", "tool")

            agent.store_history(
                user, lab, message, reply, mode,
                conversation_id=cid
            )

            yield _sse({
                "type": "final",
                **tool_result,
                "conversation_id": cid,
                "ms": ms(),
            })
            yield _sse({
                "type": "done",
                "ms": ms(),
                "first_token_ms": ms(),
                "instant": True,
            })
            return

        # 3. Build context for the language model.
        try:
            prompt_message = message + attachment_text
            if image_attachments and not prompt_message:
                prompt_message = "Please inspect the attached image(s) and describe relevant details."
            msgs, shared, first_turn = agent.build_messages(
                prompt_message, lab, user, body.history, cid
            )
            msgs = augment_messages(msgs, message, lab)
        except Exception as exc:
            log.exception("Could not build assistant context")
            yield _sse({
                "type": "error",
                "message": (
                    f"Could not prepare assistant context: "
                    f"{type(exc).__name__}: {str(exc)[:160]}"
                ),
            })
            return

        parts = []
        first = None
        targets = model_router.candidates(message)
        used_target = targets[0] if targets else {}
        last_error = None

        # 4. Try the preferred provider, then its configured fallback.
        for target_index, target in enumerate(targets):
            used_target = target

            try:
                provider = target["provider"]

                if provider == "gemini":
                    payload = _gemini_payload(
                        msgs,
                        [{"inline_data": {"mime_type": item["mime_type"], "data": item["data"]}}
                         for item in image_attachments],
                    )

                    with requests.post(
                        target["url"],
                        headers=target["headers"],
                        json=payload,
                        stream=True,
                        timeout=(10, 180),
                    ) as response:
                        response.raise_for_status()

                        for token in _stream_gemini(response):
                            if first is None:
                                first = ms()

                            parts.append(token)
                            yield _sse({
                                "type": "token",
                                "content": token,
                            })

                elif provider == "ollama-local":
                    payload = {
                        "model": target["model"],
                        "messages": [
                            {**item, **({"images": [x["data"] for x in image_attachments]}
                                       if item.get("role") == "user" and image_attachments
                                       and item is msgs[-1] else {})}
                            for item in msgs
                        ],
                        "stream": True,
                        "think": False,
                        "options": agent.ollama_options(),
                        "keep_alive": config.OLLAMA_KEEP_ALIVE,
                    }

                    with requests.post(
                        target["url"],
                        headers=target["headers"],
                        json=payload,
                        stream=True,
                        timeout=(8, 240),
                    ) as response:
                        if response.status_code == 404:
                            raise RuntimeError(
                                f"Local model '{target['model']}' not found. "
                                f"Run: ollama pull {target['model']}"
                            )

                        response.raise_for_status()

                        for token in _stream_ollama(response):
                            if first is None:
                                first = ms()

                            parts.append(token)
                            yield _sse({
                                "type": "token",
                                "content": token,
                            })

                else:
                    raise RuntimeError(
                        f"Unsupported assistant provider: {provider}"
                    )

                # Do not silently accept an empty model response.
                if not parts:
                    raise RuntimeError(
                        f"{provider} returned an empty response"
                    )

                # The selected provider completed successfully.
                break

            except Exception as exc:
                last_error = exc

                # Do not retry after tokens have already reached the browser:
                # retrying would duplicate or mix two answers.
                if not parts and target_index + 1 < len(targets):
                    log.warning(
                        "Assistant route %s failed; trying fallback (%s)",
                        target.get("provider", "unknown"),
                        type(exc).__name__,
                    )
                    continue

                log.warning(
                    "Assistant stream failed (%s): %s",
                    target.get("provider", "unknown"),
                    type(exc).__name__,
                )

                yield _sse({
                    "type": "error",
                    "message": (
                        f"Assistant request failed using "
                        f"{target.get('provider', 'unknown')}: "
                        f"{type(exc).__name__}: {str(exc)[:180]}"
                    ),
                })
                return

        if last_error is not None and not parts:
            yield _sse({
                "type": "error",
                "message": (
                    f"Assistant unavailable: "
                    f"{type(last_error).__name__}: {str(last_error)[:180]}"
                ),
            })
            return

        # 5. Store the completed answer and update the response cache.
        answer = "".join(parts).strip()

        if answer:
            history_message = message
            if body.attachments:
                history_message += " [Attachments: " + ", ".join(
                    str(x.get("name", "file"))[:100] for x in body.attachments if isinstance(x, dict)
                ) + "]"
            agent.store_history(
                user, lab, history_message, answer, "llm", shared, cid
            )

            if (
                first_turn
                and len(message) < 300
                and agent.cacheable_fast_query(message)
            ):
                agent.cache_put(key, answer)

        yield _sse({
            "type": "done",
            "ms": ms(),
            "first_token_ms": first,
            "model": used_target.get("model"),
            "provider": used_target.get("provider"),
        })

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
