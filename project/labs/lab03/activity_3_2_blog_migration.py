from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"), serverSelectionTimeoutMS=5000)
client.admin.command("ping")
db = client["nosql_exercise_3"]
posts, comments = db["blog_posts"], db["blog_comments"]
posts.drop(); comments.drop()
post_docs=[
 {"post_id":1,"title":"MongoDB Basics","author":"Asha"},
 {"post_id":2,"title":"NoSQL Data Models","author":"Ravi"},
 {"post_id":3,"title":"Aggregation Pipeline","author":"Neha"},
 {"post_id":4,"title":"Indexes Explained","author":"Kiran"},
 {"post_id":5,"title":"Schema Design","author":"Divya"}
]
comment_docs=[
 {"comment_id":i,"post_id":((i-1)//2)+1,"user":f"User{i}","text":f"Comment {i}"} for i in range(1,11)
]
posts.insert_many(post_docs); comments.insert_many(comment_docs)
print("3.2 REFERENCED DESIGN ($lookup)")
joined=list(posts.aggregate([{"$lookup":{"from":"blog_comments","localField":"post_id","foreignField":"post_id","as":"comments"}}]))
for p in joined: print(p["title"], "->", len(p["comments"]), "comments")
for p in joined:
    posts.update_one({"post_id":p["post_id"]},{"$set":{"comments":[{k:v for k,v in c.items() if k!="_id"} for c in p["comments"]]}})
embedded=list(posts.find({},{"_id":0}))
Path("data").mkdir(exist_ok=True)
Path("data/activity_3_2_blog_migration.json").write_text(json.dumps(embedded,indent=2),encoding="utf-8")
print("Embedded design migrated. Referenced design requires a $lookup aggregation; embedded design can return post and comments in one find query.")
client.close()
