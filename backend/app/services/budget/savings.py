"""Objectif d'épargne mensuel + progression (#121).

Store JSON local (`data/budget_savings_goal.json`), sans migration. La progression
se calcule à la volée contre le solde du mois (revenus − dépenses).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def savings_goal_file() -> Path:
    from app.core.config import settings
    return settings.data_dir / "budget_savings_goal.json"


def get_savings_goal(*, path: Optional[Path] = None) -> float:
    p = path or savings_goal_file()
    if not p.exists():
        return 0.0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return float(data.get("montant", 0.0))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return 0.0


def set_savings_goal(montant: float, *, path: Optional[Path] = None) -> float:
    montant = max(0.0, float(montant))
    p = path or savings_goal_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"montant": montant}, ensure_ascii=False), encoding="utf-8")
    return montant


def savings_progress(goal: float, solde: float) -> dict:
    """Épargne réalisée (solde positif) vs objectif → montant + % (pur)."""
    epargne = max(0.0, solde)
    pct = round(epargne / goal * 100, 1) if goal > 0 else 0.0
    return {"objectif": round(goal, 2), "epargne": round(epargne, 2), "progress_pct": pct}
