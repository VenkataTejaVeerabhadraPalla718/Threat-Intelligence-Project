"""Central configuration. Every tunable value is read from the environment here once."""
import os

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434").rstrip("/")
# Local model remains the fast default; OLLAMA_MODEL is retained as a compatibility alias.
OLLAMA_LOCAL_MODEL = os.getenv("OLLAMA_LOCAL_MODEL", os.getenv("OLLAMA_MODEL", "qwen3.5:4b"))
OLLAMA_MODEL = OLLAMA_LOCAL_MODEL
ASSISTANT_CLOUD_ENABLED = os.getenv("ASSISTANT_CLOUD_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/api").rstrip("/")
OLLAMA_CLOUD_MODEL = os.getenv("OLLAMA_CLOUD_MODEL", "gemma4:31b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "240"))
LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "8"))          # per username+IP
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
ALERT_FAILURE_THRESHOLD = int(os.getenv("ALERT_FAILURE_THRESHOLD", "5"))  # admin security alerts
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

# --- assistant speed tuning (all overridable from .env) ---
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")      # keep the model loaded in memory
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))       # smaller context = faster first token
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "800"))
ASSISTANT_CACHE_TTL = int(os.getenv("ASSISTANT_CACHE_TTL", "600"))
