"""
LAB 6.2 - Compare Index Strategies
Measures 10,000 inserts without secondary indexes and with five indexes,
then keeps one critical index and re-runs the five query workload.
"""
import os, random, time, uuid
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT

URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB = os.getenv("MONGODB_DB", "lab6_indexing")
random.seed(73)

def batch(n, prefix):
    cats = ["Electronics", "Books", "Clothing", "Home", "Sports"]
    tags = ["wireless", "portable", "premium", "budget", "new"]
    return [{
        "_id": f"{prefix}-{i}-{uuid.uuid4().hex[:8]}",
        "name": f"Benchmark Product {prefix} {i}",
        "category": random.choice(cats),
        "price": round(random.uniform(10, 2000), 2),
        "rating": round(random.uniform(1, 5), 1),
        "stock": random.randint(0, 300),
        "tags": random.sample(tags, k=2)
    } for i in range(n)]

def timed_insert(coll, docs):
    start = time.perf_counter()
    coll.insert_many(docs, ordered=False)
    return time.perf_counter() - start

def main():
    client = MongoClient(URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[DB]
    coll = db["write_benchmark"]
    coll.drop()

    t_no_index = timed_insert(coll, batch(10000, "noidx"))
    print(f"10,000 inserts with only _id index: {t_no_index:.4f} seconds")

    specs = [
        ([("category", ASCENDING)], "idx_category"),
        ([("price", ASCENDING)], "idx_price"),
        ([("rating", DESCENDING)], "idx_rating"),
        ([("tags", ASCENDING)], "idx_tags"),
        ([("name", TEXT)], "idx_name_text"),
    ]
    for keys, name in specs:
        coll.create_index(keys, name=name)
    t_five = timed_insert(coll, batch(10000, "fiveidx"))
    slowdown = ((t_five - t_no_index) / t_no_index * 100) if t_no_index else 0
    print(f"10,000 inserts with five secondary indexes: {t_five:.4f} seconds")
    print(f"Write-time slowdown: {slowdown:.2f}%")

    # Keep category index as the critical index for Q1; drop other secondary indexes.
    for name in ["idx_price", "idx_rating", "idx_tags", "idx_name_text"]:
        coll.drop_index(name)
    print("Remaining indexes:", [x["name"] for x in coll.list_indexes()])

    queries = [
        ("Q1 category", {"category": "Electronics"}, [("price", ASCENDING)]),
        ("Q2 price range", {"price": {"$gte": 100, "$lte": 500}}, None),
        ("Q3 tag", {"tags": "wireless"}, None),
        ("Q4 name regex", {"name": {"$regex": "Benchmark", "$options": "i"}}, None),
        ("Q5 rating", {"rating": {"$gte": 4.0}}, None),
    ]
    print("\nQuery timings after retaining category index:")
    for label, query, sort in queries:
        cursor = coll.find(query)
        if sort:
            cursor = cursor.sort(sort)
        start = time.perf_counter()
        count = sum(1 for _ in cursor.limit(500))
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed*1000:.3f} ms (sample rows={count})")
    print("\nAnalysis: secondary indexes can reduce read cost but add work to every insert/update.")
    client.close()

if __name__ == "__main__":
    main()
