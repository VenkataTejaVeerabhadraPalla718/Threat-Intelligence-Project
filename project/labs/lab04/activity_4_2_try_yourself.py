from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient, UpdateOne

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
products=client["nosql_exercise_4"]["idempotent_import"]
products.create_index("sku", unique=True)
incoming=[
 {"sku":"IMP-001","name":"Imported Mouse","price":25,"stock":10},
 {"sku":"IMP-002","name":"Imported Keyboard","price":45,"stock":5},
 {"sku":"IMP-003","name":"Imported Webcam","price":75,"stock":8}
]
ops=[UpdateOne({"sku":p["sku"]},{"$set":p},upsert=True) for p in incoming]
result=products.bulk_write(ops,ordered=True)
print("4.2 TRY IT YOURSELF — IDEMPOTENT IMPORT")
print("Matched:",result.matched_count,"Modified:",result.modified_count,"Upserted:",result.upserted_count)
print("Total records:",products.count_documents({}))
for d in products.find({},{"_id":0}).sort("sku",1): print(d)
client.close()
