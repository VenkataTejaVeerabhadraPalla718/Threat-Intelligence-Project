from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
from pymongo import MongoClient, UpdateOne

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
products=client["nosql_exercise_4"]["bulk_products"]
products.drop()
products.insert_many([
 {"sku":"A","name":"Product A","price":100,"stock":10,"is_active":True},
 {"sku":"B","name":"Product B","price":200,"stock":20,"is_active":True},
 {"sku":"C","name":"Product C","price":300,"stock":30,"is_active":True},
 {"sku":"D","name":"Product D","price":400,"stock":40,"is_active":True},
 {"sku":"E","name":"Product E","price":500,"stock":50,"is_active":True}
])
print("4.2 UPSERT")
r=products.update_one({"sku":"F"},{"$set":{"name":"Product F","price":600,"stock":15,"is_active":True}},upsert=True)
print("Matched:",r.matched_count,"Modified:",r.modified_count,"Upserted ID:",r.upserted_id)
print("4.2 BULK WRITE")
ops=[
 UpdateOne({"sku":"A"},{"$inc":{"stock":10}}),
 UpdateOne({"sku":"B"},{"$inc":{"stock":10}}),
 UpdateOne({"sku":"C"},{"$inc":{"stock":10}}),
 UpdateOne({"sku":"D"},{"$set":{"is_active":False}}),
 UpdateOne({"sku":"E"},{"$set":{"is_active":False}})
]
result=products.bulk_write(ops,ordered=True)
print("Matched:",result.matched_count,"Modified:",result.modified_count,"Upserted:",result.upserted_count)
docs=list(products.find({},{"_id":0}).sort("sku",1))
for d in docs: print(d)
Path("data").mkdir(exist_ok=True)
Path("data/activity_4_2_upsert_bulk.json").write_text(json.dumps(docs,indent=2),encoding="utf-8")
client.close()
