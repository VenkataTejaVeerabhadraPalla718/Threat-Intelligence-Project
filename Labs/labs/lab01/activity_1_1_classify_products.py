import json
from pathlib import Path

products = [
    {"product":"Amazon S3","family":"Key-value / object storage","best_for":"Durable object and file storage addressed by object keys","limitation":"Not a general-purpose database; limited querying over object contents"},
    {"product":"Couchbase","family":"Document (with key-value access)","best_for":"JSON application data, user profiles and low-latency application access","limitation":"Operational complexity and memory/resource planning"},
    {"product":"Apache HBase","family":"Wide-column","best_for":"Very large sparse tables and high-throughput reads/writes","limitation":"More complex operations; not suited to rich relational joins"},
    {"product":"Amazon Neptune","family":"Graph","best_for":"Relationship traversal, recommendation and fraud-network analysis","limitation":"Graph workloads are specialized and may not suit simple key/value access"},
    {"product":"Memcached","family":"Key-value cache","best_for":"Fast temporary caching of frequently accessed values","limitation":"In-memory cache; data is not intended as durable primary storage"}
]
print("1.1 CLASSIFICATION OF DATABASE PRODUCTS")
for p in products:
    print(f"{p['product']}: {p['family']} — {p['best_for']}")
Path("data").mkdir(exist_ok=True)
Path("data/activity_1_1_classify_products.json").write_text(json.dumps(products, indent=2), encoding="utf-8")
