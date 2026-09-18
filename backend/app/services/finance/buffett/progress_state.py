"""Progression unifiée et peu coûteuse du pipeline Buffett."""

from __future__ import annotations

import threading
import time
from collections import Counter

_lock = threading.Lock()
_state: dict = {}


def start(
    *,
    run_id: int,
    total: int,
    catalog_version=None,
    already_completed: int = 0,
    unique_instruments: int | None = None,
    secondary_quotes_skipped: int = 0,
) -> None:
    with _lock:
        _state.clear()
        _state.update({
            "run_id": run_id,
            "phase": "scoring",
            "started_monotonic": time.monotonic(),
            "last_monotonic": time.monotonic(),
            "done": already_completed,
            "already_completed": already_completed,
            "total": total,
            "cache_hits": 0,
            "errors": Counter(),
            "catalog_version": catalog_version,
            "unique_instruments": unique_instruments if unique_instruments is not None else total,
            "secondary_quotes_skipped": secondary_quotes_skipped,
            "propagated_quotes": 0,
            "stop_requested": False,
        })


def update(*, done: int | None = None, total: int | None = None, phase: str | None = None,
           cache_hit: bool = False, error_kind: str | None = None,
           propagated_quotes: int | None = None) -> None:
    with _lock:
        if not _state:
            return
        now = time.monotonic()
        gap = now - _state["last_monotonic"]
        if gap > 120:
            # Une suspension de la machine n'est pas du temps d'exécution actif.
            _state["started_monotonic"] += gap
            try:
                from app.services.finance.yf_session import rotate_session
                rotate_session()
            except Exception:
                pass
        if done is not None:
            _state["done"] = done
        if total is not None:
            _state["total"] = total
        if phase is not None:
            _state["phase"] = phase
        if cache_hit:
            _state["cache_hits"] += 1
        if error_kind:
            _state["errors"][error_kind] += 1
        if propagated_quotes is not None:
            _state["propagated_quotes"] = propagated_quotes
        _state["last_monotonic"] = now
    from app.core.realtime import publish

    publish(
        "finance.buffett.progress",
        data=snapshot(),
        invalidate=[["finance", "buffett"]],
    )


def snapshot() -> dict:
    with _lock:
        if not _state:
            return {
                "phase": "idle", "throughput_per_min": 0.0, "eta_seconds": None,
                "cache_hits": 0, "error_counts": {}, "catalog_version": None,
                "already_completed": 0, "session_processed": 0,
                "unique_instruments": 0, "secondary_quotes_skipped": 0,
                "propagated_quotes": 0, "http_requests": 0,
                "http_requests_per_hour": 0, "deferred_rate_limits": 0,
                "stop_requested": False,
            }
        elapsed = max(0.001, time.monotonic() - _state["started_monotonic"])
        done, total = _state["done"], _state["total"]
        already_completed = min(_state["already_completed"], done)
        session_processed = max(0, done - already_completed)
        throughput = session_processed / elapsed * 60
        eta = (total - done) / (throughput / 60) if throughput > 0 and total > done else 0
        http_requests = 0
        deferred_rate_limits = 0
        requests_per_hour = 0
        try:
            from app.services.finance.yf_session import http_rate_limiter

            limiter = http_rate_limiter()
            http_requests = limiter.http_requests
            deferred_rate_limits = limiter.deferred_rate_limits
            requests_per_hour = limiter.requests_per_hour
        except Exception:
            pass
        return {
            "run_id": _state.get("run_id"),
            "n_done": done,
            "n_total": total,
            "progress_pct": round(done / total * 100, 1) if total else 0.0,
            "active": _state["phase"] not in {"complete", "idle"},
            "phase": _state["phase"],
            "throughput_per_min": round(throughput, 2),
            "eta_seconds": round(eta) if eta else 0,
            "cache_hits": _state["cache_hits"],
            "error_counts": dict(_state["errors"]),
            "catalog_version": _state["catalog_version"],
            "already_completed": already_completed,
            "session_processed": session_processed,
            "unique_instruments": _state["unique_instruments"],
            "secondary_quotes_skipped": _state["secondary_quotes_skipped"],
            "propagated_quotes": _state["propagated_quotes"],
            "http_requests": http_requests,
            "http_requests_per_hour": requests_per_hour,
            "deferred_rate_limits": deferred_rate_limits,
            "stop_requested": bool(_state.get("stop_requested")),
        }


def request_stop() -> bool:
    """Demande l'arrêt coopératif du scoring ou de ses reprises Yahoo."""
    with _lock:
        if not _state or _state.get("phase") in {"complete", "idle"}:
            return False
        _state["stop_requested"] = True
        _state["last_monotonic"] = time.monotonic()
    return True


def finish() -> None:
    update(phase="complete")
