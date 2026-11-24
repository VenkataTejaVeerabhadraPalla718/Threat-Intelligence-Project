# SENTINEL-X â€” Threat Intelligence & NoSQL Operations Platform

## Docker Hub: https://hub.docker.com/r/venkatatejaveerabhadra718/nosql-labs-suite

FastAPI + MongoDB replica set (`rs0`: mongo1:27117, mongo2:27118, mongo3:27119) + local Ollama + a single-page enterprise console.
Command labels: ðŸ”µ PowerShell / Docker (no `.venv`) Â· ðŸŸ¢ Python (`.venv` required) Â· ðŸŸ  Browser.

## 1. First-time start
ðŸ”µ From the project folder (Docker Desktop must be running):
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\START_SENTINELX_FRESH.ps1
```
It creates `.env` only if missing (random `JWT_SECRET`), validates Compose, builds, starts, and waits for `/health`. Existing volumes are reused. **Never** run `docker compose down -v`, `docker volume prune` or `docker system prune` â€” they delete your data.

## 2. Create the first administrator
ðŸ”µ Password input is hidden; nothing is stored in files.
```powershell
docker exec -it sentinelx-local-api python /app/backend/bootstrap_admin.py
```
If the username already exists it is promoted without changing its password. Self-registration always creates a plain **User**; only an admin can promote accounts (Administration â†’ User management).

## 3. URLs
| Purpose | URL |
|---|---|
| ðŸŸ  Sign in | http://localhost:8000/login |
| ðŸŸ  Register | http://localhost:8000/register |
| ðŸŸ  Console | http://localhost:8000/console |
| ðŸŸ  API docs | http://localhost:8000/docs |
| ðŸŸ  Health | http://localhost:8000/health |

## 4. Daily commands
ðŸ”µ
```powershell
docker compose up -d                 # start / restart (frontend/backend edits: docker compose up -d --build api)
docker compose ps                    # api should show (healthy)
.\CHECK_SENTINELX.ps1                # diagnostics
docker compose logs --tail=80 api
docker compose stop                  # stop without deleting anything
```
Rebuilding only `api` does not recreate the MongoDB containers.

## 5. AI assistant (fast, ChatGPT-style) & Ollama
ðŸ”µ Install Ollama for Windows, then:
```powershell
ollama pull gemma4:12b
ollama pull nomic-embed-text
```
**How it answers quickly** (`docs/ARCHITECTURE.md`): (1) *instant tier* â€” definitions (replica set, sharding, write concern, Labs 7â€“18â€¦) and live tools (system health, latest threats, lab status/output, security summary for admins) answer in milliseconds without the model; (2) *cache* â€” repeated questions; (3) *streaming* â€” other answers appear token-by-token with a Stop button and a latency badge. The model is preloaded at API start and kept warm.
For the fastest first token use a small model and, ideally, a GPU: set `OLLAMA_MODEL=llama3.2:3b` in `.env`, run `ollama pull llama3.2:3b`, then `docker compose up -d api`. A 12B model on CPU can take seconds before the first token â€” that is model speed, not the app.
The assistant **generates instructions only**; it can call allow-listed tools (read-only data; lab runs for admins with `confirm <id>` for destructive ones). No shell access, no arbitrary MongoDB commands.

## 6. Labs 7â€“18
ðŸŸ  Console â†’ **Experiments** (sidebar) â†’ Lab N. Each page shows prerequisites, procedure, registered experiments, manual commands, read-only script viewer, output, history chart and a lab-scoped assistant. Only admins can press **Run**. Labs needing extra stacks (sharding, TLS, Cassandra/Neo4j, Atlas Local) show their manual commands instead of running from the page. Lab 14.2 uses `docker exec`, which the API container cannot do; run it from the host with `$env:MONGO_CONTAINER="sentinelx-local-mongo1"`.

## 7. Verify the database
ðŸ”µ
```powershell
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "rs.status().members.map(m=>m.name+' '+m.stateStr)"
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "const d=db.getSiblingDB('cti'); printjson({users:d.users.countDocuments({}), audit:d.login_activity.countDocuments({}), threats:d.threats.countDocuments({})})"
```
MongoDB ports are published on `127.0.0.1` only (the replica set has no authentication).
Persistence check: ðŸ”µ `docker compose restart api` then sign in again â€” users and audit history remain.

## 8. Testing
ðŸŸ¢ Unit + frontend logic tests (no Docker needed):
```powershell
python -m unittest discover -s tests -v
node tests\frontend_logic.test.js
```
ðŸ”µ Live end-to-end API smoke test against the running stack (creates then deletes a throw-away user; asks for an admin login to also test admin features):
```powershell
.\scripts\smoke_test.ps1
```

## 9. Backup & recovery
ðŸ”µ
```powershell
.\scripts\backup.ps1        # writes backups\sentinelx-cti-<timestamp>.archive.gz
```
The script prints the matching `mongorestore` commands. Restore uses `--drop` on the `cti` collections, so back up first.

## 10. Troubleshooting
| Symptom | Fix |
|---|---|
| API exits: "Set JWT_SECRETâ€¦" | `.env` is missing/weak. Run `START_SENTINELX_FRESH.ps1` or set a 32+ character `JWT_SECRET`. |
| Login says "Too many failed attempts" | Lockout after 8 failures per username+IP for 15 min (`LOGIN_MAX_FAILURES`, `LOGIN_LOCKOUT_MINUTES`). |
| Everyone shows the same IP in the audit log | Docker Desktop on Windows NATs requests to the gateway address; this is expected locally. |
| Charts empty / "library unavailable" | The browser needs internet access to `cdn.jsdelivr.net` for Chart.js. |
| Assistant "OLLAMA OFFLINE" | Start Ollama; confirm `ollama list` shows `OLLAMA_MODEL`. |
| Threat counts include "demo" origin | Those are labelled synthetic records from `seed_demo.py`; filter by Origin on the Threat page. |
| Old password hashes | Existing PBKDF2 accounts keep working and are upgraded to Argon2id automatically at next login. |

## 11. What was verified (build environment) and what was not
Executed and passing (19+ security tests, knowledge-base tests): Python compile of all backend/lab files; import graph of all 17 backend modules (against stubbed third-party packages); 19 security unit tests (password policy, hashing incl. legacy-hash compatibility, CSV-injection, dates, lockout); 11 frontend logic checks (escaping, code blocks, login page has no branding/marketing); JS syntax; Compose YAML structure (no duplicate ports/container names, one network).
**Not executed (no network, Docker, MongoDB or FastAPI in the build sandbox):** `docker compose config/build/up`, live API calls, MongoDB queries/aggregations, Argon2 path, SSE streaming and Ollama responses, browser rendering and responsive layout. Run `scripts\smoke_test.ps1` after starting the stack to verify the API end-to-end, and report any failure.

The original README is preserved at `docs/README_original.md`; older guides remain in the project root.

## Boss â€” saved conversations
The assistant is named **Boss** and keeps ChatGPT-style saved chats (sidebar, resume, rename, pin, search, delete, export,
regenerate/edit, voice input). See `BOSS_UPGRADE_NOTES.md`.

## Boss hybrid AI upgrade

See [`BOSS_HYBRID_AI_SETUP.md`](BOSS_HYBRID_AI_SETUP.md) for the hybrid local/cloud model router, workspace file retrieval, Lab 16 live MongoDB count tool, secure API-key setup, and rebuild commands. Run `ollama pull qwen3.5:4b`, then `scripts/SETUP_BOSS_HYBRID.ps1` with a newly rotated Ollama key before rebuilding the API service.

