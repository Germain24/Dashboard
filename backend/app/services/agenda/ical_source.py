"""Configuration locale et état de synchronisation du calendrier de travail.

L'URL iCal est un secret équivalent à un jeton : elle est gardée dans un
fichier runtime ignoré par Git et n'est jamais renvoyée à l'interface.
"""

from __future__ import annotations

import json
import os
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings


def _path() -> Path:
    return settings.data_dir / "ical_source.json"


def _empty() -> dict:
    return {
        "label": "7shifts",
        "url": "",
        "enabled": True,
        "last_sync_at": None,
        "last_error": None,
        "created_events": 0,
        "updated_events": 0,
        "deleted_events": 0,
        "skipped_duplicates": 0,
    }


def _read() -> dict:
    path = _path()
    if not path.exists():
        return _empty()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        state = _empty()
        if isinstance(value, dict):
            state.update({key: value[key] for key in state if key in value})
        return state
    except (OSError, json.JSONDecodeError):
        return _empty()


def _write(state: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def status() -> dict:
    """État non sensible destiné à l'interface (l'URL n'est jamais incluse)."""
    state = _read()
    return {
        "configured": bool(state["url"]),
        "enabled": bool(state["enabled"]),
        "label": state["label"],
        "last_sync_at": state["last_sync_at"],
        "last_error": state["last_error"],
        "created_events": state["created_events"],
        "updated_events": state["updated_events"],
        "deleted_events": state["deleted_events"],
        "skipped_duplicates": state["skipped_duplicates"],
    }


def configure(url: str, label: str = "7shifts") -> dict:
    parsed = urlparse(url.strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.hostname.lower() not in {"app.7shifts.com", "7shifts.com"}
    ):
        raise ValueError("Colle une adresse iCal HTTPS valide.")

    state = _read()
    normalized_url = url.strip()
    if normalized_url != state["url"]:
        state.update(
            last_sync_at=None,
            last_error=None,
            created_events=0,
            updated_events=0,
            deleted_events=0,
            skipped_duplicates=0,
        )
    state.update(url=normalized_url, label=label.strip()[:80] or "Calendrier de travail", enabled=True)
    _write(state)
    return status()


def remove() -> dict:
    _write(_empty())
    return status()


def source_for_sync() -> dict:
    return _read()


def sync(session) -> dict:
    """Synchronise la source de travail configurée et journalise son état."""
    from app.services.agenda.ical_import import import_ics_from_url

    state = _read()
    if not state["url"] or not state["enabled"]:
        raise ValueError("Aucun calendrier de travail n'est configuré.")
    try:
        counts = import_ics_from_url(
            session,
            state["url"],
            source_key="work",
            category="travail",
            prune_missing=True,
        )
    except Exception as exc:  # noqa: BLE001 - stored status must not leak the secret URL
        record_sync(error=f"Synchronisation impossible ({type(exc).__name__}).")
        raise RuntimeError("Synchronisation iCal impossible. Vérifie l'URL et réessaie.") from exc
    record_sync(
        created_events=counts["created_events"],
        updated_events=counts.get("updated_events", 0),
        deleted_events=counts.get("deleted_events", 0),
        skipped_duplicates=counts["skipped_duplicates"],
    )
    if counts["created_events"] or counts.get("updated_events", 0) or counts.get("deleted_events", 0):
        from app.services.agenda.weekly_revisions import (
            replan_current_weekly_revisions,
            run_weekly_revisions,
        )

        today = dt.date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        current_sunday = today - dt.timedelta(days=days_since_sunday)
        replan_current_weekly_revisions(session, today)
        run_weekly_revisions(session, current_sunday + dt.timedelta(days=7))
    return counts


def record_sync(
    *,
    created_events: int = 0,
    updated_events: int = 0,
    deleted_events: int = 0,
    skipped_duplicates: int = 0,
    error: str | None = None,
) -> dict:
    from app.core.timeutil import utcnow

    state = _read()
    state.update(
        last_sync_at=utcnow().isoformat(),
        last_error=error[:240] if error else None,
        created_events=created_events,
        updated_events=updated_events,
        deleted_events=deleted_events,
        skipped_duplicates=skipped_duplicates,
    )
    _write(state)
    return status()
