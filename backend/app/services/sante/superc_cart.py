"""Remplissage asynchrone du panier Super C dans une fenêtre Google Chrome."""

from __future__ import annotations

import copy
import json
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_active_job_id: str | None = None
_ACTIVE = {"queued", "running", "awaiting_user"}


def _script_path() -> Path:
    return settings.data_dir.parent / "frontend" / ".superc_cart.mjs"


def _profile_path() -> Path:
    return settings.data_dir / "browser_profiles" / "superc_chrome"


def _update(job_id: str, **patch: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(patch)


def _consume_event(job_id: str, event: dict[str, Any]) -> None:
    typ = event.get("type")
    if typ == "status":
        _update(
            job_id,
            status=event.get("status", "running"),
            message=event.get("message", ""),
            current=int(event.get("current", 0)),
            total=int(event.get("total", 0)),
        )
    elif typ == "item" and isinstance(event.get("result"), dict):
        with _lock:
            job = _jobs.get(job_id)
            if job is not None:
                job["results"].append(dict(event["result"]))
                job["current"] = len(job["results"])
    elif typ == "done":
        _update(job_id, status="completed", message=event.get("message", "Panier prêt."))


def _run(job_id: str, items: list[dict[str, Any]]) -> None:
    global _active_job_id
    script = _script_path()
    try:
        if not script.exists():
            raise FileNotFoundError(f"Script Chrome introuvable: {script}")
        profile = _profile_path()
        profile.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"items": items}, ensure_ascii=False)
        proc = subprocess.Popen(
            ["node", str(script), str(profile)],
            cwd=str(script.parent),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdin is not None
        proc.stdin.write(payload)
        proc.stdin.close()
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                _consume_event(job_id, event)
        return_code = proc.wait(timeout=10)
        with _lock:
            status = _jobs[job_id]["status"]
        if return_code != 0 and status != "completed":
            raise RuntimeError(f"Chrome a terminé avec le code {return_code}")
        if status in _ACTIVE:
            _update(job_id, status="completed", message="Panier prêt dans Chrome.")
    except Exception as exc:
        _update(job_id, status="failed", message="Échec du remplissage.", error=str(exc))
    finally:
        with _lock:
            if _active_job_id == job_id:
                _active_job_id = None


def start_cart_fill(
    items: list[dict[str, Any]], anchor_date: str
) -> tuple[dict[str, Any], bool]:
    """Lance un job ou retourne le job actif afin d'éviter les doubles ajouts."""
    global _active_job_id
    safe_items = [
        {
            "aliment": str(item.get("aliment") or ""),
            "product_id": item.get("product_id"),
            "product_name": item.get("product_name"),
            "href": item.get("href") if str(item.get("href") or "").startswith("/") else None,
            "qty": max(1, int(item.get("qty") or 1)),
            "a_verifier": bool(item.get("a_verifier")),
        }
        for item in items
    ]
    with _lock:
        if _active_job_id and _jobs.get(_active_job_id, {}).get("status") in _ACTIVE:
            return copy.deepcopy(_jobs[_active_job_id]), False
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "anchor_date": anchor_date,
            "status": "queued",
            "message": "Ouverture de Google Chrome…",
            "current": 0,
            "total": len(safe_items),
            "results": [],
            "error": None,
        }
        _jobs[job_id] = job
        _active_job_id = job_id
        for old_id in list(_jobs)[:-10]:
            if old_id != job_id:
                _jobs.pop(old_id, None)
    threading.Thread(
        target=_run,
        args=(job_id, safe_items),
        daemon=True,
        name=f"superc-cart-{job_id[:8]}",
    ).start()
    return copy.deepcopy(job), True


def get_cart_fill(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return copy.deepcopy(job) if job is not None else None


def _reset_for_tests() -> None:
    global _active_job_id
    with _lock:
        _jobs.clear()
        _active_job_id = None
