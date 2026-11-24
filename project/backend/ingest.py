import html
import ipaddress
import json
import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

import requests
from common import client, db
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "labs" / "lab07" / "data" / "lab71_dump.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (student CTI lab project)"}
CONTENT_TAG = "{http://purl.org/rss/1.0/modules/content/}encoded"

SOURCES = [
    {"_id": "src_bleeping", "name": "BleepingComputer", "url": "https://www.bleepingcomputer.com",
     "feed_url": "https://www.bleepingcomputer.com/feed/"},
    {"_id": "src_krebs", "name": "Krebs on Security", "url": "https://krebsonsecurity.com",
     "feed_url": "https://krebsonsecurity.com/feed/"},
    {"_id": "src_thn", "name": "The Hacker News", "url": "https://thehackernews.com",
     "feed_url": "https://feeds.feedburner.com/TheHackersNews"},
    {"_id": "src_msft", "name": "Microsoft Security Blog", "url": "https://www.microsoft.com/en-us/security/blog",
     "feed_url": "https://www.microsoft.com/en-us/security/blog/feed/"},
    {"_id": "src_secweek", "name": "SecurityWeek", "url": "https://www.securityweek.com",
     "feed_url": "https://www.securityweek.com/feed/"},
    {"_id": "src_darkread", "name": "Dark Reading", "url": "https://www.darkreading.com",
     "feed_url": "https://www.darkreading.com/rss.xml"},
    {"_id": "src_talos", "name": "Cisco Talos", "url": "https://blog.talosintelligence.com",
     "feed_url": "https://blog.talosintelligence.com/rss/"},
    {"_id": "src_unit42", "name": "Unit 42", "url": "https://unit42.paloaltonetworks.com",
     "feed_url": "https://unit42.paloaltonetworks.com/feed/"},
    {"_id": "src_record", "name": "The Record", "url": "https://therecord.media",
     "feed_url": "https://therecord.media/feed"},
    {"_id": "src_cisa", "name": "CISA Advisories", "url": "https://www.cisa.gov/news-events/cybersecurity-advisories",
     "feed_url": "https://www.cisa.gov/cybersecurity-advisories/all.xml"},
    {"_id": "src_sans", "name": "SANS Internet Storm Center", "url": "https://isc.sans.edu",
     "feed_url": "https://isc.sans.edu/rssfeed.xml"},
    {"_id": "gcve_cisa", "name": "GCVE via CISA", "url": "https://db.gcve.eu",
     "feed_url": "https://db.gcve.eu/cna-root/CISA/recent.rss"},
    {"_id": "gcve_enisa", "name": "GCVE via ENISA", "url": "https://db.gcve.eu",
     "feed_url": "https://db.gcve.eu/cna-root/ENISA/recent.rss"},
    {"_id": "gcve_google", "name": "GCVE via Google", "url": "https://db.gcve.eu",
     "feed_url": "https://db.gcve.eu/cna-root/Google/recent.rss"},
    {"_id": "gcve_redhat", "name": "GCVE via Red Hat", "url": "https://db.gcve.eu",
     "feed_url": "https://db.gcve.eu/cna-root/redhat/recent.rss"},
    {"_id": "gcve_circl", "name": "GCVE via CIRCL", "url": "https://db.gcve.eu",
     "feed_url": "https://db.gcve.eu/recent/gna-1.rss"},
]

RULES = [
    ("Ransomware", ["ransomware", "ransom"]),
    ("Phishing", ["phishing", "phish", "smishing", "social engineering"]),
    ("DDoS", ["ddos", "denial-of-service", "denial of service"]),
    ("Data Breach", ["data breach", "breach", "leak", "stolen data", "extortion"]),
    ("Malware", ["malware", "trojan", "backdoor", "infostealer", "stealer", "spyware", "botnet", "loader"]),
    ("Vulnerability", ["vulnerab", "cve-", "zero-day", "0-day", "rce", "exploit", "flaw", "patch"]),
]

IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")
DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|fun|online|xyz|ru|cn|info|biz|top|site|cc|co|me|eu|ua|us|uk|de|cloud|app|dev|pw|tk|ws)\b",
    re.I)
IGNORE_DOMAINS = {
    "github.com", "aka.ms", "amazonaws.com", "microsoft.com", "google.com", "cloud.google.com",
    "twitter.com", "x.com", "linkedin.com", "youtube.com", "virustotal.com", "gmail.com",
    "proton.me", "zscaler.com", "securelist.com", "archive.org", "upwork.com",
    "bleepingcomputer.com", "krebsonsecurity.com", "thehackernews.com",
}

