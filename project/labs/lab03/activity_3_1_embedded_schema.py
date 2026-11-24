from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client["nosql_exercise_3"]
db.courses.drop()
db.create_collection("courses", validator={
 "$jsonSchema":{"bsonType":"object","required":["title","code","instructor","schedule","students"],
 "properties":{
  "title":{"bsonType":"string"}, "code":{"bsonType":"string"},
  "instructor":{"bsonType":"string"},
  "schedule":{"bsonType":"object","required":["days","times","room"],
   "properties":{"days":{"bsonType":"array","items":{"bsonType":"string"}},
                 "times":{"bsonType":"string"},"room":{"bsonType":"string"}}},
  "students":{"bsonType":"array","items":{"bsonType":"object","required":["name","id","grade"],
   "properties":{"name":{"bsonType":"string"},"id":{"bsonType":"string"},"grade":{"bsonType":"string"}}}}
 }}})
courses = db["courses"]
courses.insert_many([
 {"title":"Database Systems","code":"CS401","instructor":"Dr. Meera Rao","schedule":{"days":["Monday","Wednesday"],"times":"09:00-10:00","room":"A-101"},"students":[{"name":"Asha","id":"S001","grade":"A"},{"name":"Ravi","id":"S002","grade":"B+"}]},
 {"title":"Machine Learning","code":"AI402","instructor":"Dr. Arjun Kumar","schedule":{"days":["Tuesday","Thursday"],"times":"10:00-11:00","room":"B-202"},"students":[{"name":"Neha","id":"S003","grade":"A"}]},
 {"title":"Computer Networks","code":"CS403","instructor":"Dr. Meera Rao","schedule":{"days":["Monday","Friday"],"times":"11:00-12:00","room":"C-303"},"students":[{"name":"Kiran","id":"S004","grade":"A-"},{"name":"Divya","id":"S005","grade":"B"}]}
])
print("3.1 COURSES MEETING ON MONDAY")
for d in courses.find({"schedule.days":"Monday"},{"_id":0}): print(d["code"], d["title"])
print("Courses taught by Dr. Meera Rao:")
for d in courses.find({"instructor":"Dr. Meera Rao"},{"_id":0}): print(d["code"], d["title"])
docs=list(courses.find({},{"_id":0}))
Path("data").mkdir(exist_ok=True)
Path("data/activity_3_1_embedded_schema.json").write_text(json.dumps(docs,indent=2),encoding="utf-8")
client.close()
