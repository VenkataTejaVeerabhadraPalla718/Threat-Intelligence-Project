"""
LAB 6.2 TRY IT YOURSELF - Covered query.
The projection returns only fields contained in the compound index.
Use explain() to verify totalDocsExamined=0 and no FETCH stage in the winning plan.
"""
import os
from pymongo import MongoClient, ASCENDING

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB = os.getenv("MONGODB_DB", "lab6_indexing")

def main():
    client = MongoClient(URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    coll = client[DB]["products"]
    coll.create_index(
        [("category", ASCENDING), ("price", ASCENDING), ("name", ASCENDING)],
        name="idx_covered_category_price_name"
    )
    query = {"category": "Electronics", "price": {"$gte": 100, "$lte": 800}}
    projection = {"_id": 0, "category": 1, "price": 1, "name": 1}
    result = coll.find(query, projection).sort("price", ASCENDING).explain()
    print("Winning plan:", result.get("queryPlanner", {}).get("winningPlan", {}))
    stats = result.get("executionStats", {})
    print("totalDocsExamined:", stats.get("totalDocsExamined"))
    print("totalKeysExamined:", stats.get("totalKeysExamined"))
    print("nReturned:", stats.get("nReturned"))
    print("Check: a covered query should examine 0 documents and avoid FETCH.")
    client.close()

if __name__ == "__main__":
    main()
