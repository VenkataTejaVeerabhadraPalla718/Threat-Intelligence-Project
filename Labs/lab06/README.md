# Lab 6 â€“ Index Design and Performance

## Docker Hub: https://hub.docker.com/r/venkatatejaveerabhadra718/nosql-labs-suite





Website-runner experiments:
- 6.1 Generate 50,000 products and compare query plans before/after indexes
- 6.1 Try it yourself: repeat the workload and inspect `$indexStats`
- 6.2 Compare 10,000 inserts with no secondary indexes and five indexes; retain the critical index and time queries
- 6.2 Try it yourself: verify a covered query using `explain()`

Scripts use the isolated `lab6_indexing` database and runner-provided `MONGODB_URI`. Lab 6.1 recreates only `lab6_indexing.products`; Lab 6.2 recreates only `lab6_indexing.write_benchmark`.




