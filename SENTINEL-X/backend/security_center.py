"""SENTINEL-X security findings, dependency scanning and safe remediation guidance.

Scans are read-only. Real host changes must be approved and performed through
the operating system's trusted security tools.
"""
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
import json
import os
import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from common import db
from saas import current_user

router = APIRouter(prefix="/api/security", dependencies=[Depends(current_user)])
SEVERITIES = {"info", "low", "medium", "high", "critical"}


def now():
    return datetime.now(timezone.utc)


def _tenant(user):
    return user["tenant"]


def _fingerprint(tenant, source, category, identity):
    raw = "|".join(str(v).strip().lower() for v in (tenant, source, category, identity))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _record_finding(*, tenant, title, severity, category, details, source,
                    identity=None, simulated=False, reported_by=None,
                    recommendation=None, evidence=None):
    identity = identity or title
    fingerprint = _fingerprint(tenant, source, category, identity)
    timestamp = now()
    finding_id = uuid4().hex
    update = {
        "$set": {
            "title": title[:180], "severity": severity, "category": category[:80],
            "details": details[:4000], "source": source[:100],
            "status": "detected", "simulated": bool(simulated),
            "last_seen": timestamp, "updated_at": timestamp,
            "recommendation": (recommendation or "")[:2000],
            "evidence": evidence or {},
        },
        "$setOnInsert": {
            "finding_id": finding_id, "tenant_id": tenant,
            "created_at": timestamp, "cleared_at": None, "resolution": None,
            "reported_by": reported_by, "occurrences": 0,
            "fingerprint": fingerprint,
        },
        "$inc": {"occurrences": 1},
    }
    db.security_findings.update_one(
        {"tenant_id": tenant, "fingerprint": fingerprint}, update, upsert=True
    )
    return db.security_findings.find_one(
        {"tenant_id": tenant, "fingerprint": fingerprint}, {"_id": 0}
    )


def _serialise(x):
    return {
        "id": x.get("finding_id", ""),
        "title": x.get("title", "Untitled finding"),
        "severity": x.get("severity", "info"),
        "category": x.get("category", "general"),
        "details": x.get("details", ""),
        "source": x.get("source", "unknown"),
        "status": x.get("status", "detected"),
        "simulated": bool(x.get("simulated", False)),
        "created_at": x.get("created_at", now()).isoformat(),
        "last_seen": x.get("last_seen").isoformat() if x.get("last_seen") else None,
        "occurrences": int(x.get("occurrences", 1)),
        "cleared_at": x.get("cleared_at").isoformat() if x.get("cleared_at") else None,
        "resolution": x.get("resolution"),
        "recommendation": x.get("recommendation", ""),
        "evidence": x.get("evidence", {}),
    }


@router.get("/findings")
def findings(user=Depends(current_user)):
    rows = db.security_findings.find(
        {"tenant_id": _tenant(user)}
    ).sort("last_seen", -1).limit(200)
    items = [_serialise(x) for x in rows]
    return {
        "findings": items,
        "active": sum(x["status"] == "detected" for x in items),
        "cleared": sum(x["status"] == "cleared" for x in items),
        "simulated": sum(bool(x["simulated"]) for x in items),
        "critical": sum(x["severity"] == "critical" and x["status"] == "detected" for x in items),
    }


@router.post("/demo")
def create_demo(user=Depends(current_user)):
    tenant = _tenant(user)
    x = _record_finding(
        tenant=tenant, title="Untrusted startup entry (DEMO)", severity="high",
        category="persistence",
        details="Harmless synthetic test indicator. No file, process, registry key or Windows setting was changed.",
        source="SENTINEL-X controlled demo", identity="sample-suspicious-startup",
        simulated=True, reported_by=user.get("sub"),
        recommendation="This is a demonstration record only. Clear it using the demo control.",
    )
    return {"ok": True, "finding": _serialise(x),
            "message": "Demo finding recorded. No host change was made."}


@router.post("/findings/{finding_id}/clear")
def clear_finding(finding_id: str, user=Depends(current_user)):
    query = {"finding_id": finding_id, "tenant_id": _tenant(user)}
    x = db.security_findings.find_one(query)
    if not x:
        raise HTTPException(404, "Finding not found.")
    if not x.get("simulated"):
        raise HTTPException(
            409,
            "Real findings cannot be cleared here. Remediate using the trusted operating-system or package tool, then rescan.",
        )
    timestamp = now()
    db.security_findings.update_one(query, {"$set": {
        "status": "cleared", "cleared_at": timestamp, "updated_at": timestamp,
        "resolution": "Synthetic demo indicator cleared from SENTINEL-X records. No host object was changed.",
    }})
    return {"ok": True, "message": "Demo finding cleared.", 
            "finding": _serialise(db.security_findings.find_one(query))}


