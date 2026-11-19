import json
from pathlib import Path

mapping = [
 {"application":"Ride sharing","data_domain":"Frequently updated driver locations","family":"Key-value (Redis)","reason":"Driver ID provides a direct key for frequent location updates and low-latency reads."},
 {"application":"Ride sharing","data_domain":"User profiles","family":"Document (MongoDB)","reason":"A profile is naturally represented as a flexible document with nested preferences."},
 {"application":"Ride sharing","data_domain":"Ride history","family":"Document or wide-column","reason":"Trip records are append-heavy and can be queried by rider, driver and time."},
 {"application":"Ride sharing","data_domain":"Driver-rider relationships","family":"Graph (Neo4j)","reason":"Graph traversal can analyze connections, referrals and suspicious relationship patterns."},
 {"application":"Social analytics","data_domain":"Raw posts","family":"Wide-column (Cassandra)","reason":"Distributed write throughput supports large volumes of append-heavy posts."},
 {"application":"Social analytics","data_domain":"Real-time counters and trending topics","family":"Key-value (Redis)","reason":"Counters and hot ranking data need very fast increments and reads."}
]
print("1.2 APPLICATION MAPPING")
for x in mapping:
    print(f"{x['application']} | {x['data_domain']} -> {x['family']}: {x['reason']}")
Path("data").mkdir(exist_ok=True)
Path("data/activity_1_2_application_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
