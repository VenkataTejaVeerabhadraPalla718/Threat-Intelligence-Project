import json
from pathlib import Path

items = [
    {"product":"ScyllaDB","family":"Wide-column","reason":"Cassandra-compatible distributed wide-column database for high-throughput workloads."},
    {"product":"InfluxDB","family":"Time-series (specialized NoSQL)","reason":"Optimized for timestamped measurements and time-series queries."},
    {"product":"ArangoDB","family":"Multi-model (document, graph and key-value)","reason":"One database supports documents and graph relationships; it spans multiple families."}
]
print("1.1 TRY IT YOURSELF")
for item in items:
    print(f"{item['product']}: {item['family']} — {item['reason']}")
Path("data").mkdir(exist_ok=True)
Path("data/activity_1_1_try_yourself.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
