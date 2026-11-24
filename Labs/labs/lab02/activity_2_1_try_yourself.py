from dotenv import load_dotenv
load_dotenv()
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
try:
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        info = client.server_info()
        build = info.get("buildEnvironment", {})
        print("2.1 TRY IT YOURSELF")
        print("Version:", info.get("version"))
        print("Allocator:", build.get("allocator", "Not reported"))
        print("Target architecture:", build.get("target_arch", "Not reported"))
except PyMongoError as exc:
    raise SystemExit(f"MongoDB connection failed. Start MongoDB or update .env: {exc}")
