# SENTINEL-X — Complete Technical and Execution Guide

## Docker Hub Images

- **AI Chatbot Assistant:** https://hub.docker.com/repository/docker/venkatateja718/nosql-labs-suite/general
- **Ollama Docker Image:** https://hub.docker.com/r/ollama/ollama

## Docker Hub Links


## Project Docker Hub: Not published/verified

## 1. Project overview

Integrated threat-intelligence platform. Confirm each feature against the actual backend routes, frontend and Compose configuration.

## 2. Technologies detected

- CSS
- Docker / Docker Compose
- HTML
- JavaScript
- MongoDB-related files detected
- Python
- Python dependency management

## 3. Component map

- `backend/` — inspect its source/configuration for the implemented responsibilities.
- `frontend/` — inspect its source/configuration for the implemented responsibilities.
- `docker/` — inspect its source/configuration for the implemented responsibilities.
- `k8s/` — inspect its source/configuration for the implemented responsibilities.
- `scripts/` — inspect its source/configuration for the implemented responsibilities.
- `docs/` — inspect its source/configuration for the implemented responsibilities.

## 4. Prerequisites

- Windows 10/11 and PowerShell.
- Docker Desktop with Linux containers enabled.
- Git for cloning/updating.
- Python if running backend outside Docker.
- Ollama and the configured model(s), if local LLM functionality is enabled.
- Credentials only for integrations explicitly enabled in configuration.

## 5. Environment setup

1. Inspect .env.example, docker-compose.yml and backend settings.
2. Create a local .env using the variable names required by the application.
3. Never commit .env, tokens, passwords, database keyfiles, certificates or backups.
4. Confirm host ports, service names, database URIs and model names from the Compose file.

## 6. Start the core stack

```powershell
Set-Location "V:\NoSQL\SENTINELX-LOCAL\github-upload\SENTINEL-X"
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail 100
```

## 7. Verify API and database

```powershell
docker compose ps
docker compose logs --tail 100 api
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/openapi.json
```

Run endpoint checks only when those routes exist in the current backend. Check MongoDB container health and replica-set status using the connection details configured in Compose.

## 8. LLM, embeddings, vector search and RAG

Document the exact LLM provider/model, embedding model, chunking logic, MongoDB database/collection, vector index, chat route, request schema and history storage after confirming them in source. A model name or dependency alone does not prove that a feature is wired and operational.

## 9. Frontend and deployment

- Check frontend API base URL and backend CORS configuration.
- Static hosting alone cannot run FastAPI, MongoDB, Docker Compose or a local Ollama server.
- A public frontend needs a separately deployed, reachable and secured backend.
- Do not expose unauthenticated MongoDB ports publicly.

## 10. Monitoring and troubleshooting

```powershell
docker compose ps
docker compose logs -f api
docker compose logs --tail 200
docker stats
Test-NetConnection localhost -Port 8000
```

Check Docker engine, environment variables, port conflicts, container health, MongoDB initialization, LLM availability and API logs.

## 11. Safe shutdown

```powershell
docker compose stop
# Or remove containers/network while preserving named volumes:

## Docker Hub Images

- **AI Chatbot Assistant:** https://hub.docker.com/repository/docker/venkatateja718/nosql-labs-suite/general
- **Ollama Docker Image:** https://hub.docker.com/r/ollama/ollama

## Docker Hub Links


## Project Docker Hub: Not published/verified
docker compose down
# Do not append -v for routine shutdown.

## Docker Hub Images

- **AI Chatbot Assistant:** https://hub.docker.com/repository/docker/venkatateja718/nosql-labs-suite/general
- **Ollama Docker Image:** https://hub.docker.com/r/ollama/ollama

## Docker Hub Links


## Project Docker Hub: Not published/verified
```

## 12. Source inventory

- `.dockerignore`
- `backend\agent.py`
- `backend\assistant_stream.py`
- `backend\assistant_stream.py.backup`
- `backend\assistant_tools.py`
- `backend\assistant_tools.py.backup`
- `backend\auth.py`
- `backend\bootstrap_admin.py`
- `backend\bootstrap_datasets.py`
- `backend\chat.py`
- `backend\common.py`
- `backend\config.py`
- `backend\conversations.py`
- `backend\dashboard.py`
- `backend\enterprise_ops.py`
- `backend\hybrid.py`
- `backend\ingest.py`
- `backend\k8s_jobs.py`
- `backend\knowledge.py`
- `backend\lab_jobs.py`
- `backend\labs_api.py`
- `backend\main.py`
- `backend\main.py.backup`
- `backend\main.py.pre-enterprise.bak`
- `backend\model_router.py`
- `backend\monitor.py`
- `backend\overview.py`
- `backend\project_knowledge.py`
- `backend\promote_admin.py`
- `backend\rag.py`
- `backend\requirements.txt`
- `backend\saas.py`
- `backend\scanner_bot.py`
- `backend\security_center.py`
- `backend\security_utils.py`
- `backend\seed_demo.py`
- `backend\sync_service.py`
- `backend\threat_correlation.py`
- `backend\threats.py`
- `backend\transaction_intelligence.py`
- `docker\k8s\mongo.yaml`
- `docker\lab_runner.py`
- `docker\replica-set\docker-compose.prod.yml`
- `docker\replica-set\docker-compose.prod.yml.backup`
- `docker\replica-set\docker-compose.yml`
- `docker\replica-set\keyfile`
- `docker\sharding\bootstrap.sh`
- `docker\sharding\docker-compose.yml`
- `docker\sharding\register.sh`
- `docker\tls\certs\ca.crt`
- `docker\tls\certs\client.pem`
- `docker\tls\certs\server.pem`
- `docker\tls\docker-compose.yml`
- `docker\tls\gen_certs.py`
- `docker-compose.yml`
- `Dockerfile`
- `docs\ARCHITECTURE.md`
- `docs\README_original.md`
- `docs\RESUME.md`
- `frontend\css\app.css`
- `frontend\css\app.css.backup`
- `frontend\css\app.css.v1-backup`
- `frontend\enterprise.html`
- `frontend\js\app.js`
- `frontend\js\app.js.backup`
- `frontend\js\app.js.v1-backup`
- `frontend\legacy\chat.html`
- `frontend\legacy\dashboard.html`
- `frontend\legacy\index.html`
- `k8s\lab16-job.yaml`
- `k8s\lab18-job.yaml`
- `README.md`
- `requirements.txt`
- `scripts\backup.ps1`
- `scripts\backup-preserve.ps1`
- `scripts\restore-preserve.ps1`
- `scripts\run_lab16_then_lab18.ps1`
- `scripts\SETUP_BOSS_HYBRID.ps1`
- `scripts\smoke_test.ps1`

## 13. Security checklist

- [ ] Revoke and rotate any credential previously exposed.
- [ ] .env and private keys are excluded from Git.
- [ ] MongoDB is not publicly exposed without authentication/TLS.
- [ ] Production API uses authentication, rate limits and HTTPS.
- [ ] Logs do not disclose credentials.