CVE_IDS = {"gcve_cisa", "gcve_enisa", "gcve_google", "gcve_redhat", "gcve_circl"}


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def classify(text):
    for name, words in RULES:
        if any(w in text for w in words):
            return name
    return "Other"


def severity(cls, text):
    if cls == "Other":
        return "Low"
    if "critical" in text or "zero-day" in text or "0-day" in text:
        return "Critical"
    if any(w in text for w in ["actively exploited", "actively scanned", "ransomware",
                               "breach", "rce", "remote code execution"]):
        return "High"
    return "Medium"


def extract_iocs(text, first_seen):
    found, seen = [], set()

    def add(kind, value):
        if (kind, value) not in seen:
            seen.add((kind, value))
            found.append({"type": kind, "value": value, "first_seen": first_seen})

    for v in SHA256_RE.findall(text):
        add("sha256", v.lower())
    for v in MD5_RE.findall(text):
        add("md5", v.lower())
    refanged = text.replace("[.]", ".")
    for v in IP_RE.findall(refanged):
        try:
            if ipaddress.ip_address(v).is_global:
                add("ip", v)
        except ValueError:
            pass
    for m in DOMAIN_RE.finditer(refanged):
        d = m.group(0).lower()
        if d not in IGNORE_DOMAINS:
            add("domain", d)
    return found


def fetch_source(src):
    r = requests.get(src["feed_url"], headers=HEADERS, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    is_cve = src["_id"] in CVE_IDS
    docs = []
    for it in root.findall(".//item"):
        link, date = it.findtext("link"), it.findtext("pubDate")
        title = clean(it.findtext("title"))
        if not link or not date or not title:
            continue
        summary = clean(it.findtext("description"))
        body = clean(it.findtext(CONTENT_TAG)) or summary
        cats = " ".join(c.text or "" for c in it.findall("category"))
        published = parsedate_to_datetime(date)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        published = published.astimezone(timezone.utc).replace(tzinfo=None)

        rule_text = f"{title} {cats} {summary}".lower()
        if is_cve:
            cls = "Vulnerability"
            if title.upper().startswith("CVE-") and summary:
                title = f"{title}: {summary[:110]}"
        else:
            cls = classify(rule_text)
        docs.append({
            "title": title,
            "content": body[:2000],
            "url": link,
            "source_id": src["_id"],                                  # REFERENCE
            "published_at": published,
            "classification": {"type": cls, "severity": severity(cls, rule_text)},   # EMBEDDED object
            "iocs": [] if is_cve else extract_iocs(f"{title} {body}", published),    # EMBEDDED array
        })
    return docs


def sync_once():
    """Incremental ingestion: never drops existing collections."""
    from pymongo import UpdateOne
    used, operations, seen_links = [], [], set()
    for src in SOURCES:
        try:
            docs = fetch_source(src)
            print(f"{src['name']}: fetched {len(docs)}")
            used.append(src)
            db.sources.update_one({"_id": src["_id"]}, {"$set": src}, upsert=True)
            for doc in docs:
                url = doc.get("url")
                if not url or url in seen_links:
                    continue
                seen_links.add(url)
                doc["record_origin"] = "live_rss"
                doc["verification"] = {
                    "status": "feed_unverified",
                    "checks": ["feed_retrieved", "url_present", "title_present"],
                    "note": "Feed item retrieved; not an independent confirmation that an IOC is malicious."
                }
                operations.append(UpdateOne(
                    {"url": url},
                    {"$set": doc, "$setOnInsert": {"first_ingested_at": __import__("datetime").datetime.utcnow()}},
                    upsert=True
                ))
        except Exception as exc:
            print(f"{src['name']}: FAILED -> {type(exc).__name__}: {str(exc)[:120]}")
    if operations:
        result = db.threats.bulk_write(operations, ordered=False)
        print(f"upserted={result.upserted_count}, modified={result.modified_count}, matched={result.matched_count}")
    db.threats.create_index("url", unique=True, sparse=True)
    db.threats.create_index("classification.type")
    db.threats.create_index([("published_at", -1)])
    db.threats.create_index("source_id")
    print("sources total:", db.sources.count_documents({}))
    print("threats total:", db.threats.count_documents({}))
    return {"sources_seen": len(used), "articles_seen": len(operations),
            "threats_total": db.threats.count_documents({})}


if __name__ == "__main__":
    sync_once()
