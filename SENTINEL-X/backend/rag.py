import os

import requests
from pymongo import MongoClient

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
from config import EMBED_MODEL, OLLAMA_MODEL as LLM_MODEL  # single source of truth for model names
VECTOR_MONGO_URI = os.getenv(
    "VECTOR_MONGO_URI",
    "mongodb://admin:pass123@localhost:27777/?authSource=admin&directConnection=true",
)
vector_client = MongoClient(VECTOR_MONGO_URI, serverSelectionTimeoutMS=5000)
vector_db = vector_client["cti_lab17"]

PLATFORMS = {
    "windows": "Windows",
    "linux": "Linux",
    "macos": "MacOS",
    "android": "Android",
    "ios": "iOS",
}
STATUSES = {
    "anticipated": "Anticipated",
    "active": "Active",
    "evolving": "Evolving",
    "resolved": "Resolved",
}


def _canonical_filter(value, allowed, field):
    if value is None or not value.strip():
        return None
    canonical = allowed.get(value.strip().casefold())
    if canonical is None:
        raise ValueError(f"Unsupported {field}: {value}")
    return canonical


def normalize_platform(value):
    return _canonical_filter(value, PLATFORMS, "platform")


def normalize_status(value):
    return _canonical_filter(value, STATUSES, "status")


def ask_threat_intel(query: str, platform: str = None, status: str = None):
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": query},
        timeout=120,
    )
    response.raise_for_status()
    query_vector = response.json().get("embedding")
    if not query_vector:
        return "Error: Could not generate embeddings."

    filters = {}
    canonical_platform = normalize_platform(platform)
    canonical_status = normalize_status(status)
    if canonical_platform:
        filters["platform"] = canonical_platform
    if canonical_status:
        filters["status"] = canonical_status

    search_stage = {
        "index": "vector_index_lifecycle",
        "path": "embedding",
        "queryVector": query_vector,
        "numCandidates": 20,
        "limit": 3,
    }
    if filters:
        search_stage["filter"] = filters

    results = list(
        vector_db.threat_chunks.aggregate(
            [
                {"$vectorSearch": search_stage},
                {
                    "$project": {
                        "text": 1,
                        "platform": 1,
                        "status": 1,
                        "_id": 0,
                    }
                },
            ]
        )
    )
    if not results:
        return f"No threats found matching criteria (Platform: {platform}, Status: {status})."

    context = "\n".join([r.get("text", "") for r in results])
    prompt = f"Using ONLY the following verified intelligence, answer the query.\n\nContext:\n{context}\n\nQuestion: {query}"
    llm_response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=300,
    )
    llm_response.raise_for_status()
    return llm_response.json().get("response", "Error generating response.")