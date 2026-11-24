"""Read-only lab metadata derived from the real files in labs/ and the experiment registry."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from common import db
from dashboard import EXPERIMENTS, LAB_INTEGRATION, MANUAL, ROOT, RUN_NOTES, RUN_WARNINGS
from saas import current_user, require_lab_view

router = APIRouter(prefix="/api/labs", dependencies=[Depends(current_user)])
ALLOWED_SUFFIX = {".py", ".md", ".sh", ".yml", ".yaml"}


def _lab_dir(n: int) -> Path:
    return ROOT / "labs" / f"lab{n:02d}"


def _files(n: int) -> list[str]:
    d = _lab_dir(n)
    if not d.is_dir():
        return []
    return sorted(str(p.relative_to(d)).replace("\\", "/") for p in d.rglob("*")
                  if p.is_file() and p.suffix in ALLOWED_SUFFIX)


def _latest_by_lab() -> dict:
    out = {}
    for r in db.experiment_runs.aggregate([{"$sort": {"ts": -1}},
                                           {"$group": {"_id": "$exp", "lab": {"$first": "$lab"}, "ok": {"$first": "$ok"},
                                                       "ts": {"$first": "$ts"}, "seconds": {"$first": "$seconds"}}}]):
        out.setdefault(str(r["lab"]).split(".")[0], []).append(r)
    return out


def _describe(n: int, latest: dict) -> dict:
    key = str(n)
    meta = LAB_INTEGRATION.get(key, {})
    exps = [{"id": i, "lab": v[0], "title": v[1], "script": v[2], "args": v[3],
             "warning": RUN_WARNINGS.get(i), "note": RUN_NOTES.get(i)}
            for i, v in EXPERIMENTS.items() if v[0].split(".")[0] == key]
    manual = [m for m in MANUAL if str(m["lab"]).split(".")[0] == key]
    runs = latest.get(key, [])
    if runs:
        status = "failed" if any(not r["ok"] for r in runs) else "passed"
    else:
        status = "not_run" if exps else ("manual" if manual else "no_runner")
    return {"lab": n, "title": meta.get("title"), "uses": meta.get("uses", []), "feeds": meta.get("feeds", []),
            "files": _files(n), "experiments": exps, "manual_steps": manual, "status": status,
            "last_run": max((r["ts"] for r in runs), default=None)}


@router.get("")
def list_labs(user=Depends(current_user)):
    latest = _latest_by_lab()
    return {"labs": [_describe(n, latest) for n in [1, 2, 3, 4, 5, 6, *range(7, 19)] if user.get("role") in ("admin","professor") or n in user.get("permissions", {}).get("labs", [])]}


@router.get("/{n}")
def lab_detail(n: int, user=Depends(current_user)):
    if n not in (1, 2, 3, 4, 5, 6, *range(7, 19)):
        raise HTTPException(404, "Lab not found.")
    require_lab_view(user, n)
    return _describe(n, _latest_by_lab())


@router.get("/{n}/files/{name:path}")
def lab_file(n: int, name: str, user=Depends(current_user)):
    if not 1 <= n <= 18 or name not in _files(n):  # allow-list: only files that exist in that lab folder
        raise HTTPException(404, "File not found.")
    require_lab_view(user, n)
    path = (_lab_dir(n) / name).resolve()
    if _lab_dir(n).resolve() not in path.parents:
        raise HTTPException(404, "File not found.")
    if path.stat().st_size > 80_000:
        raise HTTPException(413, "File too large to display.")
    return {"name": name, "content": path.read_text(encoding="utf-8", errors="replace")}
