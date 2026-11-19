"""Kubernetes-backed Lab16 -> Lab18 workflow for SENTINEL-X.

The API creates uniquely named Jobs from the reviewed manifests, streams pod logs
into MongoDB lab_jobs, and only creates Lab18 after Lab16 succeeds.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from common import db

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = ROOT / "k8s"
KUBECONFIG = os.getenv("KUBECONFIG", "/root/.kube/config")
NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
API_SERVER = os.getenv("K8S_API_SERVER", "https://kubernetes.docker.internal:6443").strip()
POLL_SECONDS = max(2, int(os.getenv("K8S_JOB_POLL_SECONDS", "3")))
_LOCK = threading.RLock()
_ACTIVE: set[str] = set()


def _now():
    return datetime.now(timezone.utc)


def _kube_apis():
    if not Path(KUBECONFIG).is_file():
        raise RuntimeError(f"Kubernetes config not found inside API container: {KUBECONFIG}")
    cfg = client.Configuration()
    config.load_kube_config(config_file=KUBECONFIG, client_configuration=cfg)
    # Docker Desktop's API endpoint must be reachable from the API container.
    # TLS verification remains enabled; only the endpoint host is normalized.
    if API_SERVER:
        cfg.host = API_SERVER
    api_client = client.ApiClient(cfg)
    return client.BatchV1Api(api_client), client.CoreV1Api(api_client)


def _job_manifest(lab: int, workflow_id: str) -> dict:
    path = MANIFESTS / f"lab{lab}-job.yaml"
    if not path.is_file():
        raise RuntimeError(f"Kubernetes manifest missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    suffix = workflow_id[:10]
    manifest.setdefault("metadata", {})["name"] = f"sentinelx-lab{lab}-{suffix}"
    manifest["metadata"].setdefault("labels", {}).update({
        "app": "sentinelx", "lab": str(lab), "workflow-id": workflow_id[:20]
    })
    pod_meta = manifest.setdefault("spec", {}).setdefault("template", {}).setdefault("metadata", {})
    pod_meta.setdefault("labels", {}).update({
        "app": "sentinelx", "lab": str(lab), "workflow-id": workflow_id[:20]
    })
    return manifest


def _append_output(workflow_id: str, text: str):
    if not text:
        return
    db.lab_jobs.update_one(
        {"job_id": workflow_id},
        {"$set": {"updated_at": _now()}, "$push": {"output_chunks": {"$each": [text], "$slice": -500}}},
    )
    # Keep a convenient bounded output field for the existing dashboard console.
    doc = db.lab_jobs.find_one({"job_id": workflow_id}, {"output_chunks": 1}) or {}
    output = "".join(doc.get("output_chunks", []))[-120000:]
    db.lab_jobs.update_one({"job_id": workflow_id}, {"$set": {"output": output}})


def _create_job(batch: client.BatchV1Api, lab: int, workflow_id: str) -> str:
    manifest = _job_manifest(lab, workflow_id)
    name = manifest["metadata"]["name"]
    try:
        batch.create_namespaced_job(namespace=NAMESPACE, body=manifest)
    except ApiException as exc:
        raise RuntimeError(f"Could not create Lab{lab} Kubernetes Job ({exc.status}): {exc.reason}") from exc
    db.lab_jobs.update_one(
        {"job_id": workflow_id},
        {"$set": {f"kubernetes.lab{lab}.job_name": name,
                  f"kubernetes.lab{lab}.status": "created", "updated_at": _now()}},
    )
    _append_output(workflow_id, f"\n[SENTINEL-X] Created Kubernetes Job {name} in namespace {NAMESPACE}.\n")
    return name


def _job_logs(core: client.CoreV1Api, job_name: str) -> str:
    pods = core.list_namespaced_pod(namespace=NAMESPACE, label_selector=f"job-name={job_name}").items
    chunks = []
    for pod in pods:
        try:
            value = core.read_namespaced_pod_log(
                name=pod.metadata.name, namespace=NAMESPACE, container=None,
                timestamps=False, _preload_content=True,
            )
            if value:
                chunks.append(f"\n--- {pod.metadata.name} ---\n{value.rstrip()}\n")
        except ApiException:
            continue
    return "".join(chunks)


def _wait_for_job(batch: client.BatchV1Api, core: client.CoreV1Api, lab: int,
                  job_name: str, workflow_id: str, timeout_seconds: int) -> bool:
    started = time.monotonic()
    last_logs = ""
    while time.monotonic() - started < timeout_seconds:
        job = batch.read_namespaced_job_status(name=job_name, namespace=NAMESPACE)
        logs = _job_logs(core, job_name)
        if logs and logs != last_logs:
            # Kubernetes pod logs are cumulative; replace the step's captured log
            # and append only the newly observed suffix where possible.
            previous = last_logs
            delta = logs[len(previous):] if logs.startswith(previous) else logs
            if delta:
                _append_output(workflow_id, delta)
            last_logs = logs
        if (job.status.succeeded or 0) >= 1:
            db.lab_jobs.update_one({"job_id": workflow_id}, {"$set": {
                f"kubernetes.lab{lab}.status": "complete", "updated_at": _now()
            }})
            _append_output(workflow_id, f"\n[SENTINEL-X] Lab{lab} Kubernetes Job completed successfully.\n")
            return True
        if (job.status.failed or 0) >= 1:
            db.lab_jobs.update_one({"job_id": workflow_id}, {"$set": {
                f"kubernetes.lab{lab}.status": "failed", "updated_at": _now()
            }})
            _append_output(workflow_id, f"\n[SENTINEL-X] Lab{lab} failed. Lab18 will not be started.\n")
            return False
        time.sleep(POLL_SECONDS)
    _append_output(workflow_id, f"\n[SENTINEL-X] Lab{lab} exceeded its {timeout_seconds // 60}-minute workflow timeout.\n")
    return False


def _run_workflow(workflow_id: str, triggered_by: str | None):
    started = time.monotonic()
    try:
        batch, core = _kube_apis()
        db.lab_jobs.update_one({"job_id": workflow_id}, {"$set": {
            "status": "running", "started_at": _now(), "updated_at": _now()
        }})
        _append_output(workflow_id, "[SENTINEL-X] Kubernetes connection established. Starting Lab16.\n")
        lab16_name = _create_job(batch, 16, workflow_id)
        if not _wait_for_job(batch, core, 16, lab16_name, workflow_id, 10800):
            _finish(workflow_id, "failed", started, "Lab16 did not complete successfully; Lab18 was skipped.")
            return
        _append_output(workflow_id, "\n[SENTINEL-X] Lab16 succeeded. Starting Lab18 benchmark automatically.\n")
        lab18_name = _create_job(batch, 18, workflow_id)
        if not _wait_for_job(batch, core, 18, lab18_name, workflow_id, 3600):
            _finish(workflow_id, "failed", started, "Lab18 did not complete successfully.")
            return
        _finish(workflow_id, "passed", started, None)
    except Exception as exc:
        message = f"\n[Kubernetes workflow error] {type(exc).__name__}: {str(exc)[:700]}\n"
        _append_output(workflow_id, message)
        _finish(workflow_id, "failed", started, str(exc)[:700])
    finally:
        with _LOCK:
            _ACTIVE.discard(workflow_id)


def _finish(workflow_id: str, status: str, started: float, error: str | None):
    doc = db.lab_jobs.find_one({"job_id": workflow_id}) or {}
    output = doc.get("output", "")
    seconds = round(time.monotonic() - started, 2)
    db.lab_jobs.update_one({"job_id": workflow_id}, {"$set": {
        "status": status, "finished_at": _now(), "seconds": seconds,
        "error": error, "updated_at": _now(), "output": output,
    }})
    db.experiment_runs.insert_one({
        "exp": "l16-l18-kubernetes", "lab": "16-18", "title": "Kubernetes Lab16 → Lab18 workflow",
        "ok": status == "passed", "status": status, "seconds": seconds,
        "output": output[-12000:], "job_id": workflow_id, "ts": _now(), "triggered_by": doc.get("triggered_by"),
        "backend": "kubernetes",
    })


def kubernetes_health() -> dict:
    """Verify the API container can authenticate to and query its Kubernetes cluster."""
    batch, core = _kube_apis()
    batch.list_namespaced_job(namespace=NAMESPACE, limit=1)
    return {"ok": True, "namespace": NAMESPACE, "api_server": API_SERVER, "message": "Kubernetes API reachable and authenticated"}


def start_workflow(triggered_by: str | None = None) -> dict:
    with _LOCK:
        active = db.lab_jobs.find_one({"backend": "kubernetes", "status": {"$in": ["queued", "running"]}})
        if active or _ACTIVE:
            raise RuntimeError("A Kubernetes Lab16 → Lab18 workflow is already running. Wait for it to finish.")
        workflow_id = uuid.uuid4().hex
        doc = {
            "job_id": workflow_id, "exp": "l16-l18-kubernetes", "lab": "16-18",
            "title": "Kubernetes Lab16 → Lab18 workflow", "backend": "kubernetes",
            "status": "queued", "output": "[SENTINEL-X] Kubernetes Lab16 → Lab18 workflow queued.\n",
            "output_chunks": [], "created_at": _now(), "updated_at": _now(),
            "triggered_by": triggered_by, "kubernetes": {},
        }
        db.lab_jobs.insert_one(doc)
        _ACTIVE.add(workflow_id)
        thread = threading.Thread(target=_run_workflow, args=(workflow_id, triggered_by),
                                  daemon=True, name=f"k8s-l16-l18-{workflow_id[:8]}")
        thread.start()
        return {k: v for k, v in doc.items() if k not in ("_id", "output_chunks")}


def get_workflow(workflow_id: str):
    return db.lab_jobs.find_one({"job_id": workflow_id, "backend": "kubernetes"}, {"_id": 0, "output_chunks": 0})


def latest_workflow():
    return db.lab_jobs.find_one({"backend": "kubernetes"}, {"_id": 0, "output_chunks": 0}, sort=[("created_at", -1)])


def workflow_report(workflow_id: str) -> str:
    doc = get_workflow(workflow_id)
    if not doc:
        raise KeyError("Workflow not found")
    output = doc.get("output", "")
    marker = "# Lab 18: Cross-Database Benchmark"
    pos = output.find(marker)
    if pos < 0:
        raise ValueError("Lab18 benchmark report is not available yet. Wait for Lab18 to finish.")
    return output[pos:].strip() + "\n"


def recover_k8s_workflows():
    """Resume monitoring existing Kubernetes Jobs after an API container restart."""
    docs = list(db.lab_jobs.find({"backend": "kubernetes", "status": {"$in": ["queued", "running"]}}))
    for doc in docs:
        workflow_id = doc["job_id"]
        with _LOCK:
            if workflow_id in _ACTIVE:
                continue
            _ACTIVE.add(workflow_id)
        thread = threading.Thread(target=_resume_workflow, args=(workflow_id,), daemon=True,
                                  name=f"k8s-resume-{workflow_id[:8]}")
        thread.start()
    return len(docs)


def _resume_workflow(workflow_id: str):
    """Best-effort recovery: continue monitoring recorded jobs, without recreating completed data jobs."""
    started = time.monotonic()
    try:
        batch, core = _kube_apis()
        doc = get_workflow(workflow_id) or {}
        k8s = doc.get("kubernetes", {})
        for lab, timeout in ((16, 10800), (18, 3600)):
            info = k8s.get(f"lab{lab}", {})
            name = info.get("job_name")
            if not name:
                if lab == 16:
                    name = _create_job(batch, 16, workflow_id)
                else:
                    _finish(workflow_id, "failed", started, "API restarted before Lab18 was recorded; inspect history before retrying.")
                    return
            try:
                batch.read_namespaced_job(name=name, namespace=NAMESPACE)
            except ApiException as exc:
                if exc.status == 404:
                    _finish(workflow_id, "failed", started, f"Kubernetes Job {name} no longer exists; not rerunning automatically.")
                    return
                raise
            if not _wait_for_job(batch, core, lab, name, workflow_id, timeout):
                _finish(workflow_id, "failed", started, f"Lab{lab} did not complete after API recovery.")
                return
            if lab == 16 and not k8s.get("lab18", {}).get("job_name"):
                _append_output(workflow_id, "\n[SENTINEL-X] Recovered Lab16 success; starting Lab18.\n")
                _create_job(batch, 18, workflow_id)
                doc = get_workflow(workflow_id) or {}
                k8s = doc.get("kubernetes", {})
        _finish(workflow_id, "passed", started, None)
    except Exception as exc:
        _append_output(workflow_id, f"\n[Kubernetes recovery error] {type(exc).__name__}: {str(exc)[:700]}\n")
        _finish(workflow_id, "failed", started, str(exc)[:700])
    finally:
        with _LOCK:
            _ACTIVE.discard(workflow_id)
