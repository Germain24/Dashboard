"""Taux horaire par défaut du module Travail.

Persisté dans un JSON local (`data/travail_settings.json`), sans migration —
même approche que l'objectif d'heures d'étude (etudes/goals.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings

DEFAULT_TAUX_HORAIRE = 12.0


def settings_file() -> Path:
    return settings.data_dir / "travail_settings.json"


def get_taux_horaire(*, path: Optional[Path] = None) -> float:
    p = path or settings_file()
    if not p.exists():
        return DEFAULT_TAUX_HORAIRE
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return float(data.get("taux_horaire", DEFAULT_TAUX_HORAIRE))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return DEFAULT_TAUX_HORAIRE


def set_taux_horaire(taux: float, *, path: Optional[Path] = None) -> float:
    if taux < 0:
        raise ValueError("Taux horaire négatif invalide")
    p = path or settings_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"taux_horaire": round(float(taux), 2)}), encoding="utf-8")
    return round(float(taux), 2)
