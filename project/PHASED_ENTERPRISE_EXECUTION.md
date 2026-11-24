# SENTINEL-X — phased enterprise upgrade and execution

## What is included in this package
This is an additive upgrade over the existing Labs 1–4 and 7–18 package. Labs 5 and 6 remain excluded. The existing named MongoDB volumes in `docker-compose.yml` are retained. The package does not contain `.env` credentials or runtime database backup archives.

### Phase 1 — LabOps and Boss foundation
- Existing allow-listed experiment registry remains the only executable lab surface.
- Existing background jobs persist output and history in MongoDB; the UI restores the selected output.
- New `/api/enterprise/registry` and `/api/enterprise/jobs` endpoints expose the catalogue and job history.
- Boss retains the controlled tool allow-list. No arbitrary shell or arbitrary database execution is granted.

### Phase 2 — database intelligence and SOC analytics
- New bounded, read-only data endpoints: `/api/enterprise/query/mongo`, `/api/enterprise/query/cassandra`, `/api/enterprise/query/neo4j`.
- New explainable IOC correlation and transaction anomaly scoring primitives.
- Existing RAG pipeline remains available for Lab 17. It is not silently re-indexed: indexing a large codebase or datasets must be explicitly run and capacity-checked.
- Cross-database analytics are exposed as safe query building blocks, not an unrestricted federated query engine.

### Phase 3 — infrastructure, security and resilience
- `/api/enterprise/infrastructure` performs read-only service reachability checks.
- Admin-only audit feed at `/api/enterprise/audit`; data reads and exports are recorded.
- Container lifecycle control is intentionally disabled in this package. A Docker socket mounted into the API would grant host-level control; production deployment should use a separately authenticated host agent with a narrow allow-list.
- Job execution still uses the existing in-process runner. It is persistent in MongoDB but not a durable distributed worker queue; restart marks active jobs interrupted and does not replay them. Scheduling and isolated workers remain a follow-on deployment step.

### Phase 4 — delivery and operations
- GitHub Actions CI workflow, syntax compilation, tests, and CSV job-history export.
- Backup and restore PowerShell scripts. Restore requires an explicit `RESTORE` confirmation.
- This is a local deployment package, not a claim of production certification. TLS, external secrets, tenant isolation review, load testing, durable worker queue, alert delivery and disaster-recovery drills are required before production.

## Data preservation rules
1. Keep the existing `.env` file outside this ZIP and copy it back only after extraction.
2. Do not run `docker compose down -v`, `docker volume prune`, `docker system prune --volumes`, `docker volume rm`, or delete Docker Desktop/WSL data.
3. Do not change the `name:` or named volume mappings in `docker-compose.yml` unless you intentionally map the existing volume names.
4. Do not run Lab 16 seed again against populated databases. Lab 16 is destructive.
5. Lab 18's historical Cassandra full-table count failure must be reviewed before rerunning it. No lab is auto-started during installation.

## Install / execute (PowerShell)
Run from the current project directory after making a normal file backup:
```powershell
# 1) Confirm project and volume names before changing files
docker compose config --volumes
docker volume ls

# 2) Extract this ZIP to a NEW staging directory first.
#    Compare docker-compose.yml and .env.example with your current versions.
#    Preserve your existing .env and current volume names.

# 3) Copy only the upgraded application files into the project after review.
#    Do not overwrite .env. Do not replace compose volume names.
#    Then rebuild only the API service:
docker compose up -d --build api

# 4) Check health and OpenAPI
Invoke-RestMethod http://localhost:8000/health
Start-Process http://localhost:8000/docs
Start-Process http://localhost:8000/console?page=labs
Start-Process http://localhost:8000/console?page=assistant
```

## New API examples
All endpoints require a signed-in JWT. Use Swagger UI at `/docs` to authorize first.
- `GET /api/enterprise/registry`
- `GET /api/enterprise/jobs?limit=50`
- `GET /api/enterprise/infrastructure`
- `GET /api/enterprise/audit` (admin)
- `POST /api/enterprise/query/mongo` body: `{"dataset":"threats","limit":20}`
- `POST /api/enterprise/query/cassandra` body: `{"table":"threat_by_id"}`
- `POST /api/enterprise/query/neo4j` body: `{"query_id":"threat_counts"}`
- `GET /api/enterprise/reports/labs.csv` (admin)

## Important limitations and next engineering steps
- The UI's existing live console and persisted job log remain the execution surface; this upgrade adds job history/query APIs but does not pretend to provide a distributed worker queue.
- Boss remains an allow-listed tool agent; tool-calling is not arbitrary computer control. Add each new operation as a typed, tested tool with role checks and audit logging.
- IOC correlation and transaction anomaly scoring are pure, explainable utilities; connect them to your live collection schema only after verifying field names and indexes.
- RAG corpus-wide indexing needs a separate incremental indexer, chunk lifecycle, embeddings cost controls, and an evaluation set. Do not index large datasets blindly.
- Container start/stop/restart requires a dedicated host agent. Do not mount `/var/run/docker.sock` into the API container.
- Millisecond response targets are realistic for UI acknowledgements and small indexed database reads, not Gemma 4 12B generation, embeddings, or long-running labs.
