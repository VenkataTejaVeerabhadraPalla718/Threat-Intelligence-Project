from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
courses = client["nosql_exercise_3"]["courses"]
courses.update_one({"code":"AI402"},{"$set":{"prerequisite_codes":["CS401"]}})
courses.update_one({"code":"CS403"},{"$set":{"prerequisite_codes":[]}})
print("3.1 TRY IT YOURSELF — PREREQUISITES")
for d in courses.find({},{"_id":0,"code":1,"title":1,"prerequisite_codes":1}):
    print(d)
print("Design choice: store prerequisite course codes as references because course relationships can be reused and updated independently.")
client.close()
