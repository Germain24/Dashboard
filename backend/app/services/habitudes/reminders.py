"""Rappels d'habitudes non cochées (#136).

Un job quotidien (20h) vérifie les habitudes non complétées et crée une
Notification consolidée. Un store JSON évite les doublons le même jour.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings


def reminded_file() -> Path:
    return settings.data_dir / "habitudes_reminded.json"


def _read_reminded(*, path: Optional[Path] = None) -> set[str]:
    p = path or reminded_file()
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data) if isinstance(data, list) else set()


def _write_reminded(keys: set[str], *, path: Optional[Path] = None) -> None:
    p = path or reminded_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(keys)[-100:], ensure_ascii=False), encoding="utf-8")


def reminder_key(date: dt.date) -> str:
    return date.isoformat()


def unchecked_habits(checklist: list[dict]) -> list[str]:
    """Pur : noms des habitudes non cochées depuis un résultat de get_today_checklist."""
    return [row["habit"].nom for row in checklist if not row.get("entry")]


def should_remind(date: dt.date, *, path: Optional[Path] = None) -> bool:
    """Pur : retourne True si aucun rappel n'a encore été envoyé pour cette date."""
    return reminder_key(date) not in _read_reminded(path=path)


def mark_reminded(date: dt.date, *, path: Optional[Path] = None) -> None:
    reminded = _read_reminded(path=path)
    reminded.add(reminder_key(date))
    _write_reminded(reminded, path=path)
