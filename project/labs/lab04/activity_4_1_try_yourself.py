from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
products=client["nosql_exercise_4"]["products"]
search=os.getenv("LAB04_SEARCH", "lap").strip() or "lap"
print("Search term:", search)
query={"name":{"$regex":search,"$options":"i"}}
print("4.1 TRY IT YOURSELF — REGEX SEARCH")
matches=list(products.find(query,{"_id":0}))
if matches:
    for p in matches: print(p)
else:
    print("No matching products found.")
client.close()
