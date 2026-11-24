# SENTINEL-X Boss — Hybrid AI Upgrade

## What this upgrade changes

- Local fast route: Ollama `qwen3.5:4b` for short/simple questions.
- Cloud reasoning route: Ollama Cloud `gemma4:31b` for longer prompts and coding, debugging, architecture, upgrade and lab questions.
- Fallback: if the preferred route fails before a response starts, Boss tries the other configured route.
- Project-file retrieval: lexical retrieval over safe text files in the current workspace (`labs/`, `backend/`, docs and frontend). `.env`, keys, certificates, backups and generated directories are excluded. Retrieved passages are supplied to the model with their file paths.
- Live Lab 16 count: a question such as “How many records are in Lab 16?” queries `cti_hybrid.threats` in MongoDB and reports the actual count.
- Existing allow-listed lab tools, admin checks, confirmation gates, conversation history and streaming UI remain in place.

This is a hybrid routing and lexical project-retrieval upgrade, not an unrestricted autonomous coding agent. Boss can inspect retrieved source and propose fixes; existing experiment execution remains governed by the registered allow-list and admin confirmation. Do not interpret a model-generated answer as proof a code change or lab run happened.

## Security

A previously shared API key must be revoked and replaced before enabling cloud routing. Do not put an API key in source code, frontend JavaScript, a ZIP archive, screenshots, or chat. Keep it only in the local `.env` file, which is ignored by Git and excluded from this ZIP.

## Windows setup

From PowerShell in the extracted project root:

```powershell
ollama pull qwen3.5:4b
.\scripts\SETUP_BOSS_HYBRID.ps1
```

The setup script prompts for the NEW rotated API key with hidden input and writes it to `.env`. It creates a timestamped `.env` backup and never prints the key.

Then validate and rebuild only the API service:

```powershell
docker compose config --quiet
docker compose up -d --build api
docker compose ps api
docker compose logs --tail=80 api
```

Do not run `docker compose down -v`, `docker volume prune`, or `docker system prune --volumes`.

## Verify

1. Open `http://localhost:8000` and sign in.
2. Ask a short general question; it should route to local Qwen.
3. Ask a detailed coding/debugging or lab question; it should prefer Ollama Cloud when the key is configured.
4. Ask “How many threat records are in Lab 16?”; the answer must show the live count from `cti_hybrid.threats`, not an assumed target value.
5. If cloud is unavailable, the router attempts local fallback. If local Ollama is unavailable, it attempts cloud fallback when configured.

Authenticated status endpoint: `GET /api/assistant/status`. It reports whether the local model is present and whether cloud credentials are configured; `cloud_configured` means a key is present, not that a live cloud request has been tested.

## Model/API configuration

- Local Ollama URL inside Docker: `http://host.docker.internal:11434`
- Local model: `qwen3.5:4b`
- Cloud API base: `https://ollama.com/api`
- Cloud model: `gemma4:31b`
- Cloud authorization: `Authorization: Bearer <OLLAMA_API_KEY>`

The key is read only by the backend from environment configuration. The cloud route uses Ollama's native `/api/chat` streaming protocol, while the local route uses the local `/api/chat` endpoint.
