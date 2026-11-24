"""
LAB 6.1 - Index Design for a Query Workload
Creates 50,000 products, explains five queries before and after indexing.
MongoDB URI can be overridden with MONGODB_URI.
"""
import os, random, string, json
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB", "lab6_indexing")
COLLECTION = "products"
random.seed(42)

CATEGORIES = ["Electronics", "Books", "Clothing", "Home", "Sports", "Beauty", "Toys"]
TAGS = ["wireless", "portable", "premium", "budget", "new", "sale", "popular", "eco", "waterproof"]

def make_products(n=50000):
    docs = []
    for i in range(n):
        category = random.choice(CATEGORIES)
        docs.append({
            "name": f"{random.choice(['Pro','Ultra','Classic','Smart','Eco'])} "
                    f"{random.choice(['Phone','Book','Bottle','Watch','Speaker','Bag'])} {i}",
            "category": category,
            "price": round(random.uniform(5, 2500), 2),
            "rating": round(random.uniform(1, 5), 1),
            "stock": random.randint(0, 500),
            "tags": random.sample(TAGS, k=random.randint(1, 4))
        })
    return docs

def explain_summary(coll, label, query, sort=None, projection=None):
    plan = coll.find(query, projection)
    if sort:
        plan = plan.sort(sort)
    result = plan.explain()
    stats = result.get("executionStats", {})
    winning = result.get("queryPlanner", {}).get("winningPlan", {})
    print(f"\n{label}")
    print("Winning plan:", winning.get("stage", "SEE queryPlanner.winningPlan"))
    print("totalDocsExamined:", stats.get("totalDocsExamined", "n/a"))
    print("nReturned:", stats.get("nReturned", "n/a"))
    print("executionTimeMillis:", stats.get("executionTimeMillis", "n/a"))
    return result

def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    coll = client[DB_NAME][COLLECTION]
    coll.drop()
    docs = make_products(50000)
    coll.insert_many(docs, ordered=False)
    print(f"Inserted {coll.count_documents({}):,} product documents.")

    queries = [
        ("Q1 category + price sort", {"category": "Electronics"}, [("price", ASCENDING)], None),
        ("Q2 price range", {"price": {"$gte": 100, "$lte": 500}}, None, None),
        ("Q3 tag lookup", {"tags": "wireless"}, None, None),
        ("Q4 text search on name", {"$text": {"$search": "Pro Phone"}}, None, None),
        ("Q5 category + rating filter", {"category": "Books", "rating": {"$gte": 4.0}}, None, None),
    ]
    print("\n========== BEFORE INDEXES ==========")
    for label, query, sort, projection in queries:
        # Text search requires a text index. For a genuine pre-index baseline,
        # Q4 uses a regex scan until the text index is created.
        if label.startswith("Q4"):
            explain_summary(coll, label + " (regex baseline)",
                            {"name": {"$regex": "Pro Phone", "$options": "i"}})
        else:
            explain_summary(coll, label, query, sort, projection)

    print("\n========== CREATE INDEXES ==========")
    indexes = [
        ([("category", ASCENDING), ("price", ASCENDING)], "idx_category_price"),
        ([("price", ASCENDING)], "idx_price"),
        ([("tags", ASCENDING)], "idx_tags"),
        ([("name", TEXT)], "idx_name_text"),
        ([("category", ASCENDING), ("rating", DESCENDING)], "idx_category_rating"),
    ]
    for keys, name in indexes:
        coll.create_index(keys, name=name)
        print("Created:", name)

    print("\n========== AFTER INDEXES ==========")
    for label, query, sort, projection in queries:
        explain_summary(coll, label, query, sort, projection)
    print("\nLab 6.1 complete. Compare totalDocsExamined and winning plans above.")
    client.close()

if __name__ == "__main__":
    main()
