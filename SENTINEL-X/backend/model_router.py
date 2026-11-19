
"""Route complex Boss requests to Gemini and simple requests to local Ollama."""

import re
import config


_CLOUD_PATTERNS = re.compile(
    r"\b(debug|debugging|traceback|exception|error|fix|repair|upgrade|"
    r"refactor|rewrite|implement|architecture|design|optimi[sz]e|"
    r"review|analy[sz]e|compare|integrat|multi.?step|codebase|"
    r"project files|docker compose|lab\s*(?:1[0-8]|[1-9]))\b",
    re.I,
)


def cloud_ready() -> bool:
    return bool(
        config.ASSISTANT_CLOUD_ENABLED
        and config.GEMINI_API_KEY
        and config.GEMINI_MODEL
    )


def choose_provider(message: str) -> str:
    """Use Gemini for complex prompts and local Ollama for simple prompts."""
    if not cloud_ready():
        return "local"

    text = (message or "").strip()

    if len(text) >= 450 or _CLOUD_PATTERNS.search(text):
        return "cloud"

    if len(re.findall(r"[?\n]", text)) >= 2:
        return "cloud"

    if len(re.findall(r"\b(and|also|then|while)\b", text, re.I)) >= 3:
        return "cloud"

    return "local"


def target(provider: str) -> dict:
    if provider == "cloud":
        model = config.GEMINI_MODEL
        return {
            "provider": "gemini",
            "model": model,
            "url": (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{model}:streamGenerateContent?alt=sse"
            ),
            "headers": {
                "x-goog-api-key": config.GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
        }

    return {
        "provider": "ollama-local",
        "model": config.OLLAMA_LOCAL_MODEL,
        "url": f"{config.OLLAMA_URL}/api/chat",
        "headers": {},
    }


def candidates(message: str) -> list[dict]:
    """Return preferred provider first, followed by a safe fallback."""
    preferred = choose_provider(message)
    result = [target(preferred)]

    if cloud_ready():
        fallback = "local" if preferred == "cloud" else "cloud"
        result.append(target(fallback))

    return result
