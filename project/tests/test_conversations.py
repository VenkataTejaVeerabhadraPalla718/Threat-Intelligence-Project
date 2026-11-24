"""API tests for Boss saved conversations (uses an in-memory MongoDB, no Docker/Ollama needed).

Run:  pip install mongomock httpx   then   python -m pytest tests/test_conversations.py
"""
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("JWT_SECRET", "x" * 40)

try:
    import mongomock
    import pymongo
    from fastapi.testclient import TestClient
    pymongo.MongoClient = mongomock.MongoClient   # must happen before the backend imports common.py
    import main
    from saas import current_user
    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False

USER = {"sub": "alice", "role": "user", "tenant": "sentinelx", "uid": "1"}


def events(resp):
    return [json.loads(x[5:]) for x in resp.text.split("\n\n") if x.startswith("data:")]


@unittest.skipUnless(AVAILABLE, "mongomock/httpx not installed")
class ConversationTests(unittest.TestCase):
    def setUp(self):
        main.db.assistant_history.delete_many({}); main.db.assistant_conversations.delete_many({})
        self.who = dict(USER)
        main.app.dependency_overrides[current_user] = lambda: self.who
        self.c = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides.clear()

    def ask(self, text, cid=None, lab=None):
        r = self.c.post("/api/assistant/stream", json={"message": text, "lab": lab, "conversation_id": cid})
        self.assertEqual(r.status_code, 200)
        ev = events(r)
        return ev[0]["conversation_id"], ev

    def test_chat_is_saved_listed_resumed_and_titled(self):
        cid, ev = self.ask("what is a replica set")
        self.assertEqual(ev[0]["type"], "meta")
        cid2, _ = self.ask("what is a shard key", cid)
        self.assertEqual(cid, cid2)
        lst = self.c.get("/api/conversations").json()["conversations"]
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["title"], "what is a replica set")
        self.assertEqual(lst[0]["message_count"], 2)
        got = self.c.get(f"/api/conversations/{cid}").json()
        self.assertEqual([m["message"] for m in got["messages"]], ["what is a replica set", "what is a shard key"])

    def test_boss_name_works_with_tools_and_knowledge(self):
        cid, ev = self.ask("Hey Boss, what is a replica set?")
        final = [e for e in ev if e["type"] == "final"][0]
        self.assertEqual(final["mode"], "knowledge")
        _, ev = self.ask("Boss")
        self.assertIn("I'm Boss", [e for e in ev if e["type"] == "final"][0]["reply"])
        _, ev = self.ask("who are you?")
        self.assertIn("Boss", [e for e in ev if e["type"] == "final"][0]["reply"])

    def test_rename_pin_search_export_regenerate_delete(self):
        cid, _ = self.ask("what is a replica set")
        other, _ = self.ask("what is a shard key")
        self.assertEqual(self.c.patch(f"/api/conversations/{other}", json={"pinned": True}).json()["pinned"], True)
        self.assertEqual(self.c.get("/api/conversations").json()["conversations"][0]["id"], other)  # pinned first
        self.assertEqual(self.c.patch(f"/api/conversations/{cid}", json={"title": "Replica notes"}).json()["title"], "Replica notes")
        self.assertEqual(self.c.patch(f"/api/conversations/{cid}", json={"title": "  "}).status_code, 400)
        hits = self.c.get("/api/conversations", params={"q": "shard"}).json()["conversations"]
        self.assertEqual([h["id"] for h in hits], [other])
        md = self.c.get(f"/api/conversations/{cid}/export")
        self.assertIn("**Boss:**", md.text); self.assertIn("attachment", md.headers["content-disposition"])
        self.assertEqual(self.c.delete(f"/api/conversations/{cid}/messages/last").json()["message"], "what is a replica set")
        self.assertEqual(self.c.delete(f"/api/conversations/{other}").json()["ok"], True)
        self.assertEqual(self.c.get(f"/api/conversations/{other}").status_code, 404)

    def test_users_cannot_see_or_touch_each_others_chats(self):
        cid, _ = self.ask("what is a replica set")
        self.who = {**USER, "sub": "bob"}
        self.assertEqual(self.c.get("/api/conversations").json()["conversations"], [])
        self.assertEqual(self.c.get(f"/api/conversations/{cid}").status_code, 404)
        self.assertEqual(self.c.delete(f"/api/conversations/{cid}").status_code, 404)
        self.assertEqual(self.c.post("/api/assistant/stream", json={"message": "hi there boss", "conversation_id": cid}).status_code, 404)
        self.who = dict(USER)
        self.assertEqual(len(self.c.get("/api/conversations").json()["conversations"]), 1)

    def test_old_history_is_adopted_and_delete_all(self):
        main.db.assistant_history.insert_one({"username": "alice", "lab": "8", "message": "old q", "reply": "old a", "answer_mode": "llm"})
        lst = self.c.get("/api/conversations").json()["conversations"]
        self.assertEqual(lst[0]["title"], "Earlier chat · Lab 8")
        self.assertEqual(self.c.get(f"/api/conversations/{lst[0]['id']}").json()["messages"][0]["reply"], "old a")
        self.ask("what is a replica set")
        self.assertEqual(self.c.delete("/api/conversations").json()["deleted_conversations"], 2)
        self.assertEqual(self.c.get("/api/conversations").json()["conversations"], [])


if __name__ == "__main__":
    unittest.main()
