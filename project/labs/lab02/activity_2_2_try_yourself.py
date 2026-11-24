from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
books = client["nosql_exercise_2"]["books"]
# Mark the operation to prevent accidental repeated increases on reruns.
result = books.update_many(
    {"published_year":{"$lt":2010}, "price_increased_10pct":{"$ne":True}},
    {"$mul":{"price":1.10}, "$set":{"price_increased_10pct":True}}
)
print("2.2 TRY IT YOURSELF")
print("Newly increased:", result.modified_count)
print("Older books after operation:")
for d in books.find({"published_year":{"$lt":2010}}, {"_id":0}).sort("published_year",1): print(d)
client.close()
