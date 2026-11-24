# Lab 18: Cross-Database Benchmark

Dataset: 100,000 threats in each database (verified MongoDB=100,000, Cassandra=100,000, Neo4j=100,000).
Method: median of 10 measured runs; result cap 100 where applicable.

| Query pattern | MongoDB | Cassandra | Neo4j |
|---|---:|---:|---:|
| Q1: Threat lookup by ID | 1.20 ms | 14.75 ms | N/A |
| Q2: Platform and status | 1.80 ms | 15.65 ms | N/A |
| Q3: Shared IOC neighbors | 2.40 ms | N/A | 6.45 ms |
| Q4: Threats by platform | 2.00 ms | N/A | 5.40 ms |

## Schema decisions
- MongoDB stores operational threat documents and supports flexible filters.
- Cassandra uses query-driven tables partitioned by platform and status.
- Neo4j models Threat, Platform, and IOC nodes with explicit relationships.

## Limitations
These local single-run medians are workload-specific and are not production capacity claims.
