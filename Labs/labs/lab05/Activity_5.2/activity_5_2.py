"""Lab 5.2 Join Data with $lookup. Run: python activity.py
Requires MongoDB running and pymongo installed. Set MONGODB_URI if needed.
"""
import os, json
from datetime import datetime
from pymongo import MongoClient

client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"), serverSelectionTimeoutMS=5000)
db = client["lab5_sales_analytics"]
def show(title, cursor):
    print("\n" + title)
    for row in cursor:
        print(json.dumps(row, default=str, indent=2))

products = [
  {
    "product_id": "P001",
    "name": "Laptop",
    "category": "Computers",
    "base_price": 850
  },
  {
    "product_id": "P002",
    "name": "Mouse",
    "category": "Accessories",
    "base_price": 25
  },
  {
    "product_id": "P003",
    "name": "Keyboard",
    "category": "Accessories",
    "base_price": 75
  },
  {
    "product_id": "P004",
    "name": "Monitor",
    "category": "Displays",
    "base_price": 220
  },
  {
    "product_id": "P005",
    "name": "USB Cable",
    "category": "Accessories",
    "base_price": 10
  },
  {
    "product_id": "P006",
    "name": "Headphones",
    "category": "Audio",
    "base_price": 120
  },
  {
    "product_id": "P007",
    "name": "Webcam",
    "category": "Accessories",
    "base_price": 55
  },
  {
    "product_id": "P008",
    "name": "Tablet",
    "category": "Computers",
    "base_price": 350
  }
]
orders = [
  {
    "order_id": "ORD001",
    "product_id": "P001",
    "quantity": 1,
    "order_date": "2026-01-05T10:00:00Z"
  },
  {
    "order_id": "ORD002",
    "product_id": "P002",
    "quantity": 2,
    "order_date": "2026-01-08T10:00:00Z"
  },
  {
    "order_id": "ORD003",
    "product_id": "P003",
    "quantity": 1,
    "order_date": "2026-01-12T10:00:00Z"
  },
  {
    "order_id": "ORD004",
    "product_id": "P004",
    "quantity": 1,
    "order_date": "2026-02-03T10:00:00Z"
  },
  {
    "order_id": "ORD005",
    "product_id": "P001",
    "quantity": 1,
    "order_date": "2026-02-10T10:00:00Z"
  },
  {
    "order_id": "ORD006",
    "product_id": "P005",
    "quantity": 3,
    "order_date": "2026-02-15T10:00:00Z"
  },
  {
    "order_id": "ORD007",
    "product_id": "P006",
    "quantity": 1,
    "order_date": "2026-03-01T10:00:00Z"
  },
  {
    "order_id": "ORD008",
    "product_id": "P002",
    "quantity": 4,
    "order_date": "2026-03-05T10:00:00Z"
  },
  {
    "order_id": "ORD009",
    "product_id": "P003",
    "quantity": 2,
    "order_date": "2026-03-11T10:00:00Z"
  },
  {
    "order_id": "ORD010",
    "product_id": "P007",
    "quantity": 1,
    "order_date": "2026-03-18T10:00:00Z"
  },
  {
    "order_id": "ORD011",
    "product_id": "P004",
    "quantity": 2,
    "order_date": "2026-04-02T10:00:00Z"
  },
  {
    "order_id": "ORD012",
    "product_id": "P006",
    "quantity": 2,
    "order_date": "2026-04-20T10:00:00Z"
  }
]
db.products.drop()
db.orders.drop()
db.products.insert_many(products)
db.orders.insert_many(orders)
print(f"Inserted {db.products.count_documents({})} products and {db.orders.count_documents({})} orders")

lookup_pipeline = [
    {"$lookup": {"from": "products", "localField": "product_id", "foreignField": "product_id", "as": "product_info"}},
    {"$unwind": "$product_info"},
    {"$project": {"_id": 0, "order_date": 1, "product_name": "$product_info.name",
                  "quantity": 1, "total": {"$multiply": ["$quantity", "$product_info.base_price"]}}},
    {"$sort": {"order_date": 1}}
]
show("ORDERS JOINED WITH PRODUCTS", db.orders.aggregate(lookup_pipeline))

never_ordered_pipeline = [
    {"$lookup": {"from": "orders", "localField": "product_id", "foreignField": "product_id", "as": "order_matches"}},
    {"$match": {"order_matches": {"$eq": []}}},
    {"$project": {"_id": 0, "product_id": 1, "name": 1, "category": 1, "base_price": 1}}
]
show("PRODUCTS NEVER ORDERED", db.products.aggregate(never_ordered_pipeline))
