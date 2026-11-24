# SENTINEL-X Cross-Lab Integration (Labs 7–18)

## What is connected
- Every lab has a workspace in the enterprise console.
- Registered experiment runs are recorded in the shared MongoDB `cti.experiment_runs` collection and appear in executive and lab dashboards.
- Threat-intelligence records and source counts are shared through the central `cti.threats` and `cti.sources` collections where a lab consumes CTI data.
- The assistant receives the selected lab number, its dependency description, shared dataset counts, and the five latest experiment outputs.
- The assistant can start only registered, allowlisted experiments. Destructive operations require explicit confirmation in the lab workspace.
- `/api/dashboard/integration` reports the relationship map and current evidence counts.

## Important boundary
The labs are integrated at the platform/orchestration/evidence layer, not all merged into one database. Labs 11–13 use dedicated sharding/security/keyfile configurations; Lab 16 uses MongoDB, Cassandra and Neo4j; Lab 17 uses Atlas Local and Ollama; Lab 18 benchmarks the prepared multi-database datasets. These remain separate services with explicit prerequisites.

## Chatbot commands
- `Explain Lab 8 and its dependency on Lab 13`
- `Run Lab 7` (runs the first safe registered Lab 7 experiment)
- `Diagnose this error: <paste traceback>`
- `What must be running before Lab 16?`
- `Summarize the last failed run in Lab 14`

For labs requiring dedicated infrastructure, `Run Lab N` returns the exact documented manual prerequisite steps instead of claiming an unsafe automatic execution.

## Verification endpoints
- `GET /api/dashboard/integration` — lab relationships and shared evidence counts
- `GET /api/dashboard/experiments` — registered experiments and last results
- `POST /api/assistant` — lab-aware offline assistant (body: `{"message":"...","lab":"7"}`)
- `POST /api/dashboard/run/{experiment_id}` — allowlisted experiment execution
