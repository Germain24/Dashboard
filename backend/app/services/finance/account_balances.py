"""Soldes de comptes connus (auto-remplissage du patrimoine).

Persiste, par compte, le dernier solde lu lors d'un import (relevé Desjardins…).
L'onglet Patrimoine s'en sert pour afficher la valeur d'un compte sans saisie
manuelle. Stocké en JSON (data/account_balances.json) — pas de migration.

Format : { "<compte>": {"solde": float, "devise": str, "date": "YYYY-MM-DD"} }
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from app.core.config import settings


def _default_path() -> Path:
    return settings.data_dir / "account_balances.json"


def get_balances(*, path: Path | None = None) -> dict:
    """Tous les soldes connus (dict vide si le fichier n'existe pas/illisible)."""
    p = path or _default_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def set_balance(
    compte: str,
    solde: float,
    *,
    devise: str = "CAD",
    date: str | None = None,
    path: Path | None = None,
) -> dict:
    """Enregistre (upsert) le solde courant d'un compte. Renvoie l'entrée écrite."""
    p = path or _default_path()
    data = get_balances(path=p)
    entry = {
        "solde": round(float(solde), 2),
        "devise": devise,
        "date": date or dt.date.today().isoformat(),
    }
    data[compte] = entry
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry
