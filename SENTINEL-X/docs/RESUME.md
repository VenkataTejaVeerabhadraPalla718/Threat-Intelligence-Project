# Resume material (edit to match what you personally built and can explain)

**SENTINEL-X — Threat Intelligence & NoSQL Operations Platform** · Python, FastAPI, MongoDB (3-node replica set), Docker Compose, Ollama, Chart.js

- Built a multi-user security console with JWT authentication, Argon2id password hashing, role-based access control, token revocation and brute-force lockout; every authentication event is audited in MongoDB with IP, user-agent and correlation ID.
- Designed an admin dashboard for user management, filtered/exportable login audit trails and automated detection of repeated failed logins and password-spraying patterns.
- Implemented a threat-intelligence pipeline (RSS ingestion, IOC extraction, URL-based deduplication) with an aggregation-driven analytics dashboard (severity, category, source, daily/weekly trends).
- Created a local-LLM assistant with Server-Sent-Event token streaming, a warm-model strategy, a response cache and an instant tier (knowledge base and live database tools), limited to an allow-listed tool registry with admin-only execution and confirmation for destructive operations.
- Packaged 12 MongoDB laboratory experiments (replication, sharding, write concern, transactions, RBAC/TLS, multi-tenancy, polyglot persistence, vector search) behind a unified Docker Compose deployment with health checks and CI.

**Be ready to explain in interviews:** why majority write concern, how elections work, how the lockout and token revocation work, why roles are re-read from the database, and what the three assistant tiers do.
**Do not claim** measured latency or user numbers you have not measured yourself.
