import sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from pymongo.errors import PyMongoError
from common import client, db

inventory, orders = db.inventory, db.orders


class OutOfStock(Exception):
    pass


def reserve(pid, qty=1):
    for attempt in range(5):
        try:
            with client.start_session() as s:
                with s.start_transaction():
                    p = inventory.find_one({"product_id": pid}, session=s)
                    if p["stock"] < qty:
                        raise OutOfStock()
                    inventory.update_one({"product_id": pid},
                                         {"$inc": {"stock": -qty, "version": 1}}, session=s)
                    orders.insert_one({"order_id": f"o-{time.time_ns()}", "customer_id": "c1",
                                       "items": [{"product_id": pid, "qty": qty, "price": 10.0}],
                                       "status": "pending", "total": 10.0 * qty}, session=s)
            return "ok"
        except OutOfStock:
            return "out_of_stock"
        except PyMongoError as e:
            if e.has_error_label("TransientTransactionError"):
                time.sleep(0.05 * 2 ** attempt)
                continue
            raise
    return "gave_up"


def reserve_fast(pid, qty=1):       # no transaction: findAndModify
    r = inventory.find_one_and_update({"product_id": pid, "stock": {"$gte": qty}},
                                      {"$inc": {"stock": -qty, "version": 1}})
    return "ok" if r else "out_of_stock"


def run(fn, requests_n, workers, stock):
    inventory.drop(); orders.drop(); db.create_collection("orders")
    inventory.insert_one({"product_id": "p1", "name": "Firewall license", "stock": stock, "version": 0})
    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(lambda _: fn("p1"), range(requests_n)))
    return results, time.perf_counter() - t0


res, _ = run(reserve, 8, 8, 5)
print("A) 8 threads, stock 5:", dict(Counter(res)),
      "| final stock:", inventory.find_one()["stock"], "| orders:", orders.count_documents({}))

print(f"\nB) throughput, 100 requests, stock 100")
print(f"{'threads':8}{'transaction ok/s':20}{'findAndModify ok/s'}")
for w in (1, 4, 8, 16):
    r1, t1 = run(reserve, 100, w, 100)
    r2, t2 = run(reserve_fast, 100, w, 100)
    print(f"{w:<8}{r1.count('ok') / t1:<20.1f}{r2.count('ok') / t2:.1f}")