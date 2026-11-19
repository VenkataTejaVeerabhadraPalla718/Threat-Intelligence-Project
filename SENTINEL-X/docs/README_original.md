# SENTINEL-X | Enterprise Threat Intelligence & NoSQL Lab Platform

A distinct student-facing package based on the supplied Lab 7–18 project materials. It contains a FastAPI threat dashboard, a lab dashboard, MongoDB replica-set configuration, threat ingestion, a 20,000-record synthetic demonstration corpus, and the retained Lab 7–18 experiment scripts. The local Ollama chatbot is optional/secondary.

## Windows 11 execution (16 GB RAM)

### A. Prerequisites
- Docker Desktop running in **Linux containers** mode.
- Docker Compose v2 (`docker compose version`).
- 16 GB RAM; close memory-heavy applications.
- Ollama is not required to start the website or run Labs 7–16.

### B. Prepare
1. Extract the ZIP to `B:\Projects\SENTINEL-X`.
2. Open the extracted `threat_intelligence_platform` folder in VS Code.
3. In PowerShell, change into that folder.
4. Create the local environment file:
   ```powershell
   Copy-Item .env.example .env
   ```
5. Set a new local JWT secret (if `.env.example` contains `CHANGE_ME`):
   ```powershell
   $secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
   (Get-Content .env) -replace 'CHANGE_ME', $secret | Set-Content .env
   ```

### C. Start core services (chatbot not needed)
```powershell
docker compose up --build -d
docker compose ps -a
```
Wait for `mongo-init` to complete successfully and for `api` to show `Up`. Check logs if needed:
```powershell
docker compose logs --tail=100 mongo-init api seed-demo
```

Open these URLs:
- Main threat dashboard: http://localhost:8000/
- Labs dashboard: http://localhost:8000/dashboard
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### D. Optional local chatbot (secondary)
Your installed model is `gemma4:12b`. The project config uses that model name. For embeddings, install the separate model:
```powershell
ollama pull nomic-embed-text
ollama list
```
Keep Ollama running on Windows. The API container reaches it using `host.docker.internal:11434`. The chatbot/vector workflow may require Atlas Local and Lab 17 index initialization; do not treat chatbot readiness as a prerequisite for the core dashboard.

### E. Optional databases for multi-database labs
Only start these when needed; running all databases simultaneously can exceed available memory:
```powershell
docker compose --profile graph up -d
docker compose --profile vector up -d
```
Stop optional services when finished:
```powershell
docker compose --profile graph --profile vector stop
```

## Data and synchronization
- The seed utility creates a 20,000-record **synthetic demonstration corpus**. These records are not verified real-world incidents or IOCs. They are labelled as demo data.
- RSS ingestion requires internet access. Feed records are source-attributed but should not be described as confirmed malicious indicators without independent validation.
- The sync service is intended to upsert/deduplicate records and preserve existing data. Check its logs and database counts after running it.
- Do not run destructive seed/migration scripts against data you need to preserve.

## Labs 7–18: recommended execution order

Run labs in order, one at a time, and use the lab dashboard/API where provided. The experiment files are retained under `labs/lab07` through `labs/lab18`. Some labs require optional database profiles or lab-specific setup. **They are not one single atomic workflow and not every experiment is launched automatically by the root Compose file.** Read each script's header and the corresponding lab notes before executing it. In particular:
- Labs 7–10: MongoDB analysis, replication, write concern/partition and transaction demonstrations.
- Labs 11–13: sharding, access control/TLS and authenticated failover; some require their dedicated Docker configurations.
- Labs 14–15: monitoring, backup/restore verification, tenant and migration exercises.
- Lab 16: multi-database model/seed; start Cassandra/Neo4j only when needed.
- Lab 17: vector/RAG pipeline; start Atlas Local and initialize the index.
- Lab 18: benchmark; run after the required databases and seed data are ready.

Use the lab scripts' own arguments and prerequisites. Do not run all labs concurrently on this laptop.

## Dashboard appearance
The dashboard uses a dark cyber-operations theme with chart panels, KPI cards, severity visualizations, source/threat lists and lab-specific panels, following the visual reference supplied for this project. Chart values reflect the connected dataset; demo corpus values are labelled synthetic.

## Troubleshooting
```powershell
docker compose ps -a
docker compose logs --tail=150 api
docker compose logs --tail=150 mongo-init
docker compose logs --tail=100 seed-demo
```
Health endpoint: `http://localhost:8000/health`.

Safe restart (keeps volumes):
```powershell
docker compose down
docker compose up --build -d
```
**Do not use `docker compose down -v`** unless you intentionally want to delete all database volumes.

## Academic integrity and limitations
This is a student demonstration platform, not a production SOC or automated remediation product. Synthetic data must be identified as synthetic. Retained lab scripts should be understood and demonstrated individually. No software package can guarantee full marks or guarantee a bug-free run on a machine that has not been tested with its exact Docker Desktop, network and system configuration. Follow your course's collaboration and attribution rules and personalize your own explanations and report.


## Offline assistant configuration

See [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md). For the installed Gemma 4 model, run `powershell -ExecutionPolicy Bypass -File .\\FIX_OLLAMA_MODEL.ps1`, then `docker compose up -d --force-recreate api`. This script preserves your JWT secret and database volumes.
