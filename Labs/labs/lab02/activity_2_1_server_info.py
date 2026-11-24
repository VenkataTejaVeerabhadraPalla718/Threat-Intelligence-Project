from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def inspect(label, uri):
    if not uri:
        print(f"{label}: URI not configured; comparison skipped.")
        return None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        info = client.server_info()
        result = {"version": info.get("version"), "gitVersion": info.get("gitVersion", "n/a")}
        print(f"{label} server version: {result['version']}")
        client.close()
        return result
    except PyMongoError as exc:
        print(f"{label}: connection failed: {exc}")
        return None

print("2.1 MONGODB SERVER VERSION COMPARISON")
atlas = inspect("MongoDB Atlas", os.getenv("MONGO_URI_ATLAS"))
local_uri = os.getenv("MONGO_URI_LOCAL") or os.getenv("MONGO_URI") or "mongodb://127.0.0.1:27017/"
local = inspect("Local MongoDB (use Docker URI only if a Docker MongoDB is running)", local_uri)
if atlas and local:
    print("Versions match." if atlas["version"] == local["version"] else "Versions differ.")
elif not atlas:
    print("To complete the Atlas comparison, add MONGO_URI_ATLAS to .env and rerun.")
