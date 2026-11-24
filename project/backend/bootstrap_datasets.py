"""Create clearly-labelled local demonstration datasets for Labs 7 and 10.
Never represents these synthetic rows as live-verified threat intelligence.
Idempotent: upserts deterministic IDs and never drops collections.
"""
import os, hashlib, random
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne

URI=os.getenv("MONGO_URI","mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0")
LAB7_TARGET=int(os.getenv("LAB7_TARGET_RECORDS","40000"))
LAB10_TARGET=int(os.getenv("LAB10_TARGET_RECORDS","200000"))
client=MongoClient(URI, serverSelectionTimeoutMS=15000)
db=client["cti"]
platforms=["Windows","Linux","macOS","Android","iOS"]
classes=["Malware","Phishing","Ransomware","Vulnerability","Data Breach","DDoS"]
severities=["Low","Medium","High","Critical"]

def stable_id(prefix,n):
    return f"{prefix}-{n:09d}"

def seed_lab7():
    col=db.threats
    existing=col.count_documents({"dataset_tag":"lab7_synthetic_demo"})
    if existing>=LAB7_TARGET:
        print(f"Lab 7 synthetic demo dataset already present: {existing:,}")
        return
    print(f"Seeding Lab 7 to {LAB7_TARGET:,} clearly-labelled records...")
    for start in range(0,LAB7_TARGET,2000):
        ops=[]
        for i in range(start,min(start+2000,LAB7_TARGET)):
            n=i+1
            ops.append(UpdateOne({"_id":stable_id("lab7-demo",n)},{"$setOnInsert":{
                "_id":stable_id("lab7-demo",n),
                "title":f"Synthetic CTI demonstration event {n}",
                "content":"Synthetic training record; not a real incident or independently verified IOC.",
                "source_id":"local_synthetic_generator",
                "url":f"https://example.invalid/sentinelx/lab7/{n}",
                "published_at":datetime(2026,1,1,tzinfo=timezone.utc),
                "classification":{"type":classes[n%len(classes)],"severity":severities[n%len(severities)]},
                "iocs":[],"record_origin":"synthetic_demo","dataset_tag":"lab7_synthetic_demo",
                "verification":{"status":"synthetic_not_verified","checks":[],"note":"Synthetic academic demo data, not live threat intelligence."}
            }},upsert=True))
        col.bulk_write(ops,ordered=False)
        if (start+2000)%10000==0: print(f"Lab 7 progress: {min(start+2000,LAB7_TARGET):,}/{LAB7_TARGET:,}")
    print("Lab 7 tagged count:",col.count_documents({"dataset_tag":"lab7_synthetic_demo"}))

def seed_lab10():
    col=db["lab10_transactions"]["records"]
    existing=col.count_documents({"dataset_tag":"lab10_consistency_demo"})
    if existing>=LAB10_TARGET:
        print(f"Lab 10 dataset already present: {existing:,}")
        return
    print(f"Seeding Lab 10 to {LAB10_TARGET:,} transaction records...")
    for start in range(0,LAB10_TARGET,2000):
        ops=[]
        for i in range(start,min(start+2000,LAB10_TARGET)):
            n=i+1
            ops.append(UpdateOne({"_id":stable_id("lab10-txn",n)},{"$setOnInsert":{
                "_id":stable_id("lab10-txn",n),"account_id":f"ACC-{(n%5000)+1:05d}",
                "transaction_id":stable_id("txn",n),"amount_cents":(n*7919)%500000,
                "currency":"INR","status":["committed","pending","reversed"][n%3],
                "version":1+(n%5),"dataset_tag":"lab10_consistency_demo",
                "record_origin":"synthetic_demo","created_at":datetime(2026,1,1,tzinfo=timezone.utc)
            }},upsert=True))
        col.bulk_write(ops,ordered=False)
        if (start+2000)%20000==0: print(f"Lab 10 progress: {min(start+2000,LAB10_TARGET):,}/{LAB10_TARGET:,}")
    print("Lab 10 tagged count:",col.count_documents({"dataset_tag":"lab10_consistency_demo"}))

if __name__=="__main__":
    client.admin.command("ping")
    seed_lab7()
    seed_lab10()
    print("Dataset bootstrap complete.")
    client.close()
