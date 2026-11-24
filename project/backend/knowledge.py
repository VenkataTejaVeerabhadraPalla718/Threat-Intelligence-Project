"""Built-in knowledge base: instant (zero-model-latency) answers to common short questions.

Pure Python, no database or network access, so it is unit-testable. Longer, detailed, debugging or
how-to questions deliberately fall through to the language model.
"""
import re

LABS = {
    7: ("Data modeling & performance", "Embedded vs referenced documents, working-set reads and monitoring on the CTI Sentinel threat data."),
    8: ("Replication & failover", "Replica-set health, elections, member priority and failover behaviour of the rs0 set."),
    9: ("Write concern & partitions", "Write-acknowledgement latency (w:1 vs majority), journaling and behaviour during a network partition."),
    10: ("Transactions & consistency", "Multi-document transfers, rollback and inventory contention."),
    11: ("Sharding & shard keys", "Shard-key distribution, config servers, mongos routing and hotspot analysis."),
    12: ("Security: RBAC & TLS", "Role-based access control, field redaction and encrypted transport."),
    13: ("Authenticated failover", "Keyfile-protected replica-set authentication and failover."),
    14: ("Monitoring & backup", "Operational metrics plus backup and restore verification with mongodump/mongorestore."),
    15: ("Multi-tenant isolation", "Tenant seeding, API-level isolation, rate limits and migration."),
    16: ("Polyglot persistence", "Using MongoDB together with Cassandra and Neo4j for different data shapes."),
    17: ("Vector search & RAG", "Local embeddings, retrieval-augmented generation and vector benchmarks."),
    18: ("Cross-database benchmark", "Comparing query latency across the different data stores."),
}

CONCEPTS = [
    (("replica set", "replication"), "Replica set",
     "A replica set is a group of MongoDB servers holding the same data: one **primary** takes writes, **secondaries** copy them. If the primary fails, the members hold an election and a secondary becomes primary automatically. Here it is `rs0` with mongo1:27117, mongo2:27118, mongo3:27119."),
    (("shard key",), "Shard key",
     "A shard key is the field MongoDB uses to split a collection across shards. A good key has high cardinality and spreads writes evenly; a monotonically increasing key (like a timestamp) creates a hotspot on one shard."),
    (("sharding", "sharded cluster", "mongos"), "Sharding",
     "Sharding splits data horizontally across several replica sets (shards). **mongos** routers send each query to the right shard, and **config servers** store the cluster metadata and chunk ranges."),
    (("write concern",), "Write concern",
     "Write concern controls how many members must acknowledge a write: `w:1` = primary only (fast), `w:\"majority\"` = most members (durable across failover), and `j:true` also waits for the journal."),
    (("journaling", "journal"), "Journaling",
     "The journal is a write-ahead log. MongoDB records operations there before applying them to data files, so after a crash it can replay the journal and recover committed writes."),
    (("acid", "transaction"), "Transactions",
     "A multi-document transaction applies several writes atomically: all commit or none do (ACID). MongoDB supports them on replica sets and sharded clusters; use them when related documents must change together, e.g. a bank transfer."),
    (("index",), "Index",
     "An index is a sorted structure that lets MongoDB find documents without scanning the whole collection. Use `explain(\"executionStats\")` to confirm a query uses an index (IXSCAN, not COLLSCAN)."),
    (("aggregation pipeline", "aggregation"), "Aggregation pipeline",
     "An aggregation pipeline passes documents through stages such as `$match`, `$group`, `$sort` and `$lookup`. This platform's dashboard charts are built with pipelines."),
    (("cap theorem",), "CAP theorem",
     "During a network partition a distributed database must choose between **consistency** and **availability**. MongoDB favours consistency: a partitioned minority of a replica set cannot accept writes."),
    (("arbiter",), "Arbiter",
     "An arbiter is a replica-set member that votes in elections but stores no data. It breaks ties cheaply, but it cannot acknowledge majority writes, so it is used sparingly."),
    (("docker compose",), "Docker Compose",
     "Docker Compose starts several containers from one `docker-compose.yml`. Useful commands: `docker compose up -d`, `docker compose ps`, `docker compose logs --tail=80 api`, `docker compose stop`. Avoid `down -v`, which deletes volumes."),
    (("jwt", "json web token"), "JWT",
     "A JSON Web Token is a signed token proving who you are. SENTINEL-X issues one at login (with expiry and a unique ID), checks it on every API call, and revokes it on logout."),
    (("rbac", "role based access", "role-based access"), "RBAC",
     "Role-based access control grants permissions by role. In SENTINEL-X there are two roles: **User** (read data, use the assistant) and **Admin** (also manage users, view audit logs and run experiments)."),
    (("argon2", "password hashing"), "Password hashing",
     "Argon2id is a memory-hard password hash, so brute-forcing stolen hashes is expensive. Each password gets its own random salt, and plain-text passwords are never stored."),
    (("rag", "retrieval augmented", "retrieval-augmented"), "RAG",
     "Retrieval-augmented generation first searches your own data (via embeddings/vector search), then gives the matching passages to the language model so its answer is grounded in real records."),
    (("vector search", "embedding"), "Vector search",
     "An embedding turns text into a list of numbers; similar meanings land close together. Vector search finds the nearest embeddings, which is how Lab 17 retrieves relevant threat records."),
    (("ioc", "indicator of compromise"), "IOC",
     "An indicator of compromise is an observable artefact such as an IP, domain or file hash associated with malicious activity. A feed listing an IOC does not by itself prove it is malicious."),
]

_SKIP = re.compile(r"\b(detail\w*|deep\w*|step\w*|code|example\w*|why|error\w*|debug|fix|how do i|how to|compare|difference|versus|vs|run|execute|start|status|output|result\w*)\b", re.I)
_ASK = re.compile(r"^(what('?s| is| are)|whats|explain|define|meaning of|tell me about|describe|about)\b", re.I)


def answer(message: str):
    """Return an instant answer for short definition-style questions, else None."""
    m = (message or "").strip().rstrip("?.! ")
    low = m.lower()
    if not m or len(m.split()) > 10 or _SKIP.search(low):
        return None
    lab = re.search(r"\blab\s*(1[0-8]|[7-9])\b", low)
    if lab and (_ASK.match(low) or re.match(r"^lab\s*\d+$", low)):
        n = int(lab.group(1)); title, text = LABS[n]
        return (f"**Lab {n} · {title}**\n{text}\n\nOpen *Experiments → Lab {n}* for its prerequisites, scripts and runnable steps. "
                f"Ask a longer follow-up (e.g. \"explain lab {n} step by step\") for a detailed model-generated walkthrough.")
    if _ASK.match(low) or len(low.split()) <= 3:
        for keys, title, text in CONCEPTS:
            if any(re.search(rf"\b{re.escape(k)}s?\b", low) for k in keys):
                return f"**{title}**\n{text}\n\nAsk a more detailed follow-up for a deeper model-generated explanation."
    return None
