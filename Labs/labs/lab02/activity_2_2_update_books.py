from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
books = client["nosql_exercise_2"]["books"]
books.delete_many({})
books.insert_many([
    {"title":"Database Systems","author":"A. Kumar","published_year":2005,"price":500.0},
    {"title":"Python Programming","author":"R. Sharma","published_year":2012,"price":450.0},
    {"title":"NoSQL Fundamentals","author":"S. Patel","published_year":2008,"price":600.0},
    {"title":"Modern Data Engineering","author":"M. Rao","published_year":2021,"price":750.0},
    {"title":"Algorithms","author":"T. Das","published_year":2001,"price":400.0}
])
print("Before update:")
for d in books.find({}, {"_id":0}).sort("published_year", 1): print(d)
result = books.update_many({"published_year":{"$lt":2010}}, {"$mul":{"price":1.10}})
print(f"Matched: {result.matched_count}; modified: {result.modified_count}")
print("After update:")
docs = list(books.find({}, {"_id":0}).sort("published_year", 1))
for d in docs: print(d)
Path("data").mkdir(exist_ok=True)
Path("data/activity_2_2_update_books.json").write_text(json.dumps(docs, indent=2), encoding="utf-8")
client.close()
