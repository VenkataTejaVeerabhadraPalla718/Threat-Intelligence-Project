# SENTINEL-X FINAL SUBMISSION BUILD

This is the final integrated project package based on the supplied project ZIP and the previously specified Claude requirements.

## Included final scope

- Labs 07–18 retained as separate workspaces, with the shared integration/evidence map.
- Executive overview and an individual workspace page for every Lab 07–18.
- Dark/light theme, responsive enterprise interface, charts and CSV/JSON downloads.
- Threat synchronization controls: 10 seconds, 30 seconds, 1 minute, 5 minutes, 10 minutes and 30 minutes.
- Scheduled incremental threat synchronization through the `threat-sync` service.
- Local Ollama assistant on the executive overview, the dedicated AI Assistant page and every individual lab page.
- Assistant conversation persistence, per-user/per-tenant isolation, conversation switching and New chat.
- Centered login/register UI, multi-user registration, JWT authentication, role checks and login audit.
- Lab 15's separate scan/mitigation chat workflow retained.
- Lab execution remains allow-listed; destructive experiments require confirmation and administrator access.
- Lab Output panels retain the last selected/successfully executed output across lab rerenders, navigation and browser refreshes; see `OUTPUT_PERSISTENCE_UPDATE.md`.

## Important architecture boundary

The labs are integrated through the central platform, shared threat intelligence and execution evidence. Labs 11–13, 16–18 still require their dedicated infrastructure (sharding, TLS/keyfile, Cassandra, Neo4j and Atlas Local/Ollama) where specified. The web assistant does not run arbitrary shell commands and does not pretend those prerequisites are present.

## Safe update on the existing Windows installation

1. Keep the current project folder and MongoDB data. Make a copy of the project folder before replacing files.
2. Extract this ZIP to a temporary folder.
3. Copy the extracted `threat_intelligence_platform` contents over the current project folder. The package intentionally does not include `.env`; keep your existing `.env` and never overwrite it with `.env.example`.
4. In PowerShell, enter the current project folder and verify the required environment values without displaying your JWT secret:

   ```powershell
   Get-Content .\.env | Where-Object { $_ -match '^(OLLAMA_URL|OLLAMA_MODEL|EMBED_MODEL|MONGO_URI)=' }
   ```

   Keep the known-good local Ollama values (`http://host.docker.internal:11434`, `gemma4:12b`, `nomic-embed-text`) if those are still the models installed on your machine.

5. Before rebuilding, compare the networks attached to the running API and MongoDB containers:

   ```powershell
   docker inspect sentinelx-local-api --format '{{range $name,$v := .NetworkSettings.Networks}}{{$name}} {{end}}'
   docker inspect sentinelx-local-mongo1 --format '{{range $name,$v := .NetworkSettings.Networks}}{{$name}} {{end}}'
   ```

   The API must share a Docker network with the MongoDB replica-set containers. Do not remove or recreate MongoDB containers or volumes. If the network names differ, stop here and resolve the existing network attachment before rebuilding.

6. When the existing API and MongoDB containers are on the expected Compose network, rebuild only the API (do not force-recreate the database):

   ```powershell
   docker compose up -d --build --no-deps api
   ```

   If the `threat-sync` service is not already running and is part of this same Compose project/network, start it separately:

   ```powershell
   docker compose up -d --build --no-deps threat-sync
   ```

   Do not start a second MongoDB stack from another project folder.

7. Verify the running services:

   ```powershell
   docker ps
   docker logs sentinelx-local-api --tail 80
   Invoke-RestMethod http://localhost:8000/health
   ```

8. Open `http://localhost:8000/login`, sign in with your existing account, and run the acceptance checks below.

## 15-minute acceptance checklist

- [ ] Login succeeds and the correct username/role is shown.
- [ ] Overview dashboard loads KPIs and charts.
- [ ] Theme toggle changes between dark and light.
- [ ] Threat Intelligence page loads and CSV export works.
- [ ] Sources page shows the configured sync interval; all six interval choices are available.
- [ ] The overview chatbot responds and shows `OLLAMA READY`.
- [ ] Each Lab 07–18 page opens and contains its lab-specific assistant.
- [ ] New chat starts a separate conversation; saved conversations can be selected.
- [ ] A regular user cannot run experiments; an administrator can run only registered experiments.
- [ ] A destructive experiment displays a warning/confirmation before execution.
- [ ] Lab 15's `/api/chat` scan/fix confirmation workflow remains available.
- [ ] `GET /api/assistant/status` reports `model_available: true`.

## Static checks completed for this package

- Python `compileall` passed for backend, Docker scripts and labs.
- Node syntax check passed for `frontend/js/app.js`.
- Existing frontend logic tests passed.
- Existing Python security tests passed (19 tests).
- Final integration acceptance tests passed (5 tests).

## Not claimed as verified

A fresh live Docker build and all twelve lab executions were not performed in the packaging environment. Some labs require additional services and destructive test data. Use the live checks above on the target Windows installation; do not claim all labs passed unless their recorded results show that.
