# SENTINEL-X Enterprise LabOps Upgrade

## Included
- Website lab catalogue for Labs 1–4 and 7–18 (Labs 5 and 6 intentionally excluded).
- Labs 1–4 source activities imported from the supplied Exercise 1–4 archives.
- Admin-only, allowlisted background lab execution with a single active job at a time.
- Live console polling, persistent job output in MongoDB, last-run restoration after page refresh, and downloadable logs.
- Boss assistant can launch registered labs, report job IDs, answer live threat questions, and query the Lab 10 transaction collection.
- Ollama model remains configured by environment; default is gemma4:12b.
- Lab 18 avoids a Cassandra full-table COUNT(*); it reports the nodetool partition estimate and confirms Cassandra with a bounded sample query.

## Deployment into an existing local project
1. Back up the project source folder (do not remove or recreate Docker volumes).
2. Merge this package's `backend/`, `frontend/`, `labs/`, `Dockerfile`, `docker-compose.yml`, `pytest.ini`, and `ENTERPRISE_LABOPS_UPGRADE.md` into the existing project. Preserve the existing `.env` and all Docker volumes.
3. Keep `OLLAMA_MODEL=gemma4:12b` and `OLLAMA_URL=http://host.docker.internal:11434` in the existing `.env`.
4. From the project root run `docker compose up -d --build api`. This rebuilds/restarts only the API service and does not remove MongoDB, Cassandra, Neo4j, or Atlas Local volumes.
5. Verify with `Invoke-RestMethod http://localhost:8000/health` and sign in as an administrator. Open `/console?lab=1` and `/console?page=assistant`.

## Runtime behavior and safety
- The API executes only scripts explicitly registered in `backend/dashboard.py`; it does not expose arbitrary shell or database commands to Boss.
- Lab runs are serialized. A second run is rejected while another job is queued/running.
- Data-changing registered labs display a confirmation warning. Lab 16 is still destructive and must not be rerun unless its data is disposable.
- Lab 11, Lab 12 and Lab 13 require their dedicated infrastructure stacks and credentials. The API mounts the TLS test certificate directory read-only. The web runner does not mount the host Docker socket; start those isolated stacks using their documented prerequisites before launching the registered script. Lab 9.2 network partition remains a documented infrastructure operation because it requires Docker network control.
- Boss answers simple built-in/database queries immediately; Gemma 4 12B generation and long-running labs stream progressively and cannot be guaranteed to finish in milliseconds.
- Job logs are persisted in MongoDB `lab_jobs`; an API restart marks an active job `interrupted` and never silently reruns it.

## Verification
`python -m pytest -q` and `node --test tests/frontend_logic.test.js` are the package checks.
