# SENTINEL-X Offline Assistant – configuration and safe operation

## Configure the installed local model

This project defaults to `gemma4:12b` and `nomic-embed-text`. The model must exist in the Windows Ollama installation.

In PowerShell, from `threat_intelligence_platform`, run:

```powershell
ollama list
ollama pull nomic-embed-text
powershell -ExecutionPolicy Bypass -File .\FIX_OLLAMA_MODEL.ps1
docker compose up -d --force-recreate api
```

The script updates only `OLLAMA_MODEL` in `.env`; it does not touch `JWT_SECRET` or MongoDB data.

The API container reaches Ollama through `http://host.docker.internal:11434`. Keep Ollama running on Windows. Verify with:

```powershell
docker compose exec api python -c "import os,requests; u=os.getenv('OLLAMA_URL','http://host.docker.internal:11434'); print(u); print(requests.get(u+'/api/tags',timeout=5).status_code)"
```

Open `/api/assistant/status` to see whether the configured model is available.

## Assistant capabilities

- General local Q&A through Ollama `/api/chat`.
- Context-aware answers using the selected lab, lab dependency map, threat/source counts and recent experiment output.
- Browser chat history is retained per workspace in local storage.
- Error diagnosis for pasted Docker, Python, FastAPI, MongoDB and Ollama errors.
- Execution of experiments registered in `backend/dashboard.py`.
- Destructive experiments require the explicit `confirm <experiment-id>` response after the assistant explains the warning.

## Safety and honest limitations

This is a local project copilot, not an unrestricted autonomous system administrator. It does not execute arbitrary PowerShell, edit arbitrary project files, delete databases, or claim an operation succeeded without a server-side result. It can explain a code/config patch and run only the allowlisted experiment scripts. Labs with dedicated sharding, TLS/keyfile, Cassandra, Neo4j or Atlas Local infrastructure still require those services and their prerequisites.

For an API or UI failure, inspect:

```powershell
docker compose logs api --tail=100
docker compose ps -a
```

Do not use `docker compose down -v` when you need to preserve lab or threat data.
