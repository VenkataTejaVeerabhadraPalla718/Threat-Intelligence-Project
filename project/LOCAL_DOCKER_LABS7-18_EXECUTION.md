# SENTINEL-X — Local Docker Edition (Labs 7–18 + Boss)

## What this edition changes
- Uses a new Compose project name `sentinelx-local` and project-owned volumes (`sentinelx-local-mongo*-data`), rather than requiring your friend's `sentinelx-fresh_*` external volumes.
- Adds an idempotent bootstrap job: 40,000 labelled synthetic Lab 7 CTI demo rows and 200,000 labelled synthetic Lab 10 transaction records.
- Raises the Lab 16 polyglot seed target to 300,000 records per database; Lab 18 benchmark requires 300,000 per database.
- Sets the Lab 17 vector benchmark target to 300,000 vectors.
- Preserves the Boss assistant and conversation UI from the supplied BOSS archive.

## Data integrity / important truth
The 40k/200k/300k targets are synthetic academic demonstration datasets, not 40k/200k/300k independently verified live threat reports. Live RSS sync remains a separate incremental process; its actual volume depends on feed availability and historical feed retention. The bootstrap uses deterministic IDs, upserts, and dataset tags; it does not delete existing rows. Lab 16's original script intentionally resets its own dedicated `cti_hybrid.threats`, Cassandra tables and Neo4j default graph before reseeding; run only after backing up any data in those lab-specific targets.

Lab 17 uses Atlas Local and the Ollama embedding service. Its 300k vector workload can be memory- and disk-intensive. Do not run it together with Lab 16 or all other labs. Execute sequentially and monitor Docker Desktop memory/disk.

## 0. Before starting
- Start Docker Desktop and wait until the Linux engine is running.
- Keep Ollama running on Windows. `ollama list` must show `gemma4:12b` and `nomic-embed-text`.
- Extract this ZIP to a folder on V:, e.g. `V:\NoSQL\SENTINELX-LOCAL`.
- Open PowerShell in the `threat_intelligence_platform` folder.

## 1. Configure .env
The included `.env` is a safe template, not a real secret. Generate a new JWT secret:
```powershell
$secret = -join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
(Get-Content .env) -replace '^JWT_SECRET=.*$', "JWT_SECRET=$secret" | Set-Content .env
```
Review `OLLAMA_MODEL` against `ollama list`. If using another model, update `.env`.

## 2. Validate and start core stack
```powershell
docker compose config --services
docker compose config
docker compose up -d --build mongo1 mongo2 mongo3 mongo-init api seed-demo bootstrap-datasets threat-sync
docker compose ps -a
```
This starts the core MongoDB replica set, API, initial demo seed, local Lab 7/10 data bootstrap, and automatic incremental threat feed sync. The bootstrap container exits with code 0 after seeding; that is expected.

## 3. Verify health and datasets
```powershell
Invoke-RestMethod http://localhost:8000/health
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "const d=db.getSiblingDB('cti'); printjson({lab7Synthetic:d.threats.countDocuments({dataset_tag:'lab7_synthetic_demo'}),lab10Transactions:d.getSiblingDB('lab10_transactions').records.countDocuments({dataset_tag:'lab10_consistency_demo'}),liveRSS:d.threats.countDocuments({record_origin:'live_rss'})})"
```
The `lab10_transactions` database query in the preceding command is best run separately if your mongosh version does not allow cross-db access through `d`; use:
```powershell
docker exec sentinelx-local-mongo1 mongosh --port 27117 --quiet --eval "print(db.getSiblingDB('lab10_transactions').records.countDocuments({dataset_tag:'lab10_consistency_demo'}))"
```

## 4. Create admin and open Boss
```powershell
docker exec -it sentinelx-local-api python /app/backend/bootstrap_admin.py
```
Open:
- `http://localhost:8000/login`
- `http://localhost:8000/console`
- `http://localhost:8000/console?page=assistant`
- `http://localhost:8000/console?page=labs`
- `http://localhost:8000/docs`

## 5. Labs 7–18 execution
The UI lists registered experiments and manual steps. Some advanced labs require optional infrastructure:
- Lab 11: sharding stack (`docker/sharding`)
- Lab 12: TLS/RBAC stack (`docker/tls`)
- Lab 16: Cassandra + Neo4j optional graph profile, then run the Lab 16 seed.
- Lab 17: Atlas Local vector profile and Ollama embedding model.
- Lab 18: requires Lab 16's 300k records to exist in MongoDB, Cassandra and Neo4j.

Optional infrastructure:
```powershell
docker compose --profile graph up -d cassandra neo4j
docker compose --profile vector up -d atlas-local
```
Do not start graph/vector profiles simultaneously with heavy workloads if Docker memory is constrained. The Lab 16 seed is destructive to its dedicated Lab 16 datasets; back up first and use the dashboard's explicit confirmation.

## 6. Lab 16 and 18
Ensure graph profile services are healthy, then from the project root run the registered lab action through the Boss/Labs UI. The 300k Lab 16 workload is large and can take a long time. Run it alone. Lab 18 is read-only and should run only after counts are verified.

## 7. Lab 17
The vector benchmark has a 300k target and is resource-heavy. Run Atlas Local first and check free Docker memory/disk. If your system cannot sustain it, lower `LAB17_TARGET_RECORDS` in `.env` and rebuild/recreate only the relevant workload; do not claim 300k unless the count check confirms it.

## 8. Monitoring / logs
```powershell
docker compose ps -a
docker compose logs --tail=100 api
docker compose logs --tail=100 threat-sync
docker compose logs --tail=100 bootstrap-datasets
docker stats --no-stream
```
Stop without deleting data:
```powershell
docker compose stop
```
Never use `docker compose down -v`, `docker volume prune`, or `docker system prune --volumes`.

## Known scope limits
- Compose's core stack does not automatically start every optional per-lab stack (sharding, TLS, Cassandra, Neo4j, Atlas Local).
- The supplied code's RSS sync fetches current feed items; it does not guarantee 40,000 real articles. The 40,000 target here is clearly tagged synthetic demo data.
- Lab 17.2's benchmark script target is adjusted; the full 300k execution is not pre-run in this ZIP.
- Docker build/start, live RSS network access, Ollama inference, and actual 300k multi-database insertion must be verified on your machine after extraction. This ZIP does not claim those have already succeeded.
