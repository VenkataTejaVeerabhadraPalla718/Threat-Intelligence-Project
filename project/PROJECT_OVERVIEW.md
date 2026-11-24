# SENTINEL-X Project Overview

## Main modules
- Threat intelligence dashboard: `/`
- Lab execution/history dashboard: `/dashboard`
- Local LLM/RAG chat: `/chat`
- FastAPI docs: `/docs`
- MongoDB replica-set: three data-bearing members
- Optional Atlas Local vector service, Cassandra and Neo4j services through Compose profiles
- Labs 7–18 scripts retained in `labs/`

## Threat data integrity model
- Synthetic demonstration data is visibly labeled `synthetic_demo` and `demo_only`.
- RSS feed records are labeled `live_rss` and `feed_unverified` until independently validated.
- Ingestion upserts by canonical URL and never clears the `threats` or `sources` collections.
- Sync service repeats at the configured interval and records source failures in logs.
- The dashboard count can include both synthetic demonstration records and live feed records. Do not describe synthetic records as verified real-world incidents.

## Local AI
Ollama runs on the Windows host; FastAPI reaches it through `host.docker.internal`. Required model tags are `llama3.2:3b` and `nomic-embed-text`.
