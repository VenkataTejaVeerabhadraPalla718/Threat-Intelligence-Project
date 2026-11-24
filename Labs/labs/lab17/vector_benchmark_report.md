# Lab 17.2: Cross-Engine HNSW Vector Search

Run time (UTC): 2026-11-12T20:09:18.155249+00:00
Dataset: 5,000 identical normalized vectors | dimensions: 384
Queries: 100 measured per engine, plus 10 warmups
Top K: 10 | metric: cosine similarity
MongoDB version: 9.0.4
Neo4j version: 5.26.33

| Engine | Index | Median latency | P95 latency | Mean recall@10 |
|---|---|---:|---:|---:|
| MongoDB Atlas Local | HNSW (maxEdges=16; numCandidates=100) | 11.07 ms | 21.96 ms | 94.9% |
| Neo4j | HNSW (native vector index defaults) | 9.20 ms | 14.85 ms | 54.6% |

Method: both engines received the same deterministic vector dataset and query vectors. Exact cosine top-10 from NumPy is used only as the recall reference, not as a competing search engine. Query latency includes the client round trip and result transfer; both engines were warmed and query order was alternated. Engine-specific HNSW implementations and defaults differ, so timings describe this host and configuration rather than a hardware-independent ranking.

The script upserts records in dedicated Lab 17.2 collections/labels and does not drop collections, delete graph nodes, or reset database volumes.
