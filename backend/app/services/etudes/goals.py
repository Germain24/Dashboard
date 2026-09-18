"""Objectif d'heures d'étude par semaine (#95).

Persisté dans un JSON local (`data/etudes_goal.json`), sans migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings

DEFAULT_WEEKLY_HOURS = 10.0


def goal_file() -> Path:
    return settings.data_dir / "etudes_goal.json"


def get_weekly_hours(*, path: Optional[Path] = None) -> float:
    p = path or goal_file()
    if not p.exists():
        return DEFAULT_WEEKLY_HOURS
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return float(data.get("weekly_hours", DEFAULT_WEEKLY_HOURS))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return DEFAULT_WEEKLY_HOURS


def set_weekly_hours(hours: float, *, path: Optional[Path] = None) -> float:
    if hours < 0:
        raise ValueError("Objectif négatif invalide")
    p = path or goal_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"weekly_hours": round(float(hours), 1)}), encoding="utf-8")
    return round(float(hours), 1)
