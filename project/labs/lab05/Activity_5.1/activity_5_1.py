"""Lab 5.1 Sales Analytics Pipeline. Run: python activity.py
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

orders = [
  {
    "customer": "Aarav",
    "product": "Laptop",
    "quantity": 1,
    "unit_price": 850,
    "order_date": "2026-01-05T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Diya",
    "product": "Mouse",
    "quantity": 2,
    "unit_price": 25,
    "order_date": "2026-01-08T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Kabir",
    "product": "Keyboard",
    "quantity": 1,
    "unit_price": 75,
    "order_date": "2026-01-12T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Aarav",
    "product": "Monitor",
    "quantity": 1,
    "unit_price": 220,
    "order_date": "2026-02-03T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Meera",
    "product": "Laptop",
    "quantity": 1,
    "unit_price": 900,
    "order_date": "2026-02-10T10:00:00Z",
    "status": "pending"
  },
  {
    "customer": "Rohan",
    "product": "USB Cable",
    "quantity": 3,
    "unit_price": 10,
    "order_date": "2026-02-15T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Diya",
    "product": "Headphones",
    "quantity": 1,
    "unit_price": 120,
    "order_date": "2026-03-01T10:00:00Z",
    "status": "shipped"
  },
  {
    "customer": "Kabir",
    "product": "Mouse",
    "quantity": 4,
    "unit_price": 22,
    "order_date": "2026-03-05T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Meera",
    "product": "Keyboard",
    "quantity": 2,
    "unit_price": 65,
    "order_date": "2026-03-11T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Aarav",
    "product": "Webcam",
    "quantity": 1,
    "unit_price": 55,
    "order_date": "2026-03-18T10:00:00Z",
    "status": "cancelled"
  },
  {
    "customer": "Rohan",
    "product": "Monitor",
    "quantity": 2,
    "unit_price": 210,
    "order_date": "2026-04-02T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Diya",
    "product": "Laptop",
    "quantity": 1,
    "unit_price": 820,
    "order_date": "2026-04-07T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Kabir",
    "product": "USB Cable",
    "quantity": 5,
    "unit_price": 9,
    "order_date": "2026-04-12T10:00:00Z",
    "status": "pending"
  },
  {
    "customer": "Meera",
    "product": "Headphones",
    "quantity": 2,
    "unit_price": 110,
    "order_date": "2026-04-20T10:00:00Z",
    "status": "shipped"
  },
  {
    "customer": "Aarav",
    "product": "Mouse",
    "quantity": 3,
    "unit_price": 24,
    "order_date": "2026-05-02T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Rohan",
    "product": "Keyboard",
    "quantity": 1,
    "unit_price": 80,
    "order_date": "2026-05-08T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Diya",
    "product": "Webcam",
    "quantity": 2,
    "unit_price": 60,
    "order_date": "2026-05-14T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Kabir",
    "product": "Laptop",
    "quantity": 1,
    "unit_price": 880,
    "order_date": "2026-05-21T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Meera",
    "product": "Monitor",
    "quantity": 1,
    "unit_price": 230,
    "order_date": "2026-06-04T10:00:00Z",
    "status": "completed"
  },
  {
    "customer": "Rohan",
    "product": "Headphones",
    "quantity": 1,
    "unit_price": 130,
    "order_date": "2026-06-10T10:00:00Z",
    "status": "cancelled"
  }
]
db.orders.drop()
db.orders.insert_many(orders)
print(f"Inserted {db.orders.count_documents({})} orders into lab5_sales_analytics.orders")

monthly_pipeline = [
    {"$addFields": {"order_total": {"$multiply": ["$quantity", "$unit_price"]},
                    "month": {"$dateToString": {"format": "%Y-%m", "date": {"$toDate": "$order_date"}}}}},
    {"$group": {"_id": "$month", "monthly_revenue": {"$sum": "$order_total"}}},
    {"$sort": {"_id": 1}}
]
show("MONTHLY REVENUE", db.orders.aggregate(monthly_pipeline))

customer_pipeline = [
    {"$addFields": {"order_total": {"$multiply": ["$quantity", "$unit_price"]}}},
    {"$group": {"_id": "$customer", "total_spending": {"$sum": "$order_total"},
                 "products_bought": {"$addToSet": "$product"}}},
    {"$sort": {"total_spending": -1}}, {"$limit": 3}
]
show("TOP 3 CUSTOMERS", db.orders.aggregate(customer_pipeline))

status_pipeline = [
    {"$addFields": {"order_total": {"$multiply": ["$quantity", "$unit_price"]}}},
    {"$group": {"_id": "$status", "average_order_value": {"$avg": "$order_total"},
                 "order_count": {"$sum": 1}}},
    {"$sort": {"_id": 1}}
]
show("AVERAGE ORDER VALUE BY STATUS", db.orders.aggregate(status_pipeline))
