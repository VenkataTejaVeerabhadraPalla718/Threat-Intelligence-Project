"""Small, dependency-free project-file retrieval for Boss (lexical RAG).

Indexes safe text files under the project root in memory and returns the most
relevant chunks. Secret/config files and generated/binary directories are excluded.
"""
from pathlib import Path
import re
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
_ALLOWED = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".sql", ".ps1", ".js", ".html", ".toml", ".ini"}
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "backups", "dist", "build", "coverage", ".pytest_cache"}
_SKIP_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "secrets.json", "credentials.json"}
_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{1,40}")
_LOCK = threading.Lock()
_INDEX = []
_INDEXED_AT = 0.0
_TTL = 300
_MAX_FILES = 1800
_MAX_FILE_BYTES = 512_000
_MAX_CHUNKS = 7000
_CHUNK = 1700
_OVERLAP = 220


def _tokens(text):
    return {x.casefold() for x in _TOKEN.findall(text)}


def _build_index():
    chunks = []
    files_seen = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _ALLOWED:
            continue
        rel = path.relative_to(ROOT)
        if any(part in _SKIP_DIRS for part in rel.parts) or path.name.casefold() in _SKIP_NAMES:
            continue
        if path.name.startswith(".env") or path.stat().st_size > _MAX_FILE_BYTES:
            continue
        files_seen += 1
        if files_seen > _MAX_FILES:
            break
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not content.strip():
            continue
        start = 0
        while start < len(content) and len(chunks) < _MAX_CHUNKS:
            part = content[start:start + _CHUNK]
            if len(part.strip()) > 80:
                chunks.append({"path": str(rel).replace("\\", "/"), "text": part, "tokens": _tokens(part)})
            start += _CHUNK - _OVERLAP
    return chunks


def retrieve(message: str, lab: str | None = None, limit: int = 5) -> str:
    global _INDEX, _INDEXED_AT
    now = time.time()
    if not _INDEX or now - _INDEXED_AT > _TTL:
        with _LOCK:
            if not _INDEX or time.time() - _INDEXED_AT > _TTL:
                _INDEX = _build_index()
                _INDEXED_AT = time.time()
    query_tokens = _tokens(message)
    if not query_tokens:
        return ""
    lab_match = re.search(r"(?:lab\s*|lab)(1[0-8]|[1-9])", str(lab or message), re.I)
    lab_num = lab_match.group(1) if lab_match else None
    ranked = []
    for item in _INDEX:
        overlap = query_tokens & item["tokens"]
        if not overlap:
            continue
        score = len(overlap) / max(5, len(query_tokens))
        path = item["path"].casefold()
        if lab_num and (f"lab{int(lab_num):02d}" in path or f"lab{lab_num}" in path):
            score += 0.65
        if path.endswith("readme.md") or path.startswith("docs/"):
            score += 0.04
        ranked.append((score, item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = []
    for score, item in ranked[:limit]:
        selected.append(f"[Source: {item['path']} | relevance: {score:.2f}]\n{item['text'].strip()[:1500]}")
    return "\n\n---\n\n".join(selected)


def augment_messages(messages: list[dict], message: str, lab: str | None = None) -> list[dict]:
    context = retrieve(message, lab)
    if context and messages:
        messages[0]["content"] += (
            "\n\nPROJECT FILE CONTEXT (retrieved from the current SENTINEL-X workspace; "
            "treat as source evidence, cite file paths in your answer, and say when evidence is missing):\n"
            + context[:7500]
        )
    return messages
