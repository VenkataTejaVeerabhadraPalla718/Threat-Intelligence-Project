# Phased upgrade changelog

- Added authenticated enterprise operations router and registered it in FastAPI.
- Added lab registry and job-history APIs.
- Added bounded read-only MongoDB, Cassandra and Neo4j query endpoints.
- Added admin audit history and lab-history CSV export.
- Added read-only infrastructure reachability endpoint.
- Added explainable IOC correlation and transaction anomaly scoring modules.
- Added safe manual Mongo backup/restore scripts; restore requires explicit confirmation.
- Added GitHub Actions CI workflow and tests.
- Added phased execution, safety and data-preservation guide.

Existing named Mongo volumes are unchanged. `.env` and local backup archives are excluded.


## AI assistant low-latency upgrade

- Added a thread-safe 512-entry in-memory response cache with normalized query keys.
- Standalone informational queries can be served from cache before MongoDB or Ollama is contacted.
- Contextual follow-ups and state-changing/action requests are excluded from cache reuse.
- Deterministic knowledge-base and read-only tool answers are cached; successful first-turn LLM answers remain cacheable.
- Removed unconditional full threat/source collection counts from every LLM prompt; live counts are fetched only for explicit analytics requests.
- Reordered threat analytics intent detection so unrelated questions do not trigger MongoDB collection counts.
- Assistant UI identifies cache-served responses; existing first-response and total latency display remains enabled.

Latency depends on machine load, MongoDB response time, network conditions, and Ollama model/hardware. Millisecond responses are realistic for cache hits and lightweight local tools, not guaranteed for generated LLM answers. The cache is process-local and clears when the API restarts.
