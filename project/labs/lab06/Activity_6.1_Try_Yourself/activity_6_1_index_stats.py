"""
LAB 6.1 TRY IT YOURSELF - Measure actual index usage with $indexStats.
Run after activity_6_1.py, then execute the representative queries repeatedly.
"""
import os
from pymongo import MongoClient, ASCENDING, DESCENDING

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB = os.getenv("MONGODB_DB", "lab6_indexing")

def main():
    client = MongoClient(URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    coll = client[DB]["products"]
    workloads = [
        lambda: list(coll.find({"category": "Electronics"}).sort("price", ASCENDING).limit(20)),
        lambda: list(coll.find({"price": {"$gte": 100, "$lte": 500}}).limit(20)),
        lambda: list(coll.find({"tags": "wireless"}).limit(20)),
        lambda: list(coll.find({"$text": {"$search": "Pro Phone"}}).limit(20)),
        lambda: list(coll.find({"category": "Books", "rating": {"$gte": 4.0}}).limit(20)),
    ]
    for _ in range(10):
        for run_query in workloads:
            run_query()
    print("Executed each of the five workload queries 10 times.")
    print("\n$indexStats results:")
    for row in coll.aggregate([{"$indexStats": {}}]):
        print({
            "name": row.get("name"),
            "accesses": row.get("accesses", {}),
            "host": row.get("host")
        })
    client.close()

if __name__ == "__main__":
    main()
