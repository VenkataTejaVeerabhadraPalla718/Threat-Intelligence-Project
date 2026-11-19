import sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))
from pymongo.errors import PyMongoError
from common import client, db

accounts, history = db.accounts, db.transfer_history


def reset():
    accounts.drop(); history.drop()
    accounts.insert_many([{"account_id": "A", "balance": 500, "version": 0},
                          {"account_id": "B", "balance": 200, "version": 0}])


def show(label):
    print(f"{label:38}", {a["account_id"]: a["balance"] for a in accounts.find()})


def transfer(src, dst, amount):
    for attempt in range(5):
        try:
            with client.start_session() as s:
                with s.start_transaction():
                    r = accounts.update_one({"account_id": src, "balance": {"$gte": amount}},
                                            {"$inc": {"balance": -amount, "version": 1}}, session=s)
                    if r.modified_count == 0:
                        raise ValueError("insufficient funds")   # exception = automatic rollback
                    accounts.update_one({"account_id": dst},
                                        {"$inc": {"balance": amount, "version": 1}}, session=s)
                    history.insert_one({"from": src, "to": dst, "amount": amount}, session=s)
            return
        except PyMongoError as e:
            if e.has_error_label("TransientTransactionError"):
                time.sleep(0.1 * 2 ** attempt)    # exponential backoff
                continue
            raise


reset(); show("start")
transfer("A", "B", 100); show("after A->B 100")
try:
    transfer("A", "B", 1000)
except ValueError as e:
    print("rejected:", e)
show("after failed transfer (unchanged)")
print("history rows:", history.count_documents({}), "(expect 1)")