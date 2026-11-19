from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client["nosql_exercise_4"]
db.products.drop()
db.create_collection("products", validator={"$jsonSchema":{
 "bsonType":"object","required":["name","price","stock","tags"],
 "properties":{"name":{"bsonType":"string"},"price":{"bsonType":["int","double"],"minimum":0},
 "stock":{"bsonType":"int","minimum":0},"tags":{"bsonType":"array","items":{"bsonType":"string"}}}
}})
products=db.products
products.insert_many([
 {"sku":"P001","name":"Wireless Mouse","price":25.0,"stock":40,"tags":["electronics","wireless"]},
 {"sku":"P002","name":"Bluetooth Keyboard","price":45.0,"stock":0,"tags":["electronics","wireless","premium"]},
 {"sku":"P003","name":"USB Cable","price":10.0,"stock":100,"tags":["electronics","accessory"]},
 {"sku":"P004","name":"Office Chair","price":120.0,"stock":15,"tags":["furniture"]},
 {"sku":"P005","name":"Laptop Stand","price":35.0,"stock":20,"tags":["electronics","accessory"]},
 {"sku":"P006","name":"Desk Lamp","price":55.0,"stock":0,"tags":["home","lighting"]},
 {"sku":"P007","name":"Gaming Headset","price":90.0,"stock":12,"tags":["electronics","wireless","premium"]},
 {"sku":"P008","name":"Notebook","price":5.0,"stock":200,"tags":["stationery"]},
 {"sku":"P009","name":"Webcam","price":75.0,"stock":8,"tags":["electronics","wireless"]},
 {"sku":"P010","name":"Monitor","price":180.0,"stock":5,"tags":["electronics","display"]}
])
def show(label, cursor):
    print("\\n"+label)
    for d in cursor: print({k:v for k,v in d.items() if k!="_id"})
show("Price between 20 and 50:", products.find({"price":{"$gte":20,"$lte":50}}))
show("Out of stock OR price above 100:", products.find({"$or":[{"stock":0},{"price":{"$gt":100}}]}))
show("In stock AND premium:", products.find({"$and":[{"stock":{"$gt":0}},{"tags":"premium"}]}))
show("Has BOTH electronics AND wireless:", products.find({"tags":{"$all":["electronics","wireless"]}}))
show("Exactly two tags:", products.find({"tags":{"$size":2}}))
print("\\nPagination — page 2, 3 items per page, sorted by name:")
show("Page 2:", products.find({},{"_id":0}).sort("name",1).skip(3).limit(3))
term="wire"
show(f"Regex search for '{term}' (case-insensitive):", products.find({"name":{"$regex":term,"$options":"i"}}))
docs=list(products.find({},{"_id":0}).sort("name",1))
Path("data").mkdir(exist_ok=True)
Path("data/activity_4_1_product_queries.json").write_text(json.dumps(docs,indent=2),encoding="utf-8")
client.close()
