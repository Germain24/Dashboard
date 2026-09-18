"""Planificateur de tenues sur la semaine (#79).

Associe une tenue (slot -> id de vêtement) à une date. Persisté dans un JSON
local (`data/garderobe_plan.json`), sans migration. La route enrichit chaque
jour avec les événements d'agenda (lien #79) pour aider au choix.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings


def planner_file() -> Path:
    return settings.data_dir / "garderobe_plan.json"


def monday_of(date: dt.date) -> dt.date:
    return date - dt.timedelta(days=date.weekday())


def week_dates(start: dt.date) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(7)]


def _read(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_day(date: dt.date, *, path: Optional[Path] = None) -> dict[str, str]:
    """Tenue planifiée pour une date : {slot_id: vetement_id}."""
    return _read(path or planner_file()).get(str(date), {})


def set_day(date: dt.date, tenue: dict[str, Optional[str]], *, path: Optional[Path] = None) -> dict[str, str]:
    """Enregistre la tenue d'un jour. Les slots à None sont retirés.

    Si la tenue résultante est vide, la date est supprimée du plan.
    """
    p = path or planner_file()
    data = _read(p)
    cleaned = {slot: vid for slot, vid in tenue.items() if vid}
    if cleaned:
        data[str(date)] = cleaned
    else:
        data.pop(str(date), None)
    _write(p, data)
    return cleaned