class AgentReport(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    severity: str = Field(pattern="^(info|low|medium|high|critical)$")
    category: str = Field(min_length=2, max_length=80)
    details: str = Field(default="", max_length=4000)
    source: str = Field(default="SENTINEL-X Windows host agent", max_length=100)
    identifier: str | None = Field(default=None, max_length=200)
    recommendation: str = Field(default="", max_length=2000)
    evidence: dict = Field(default_factory=dict)


@router.post("/agent-report")
def agent_report(body: AgentReport, user=Depends(current_user)):
    x = _record_finding(
        tenant=_tenant(user), title=body.title, severity=body.severity,
        category=body.category, details=body.details, source=body.source,
        identity=body.identifier or body.title, reported_by=user.get("sub"),
        recommendation=body.recommendation, evidence=body.evidence,
    )
    return {"ok": True, "finding": _serialise(x),
            "message": "Host observation recorded or updated. Review the recommended action before making changes."}


@router.post("/scan/dependencies")
def scan_dependencies(user=Depends(current_user)):
    """Audit the API's pinned dependency manifest with pip-audit (fixed command only)."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator permission required to start a dependency scan.")

    requirements = os.getenv("SENTINELX_REQUIREMENTS_FILE", "/app/backend/requirements.txt")
    if not os.path.isfile(requirements):
        raise HTTPException(503, "Dependency manifest was not found in this runtime.")

    command = [
        sys.executable, "-m", "pip_audit", "-r", requirements,
        "-f", "json", "--progress-spinner", "off",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180,
            cwd=os.path.dirname(requirements) or None, check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Dependency scan timed out after 180 seconds.")
    except OSError as exc:
        raise HTTPException(503, f"Could not start pip-audit: {exc.__class__.__name__}")

    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        detail = (result.stderr or result.stdout or "No scanner output")[-1500:]
        raise HTTPException(502, "Dependency scanner returned unreadable output: " + detail)

    tenant = _tenant(user)
    detected = 0
    for package in payload if isinstance(payload, list) else []:
        package_name = str(package.get("name", "unknown"))
        installed = str(package.get("version", "unknown"))
        for vuln in package.get("vulns", []) or []:
            aliases = vuln.get("aliases") or []
            cve = next((a for a in aliases if str(a).startswith("CVE-")), None)
            vuln_id = str(vuln.get("id") or cve or "UNKNOWN")
            fixes = vuln.get("fix_versions") or []
            description = str(vuln.get("description") or "Known vulnerability reported by pip-audit.")
            title = f"Vulnerable Python dependency: {package_name} ({vuln_id})"
            recommendation = (
                f"Upgrade {package_name} from {installed} to a fixed version: "
                + (", ".join(map(str, fixes)) if fixes else "check the advisory for a supported patched release")
                + ". Test the application before deploying the change."
            )
            _record_finding(
                tenant=tenant, title=title, severity="medium", category="dependency-vulnerability",
                details=f"{package_name} {installed} is affected. {description} Severity is a medium triage default because pip-audit does not provide a CVSS score in this output; verify the vendor advisory.",
                source="pip-audit", identity=f"{package_name}:{installed}:{vuln_id}",
                reported_by=user.get("sub"), recommendation=recommendation,
                evidence={"package": package_name, "installed_version": installed,
                          "vulnerability_id": vuln_id, "aliases": aliases,
                          "fix_versions": fixes, "severity_source": "medium triage default; verify vendor advisory"},
            )
            detected += 1

    scan_doc = {
        "tenant_id": tenant, "scanner": "pip-audit",
        "created_at": now(), "vulnerabilities": detected,
        "packages_with_findings": len(payload) if isinstance(payload, list) else 0,
        "exit_code": result.returncode,
    }
    db.security_scans.insert_one(scan_doc)
    return {
        "ok": True, "scanner": "pip-audit", "vulnerabilities": detected,
        "packages_checked_with_findings": scan_doc["packages_with_findings"],
        "message": (f"Scan completed: {detected} vulnerable package advisory finding(s) recorded."
                    if detected else "No vulnerable dependencies were reported by pip-audit for this manifest."),
        "note": "This checks the API dependency manifest only; it does not scan Windows, Docker images or every installed host application.",
    }


class AgentControlUpdate(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=15, ge=5, le=1440)


@router.get("/agent-control")
def get_agent_control(user=Depends(current_user)):
    """Return this tenant's desired Windows-agent monitoring state."""
    row = db.security_agent_controls.find_one(
        {"tenant_id": _tenant(user)}, {"_id": 0}
    ) or {}
    return {
        "enabled": bool(row.get("enabled", False)),
        "interval_minutes": int(row.get("interval_minutes", 15)),
        "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }


@router.post("/agent-control")
def set_agent_control(body: AgentControlUpdate, user=Depends(current_user)):
    """Enable/disable continuous host checks; only an administrator can change it."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Administrator permission required to change host monitoring.")
    timestamp = now()
    db.security_agent_controls.update_one(
        {"tenant_id": _tenant(user)},
        {"$set": {
            "enabled": body.enabled,
            "interval_minutes": body.interval_minutes,
            "updated_at": timestamp,
            "updated_by": user.get("sub"),
        }, "$setOnInsert": {"tenant_id": _tenant(user), "created_at": timestamp}},
        upsert=True,
    )
    return {
        "ok": True, "enabled": body.enabled,
        "interval_minutes": body.interval_minutes,
        "message": ("Continuous Windows monitoring enabled. The background agent must be running on the Windows host."
                    if body.enabled else "Continuous Windows monitoring disabled. The agent will stop scanning after its next control check."),
    }


@router.get("/scans/latest")
def latest_scan(user=Depends(current_user)):
    row = db.security_scans.find_one(
        {"tenant_id": _tenant(user)}, sort=[("created_at", -1)]
    )
    if not row:
        return {"latest": None}
    return {"latest": {
        "scanner": row.get("scanner"), "created_at": row["created_at"].isoformat(),
        "vulnerabilities": row.get("vulnerabilities", 0),
        "packages_checked_with_findings": row.get("packages_with_findings", 0),
    }}
