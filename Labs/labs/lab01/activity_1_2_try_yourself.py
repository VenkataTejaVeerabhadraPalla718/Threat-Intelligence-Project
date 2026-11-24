import json
from pathlib import Path

mapping = [
 {"domain":"Healthcare patient profile","family":"Document","reason":"Flexible patient records can contain nested history and changing attributes."},
 {"domain":"E-commerce shopping cart","family":"Key-value","reason":"Cart lookup and updates are keyed by customer/session ID."},
 {"domain":"IoT sensor readings","family":"Wide-column / time-series","reason":"Large volumes of timestamped readings are written and queried by device and time."},
 {"domain":"Healthcare referral network","family":"Graph","reason":"A graph represents links among patients, providers and referrals."}
]
print("1.2 TRY IT YOURSELF")
for x in mapping:
    print(f"{x['domain']}: {x['family']} — {x['reason']}")
Path("data").mkdir(exist_ok=True)
Path("data/activity_1_2_try_yourself.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
