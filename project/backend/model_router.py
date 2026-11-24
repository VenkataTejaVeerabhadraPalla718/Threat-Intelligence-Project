"""Hybrid model routing for SENTINEL-X Boss.

Short/simple prompts use the local Ollama model. Complex coding, debugging,
architecture and longer lab questions use Ollama Cloud when configured.
Cloud failures fall back to the local model; secrets never enter responses/logs.
"""
import re
import config

_CLOUD_PATTERNS = re.compile(
    r"\b(debug|debugging|traceback|exception|error|fix|repair|upgrade|refactor|rewrite|"
    r"implement|architecture|design|optimi[sz]e|review|analy[sz]e|compare|integrat|"
    r"multi.?step|codebase|project files|docker compose|lab\s*(?:1[0-8]|[1-9]))\b",
    re.I,
)


def cloud_ready() -> bool:
    return bool(config.ASSISTANT_CLOUD_ENABLED and config.OLLAMA_API_KEY)


def choose_provider(message: str) -> str:
    """Prefer local for fast/simple prompts; cloud for complex work if configured."""
    if not cloud_ready():
        return "local"
    text = (message or "").strip()
    if len(text) >= 450 or _CLOUD_PATTERNS.search(text):
        return "cloud"
    # Multi-part questions tend to benefit from the larger hosted model.
    if len(re.findall(r"[?\n]", text)) >= 2 or len(re.findall(r"\b(and|also|then|while)\b", text, re.I)) >= 3:
        return "cloud"
    return "local"


def target(provider: str) -> dict:
    if provider == "cloud":
        return {
            "provider": "ollama-cloud",
            "model": config.OLLAMA_CLOUD_MODEL,
            "url": f"{config.OLLAMA_CLOUD_URL}/chat",
            "headers": {"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
        }
    return {
        "provider": "ollama-local",
        "model": config.OLLAMA_LOCAL_MODEL,
        "url": f"{config.OLLAMA_URL}/api/chat",
        "headers": {},
    }


def candidates(message: str) -> list[dict]:
    preferred = choose_provider(message)
    result = [target(preferred)]
    # Graceful fallback in either direction: cloud outages fall back to local,
    # and a stopped/unavailable local Ollama server can fall back to cloud.
    if cloud_ready():
        fallback = "local" if preferred == "cloud" else "cloud"
        result.append(target(fallback))
    return result
