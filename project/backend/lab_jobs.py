"""Persistent background execution for the registered SENTINEL-X lab allow-list."""
from __future__ import annotations
import os, subprocess, sys, threading, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from pymongo import DESCENDING
from common import db

ROOT = Path(__file__).resolve().parent.parent
_LOCK = threading.RLock()
_PROCESSES: dict[str, subprocess.Popen] = {}
_MAX_OUTPUT = 120_000


def _now():
    return datetime.now(timezone.utc)


def _append(job_id: str, chunk: str, buf: list[str]):
    buf.append(chunk)
    joined = "".join(buf)
    if len(joined) > _MAX_OUTPUT:
        joined = "[Earlier output trimmed to keep the live console responsive.]\n" + joined[-_MAX_OUTPUT:]
        buf[:] = [joined]
    db.lab_jobs.update_one({"job_id": job_id}, {"$set": {"output": joined, "updated_at": _now()}})


def _worker(job_id: str, exp_id: str, lab: str, title: str, script: str, args: list[str], triggered_by: str | None):
    started = time.perf_counter()
    buf: list[str] = []
    env = os.environ.copy()
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
    # Lab 1 is offline; Labs 2-4 use their own isolated databases on the local replica set.
    env.setdefault("MONGO_URI", "mongodb://mongo1:27117,mongo2:27118,mongo3:27119/?replicaSet=rs0")
    env.setdefault("CTI_MONGO_URI", env["MONGO_URI"])
    env.setdefault("MONGODB_URI", env["MONGO_URI"])
    env.setdefault("LAB18_REQUIRED_RECORDS", "300000")
    env.setdefault("NEO4J_PASSWORD", "change-this-local")
    env.setdefault("CASSANDRA_HOST", "cassandra")
    env.setdefault("CASSANDRA_PORT", "9042")
    env.setdefault("LAB11_MONGO_URI", "mongodb://host.docker.internal:27217")
    env.setdefault("LAB12_RBAC_URI", "mongodb://admin:admin123@host.docker.internal:27200/?authSource=admin")
    env.setdefault("LAB12_TLS_HOST", "host.docker.internal")
    env.setdefault("LAB12_TLS_PORT", "27201")
    if exp_id == "l13-authfail" and not env.get("KEYFILE_MONGO_URI"):
        db.lab_jobs.update_one({"job_id": job_id}, {"$set": {"status": "failed", "finished_at": _now(),
            "error": "KEYFILE_MONGO_URI is required for Lab 13. Start the dedicated keyfile replica-set stack and configure its URI.",
            "output": "Lab 13 was not started: KEYFILE_MONGO_URI is not configured.\n", "updated_at": _now()}})
        return
    cmd = [sys.executable, "-u", str(ROOT / script), *args]
    db.lab_jobs.update_one({"job_id": job_id}, {"$set": {"status": "running", "started_at": _now(), "command": f"python {script} {' '.join(args)}"}})
    try:
        p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
        with _LOCK:
            _PROCESSES[job_id] = p
        last_flush = time.monotonic()
        pending = []
        assert p.stdout is not None
        for line in p.stdout:
            pending.append(line)
            if time.monotonic() - last_flush >= 0.35 or len(pending) >= 12:
                _append(job_id, "".join(pending), buf)
                pending.clear(); last_flush = time.monotonic()
        if pending:
            _append(job_id, "".join(pending), buf)
        code = p.wait()
        ok = code == 0
        status = "passed" if ok else "failed"
        if not buf:
            _append(job_id, "(No output produced.)\n", buf)
        elapsed = round(time.perf_counter() - started, 2)
        output = "".join(buf)[-_MAX_OUTPUT:]
        db.lab_jobs.update_one({"job_id": job_id}, {"$set": {"status": status, "return_code": code,
            "seconds": elapsed, "finished_at": _now(), "output": output, "updated_at": _now()}})
        db.experiment_runs.insert_one({"exp": exp_id, "lab": lab, "title": title, "ok": ok, "status": status,
            "seconds": elapsed, "output": output[-12000:], "job_id": job_id, "ts": _now(), "triggered_by": triggered_by})
    except Exception as exc:
        msg = f"\n[runner error] {type(exc).__name__}: {str(exc)[:500]}\n"
        _append(job_id, msg, buf)
        db.lab_jobs.update_one({"job_id": job_id}, {"$set": {"status": "failed", "finished_at": _now(),
            "seconds": round(time.perf_counter()-started, 2), "error": str(exc)[:500], "updated_at": _now()}})
    finally:
        with _LOCK:
            _PROCESSES.pop(job_id, None)


def start_job(exp_id: str, meta: tuple, triggered_by: str | None = None) -> dict:
    lab, title, script, args = meta
    with _LOCK:
        if db.lab_jobs.count_documents({"status": {"$in": ["queued", "running"]}}):
            raise RuntimeError("Another lab is already running. Wait for it to finish before starting another run.")
        job_id = uuid.uuid4().hex
        doc = {"job_id": job_id, "exp": exp_id, "lab": lab, "title": title, "status": "queued", "output":
               f"[SENTINEL-X] Queued {lab} · {title}\n", "created_at": _now(), "updated_at": _now(),
               "triggered_by": triggered_by}
        db.lab_jobs.insert_one(doc)
        t = threading.Thread(target=_worker, args=(job_id, exp_id, lab, title, script, args, triggered_by),
                             daemon=True, name=f"lab-{lab}-{job_id[:8]}")
        t.start()
    return {k: v for k, v in doc.items() if k != "_id"}


def get_job(job_id: str):
    return db.lab_jobs.find_one({"job_id": job_id}, {"_id": 0})


def latest_job(lab: int | str):
    return db.lab_jobs.find_one({"lab": {"$regex": rf"^{int(lab)}(?:\\.|$)"}}, {"_id": 0}, sort=[("created_at", DESCENDING)])


def recover_interrupted_jobs():
    """Mark jobs from a previous API process as interrupted; never auto-rerun them."""
    now = _now()
    return db.lab_jobs.update_many({"status": {"$in": ["queued", "running"]}},
        {"$set": {"status": "interrupted", "finished_at": now, "updated_at": now,
                  "error": "API restarted while this job was active. Review the saved output before starting it again."}}).modified_count
