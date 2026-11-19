import os
import re

import requests
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["cti"]

LIMIT = 16 * 1024 * 1024  # MongoDB max document size, 16,777,216 bytes

# WiredTiger counter names inside db.serverStatus()["wiredTiger"]["cache"]
REQ = "pages requested from the cache"
READ = "pages read into cache"
INUSE = "bytes currently in the cache"
MAX = "maximum bytes configured"


def cache():
    return db.command("serverStatus")["wiredTiger"]["cache"]


# ---- GitHub list of annual security reports (Lab 7.2 dataset) ----
GITHUB_API = "https://api.github.com/repos/jacobdjwilson/awesome-annual-security-reports/readme"
GH_HEADERS = {"Accept": "application/vnd.github.raw+json", "User-Agent": "student CTI lab project"}
SKIP_HOSTS = ("shields.io", "awesome.re", "linkedin.com", "github.com", "githubusercontent.com")
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")  # [text](url), not ![img](url)


def fetch_readme(etag=None):
    """Returns (text, etag). text is None if GitHub says 'not modified' (HTTP 304)."""
    h = dict(GH_HEADERS)
    if etag:
        h["If-None-Match"] = etag
    r = requests.get(GITHUB_API, headers=h, timeout=20)
    if r.status_code == 304:
        return None, etag
    r.raise_for_status()
    return r.content.decode("utf-8", errors="replace"), r.headers.get("ETag")


def parse_reports(text):
    """Returns {url: vendor} for the report links in the README."""
    if "<!-- BADGES_END -->" in text:
        text = text.split("<!-- BADGES_END -->", 1)[1]
    found = {}
    for title, url in LINK_RE.findall(text):
        if any(h in url for h in SKIP_HOSTS):
            continue
        found.setdefault(url, title.strip())
    return found