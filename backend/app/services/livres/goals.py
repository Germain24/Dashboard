"""Objectif annuel de lecture (#151).

Persisté dans un JSON local (`data/livres_goal.json`), sans migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings

DEFAULT_ANNUAL_GOAL = 12


def goal_file() -> Path:
    return settings.data_dir / "livres_goal.json"


def get_annual_goal(*, path: Optional[Path] = None) -> int:
    p = path or goal_file()
    if not p.exists():
        return DEFAULT_ANNUAL_GOAL
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return int(data.get("annual_goal", DEFAULT_ANNUAL_GOAL))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return DEFAULT_ANNUAL_GOAL


def set_annual_goal(goal: int, *, path: Optional[Path] = None) -> int:
    if goal < 0:
        raise ValueError("Objectif négatif invalide")
    p = path or goal_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"annual_goal": int(goal)}), encoding="utf-8")
    return int(goal)


def goal_progress(livres_lus: int, goal: int) -> dict:
    """Pur : progression vers l'objectif annuel."""
    pct = round(livres_lus / goal * 100, 1) if goal > 0 else 0.0
    return {
        "goal": goal,
        "livres_lus": livres_lus,
        "pct": min(pct, 100.0),
        "atteint": goal > 0 and livres_lus >= goal,
        "restant": max(0, goal - livres_lus),
    }
