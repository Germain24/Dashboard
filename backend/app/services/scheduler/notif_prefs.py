"""Préférences de notification par source (#171).

Persistées dans un JSON local (data/notif_prefs.json) : {source: bool}.
Source absente = activée par défaut. Une source désactivée n'est plus affichée
dans le centre de notifications (filtrage à la lecture, non invasif).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings


def prefs_file() -> Path:
    return settings.data_dir / "notif_prefs.json"


def get_prefs(*, path: Path | None = None) -> dict[str, bool]:
    p = path or prefs_file()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {str(k): bool(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def is_enabled(source: str, *, path: Path | None = None) -> bool:
    """Une source est activée sauf si explicitement désactivée."""
    return get_prefs(path=path).get(source, True)


def set_source(source: str, enabled: bool, *, path: Path | None = None) -> dict[str, bool]:
    prefs = get_prefs(path=path)
    prefs[source] = bool(enabled)
    p = path or prefs_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    return prefs


def filter_enabled(notifications: list, *, path: Path | None = None) -> list:
    """Retire les notifications dont la source est désactivée."""
    prefs = get_prefs(path=path)
    return [n for n in notifications if prefs.get(getattr(n, "source", "system"), True)]
