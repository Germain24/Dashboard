"""Suivi manuel des abonnements/contrats (#362).

Distinct de la détection automatique des récurrences (`analytics.detect_recurring`,
#116/#266) qui infère des abonnements à partir des transactions importées : ici
l'utilisateur saisit lui-même ses contrats (assurances, box internet, salle de
sport…), y compris ceux qui n'apparaissent pas tels quels dans les relevés ou
dont l'échéance d'engagement doit être surveillée.

Persisté dans `data/budget_contracts.json` (liste de dicts). Pas de migration
SQL — JSON local suffisant, même pattern que `cuisine/pantry.py`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from app.core.config import settings


def _contracts_path() -> Path:
    return settings.data_dir / "budget_contracts.json"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(items: list[dict]) -> int:
    return max((i.get("id", 0) for i in items), default=0) + 1


def classify_echeance(date_echeance: Optional[str], today: str) -> str:
    """Pur : 'no_date' | 'depassee' | 'proche' (≤ 30 jours) | 'ok'."""
    if not date_echeance:
        return "no_date"
    ech = date.fromisoformat(date_echeance)
    ref = date.fromisoformat(today)
    delta = (ech - ref).days
    if delta < 0:
        return "depassee"
    if delta <= 30:
        return "proche"
    return "ok"


def monthly_cost(contracts: list[dict]) -> float:
    """Pur : coût mensuel total des contrats actifs (annuel converti / 12)."""
    total = 0.0
    for c in contracts:
        if c.get("statut") != "actif":
            continue
        montant = c.get("montant") or 0
        if c.get("periodicite") == "annuel":
            total += montant / 12
        else:
            total += montant
    return round(total, 2)


def upcoming_renewals(contracts: list[dict], today: str, *, days: int = 30) -> list[dict]:
    """Pur : contrats actifs en échéance proche ou dépassée, triés par date croissante."""
    result = []
    for c in contracts:
        if c.get("statut") != "actif":
            continue
        statut_echeance = classify_echeance(c.get("date_echeance"), today)
        if statut_echeance in ("proche", "depassee"):
            result.append(c)

    def sort_key(c: dict):
        d = c.get("date_echeance")
        return (d is None, d or "")

    return sorted(result, key=sort_key)


def list_contracts(*, path: Optional[Path] = None) -> list[dict]:
    return _read(path or _contracts_path())


def add_contract(
    nom: str,
    categorie: str,
    montant: float,
    periodicite: str,
    *,
    date_echeance: Optional[str] = None,
    notes: str = "",
    path: Optional[Path] = None,
) -> dict:
    p = path or _contracts_path()
    items = _read(p)
    item: dict = {
        "id": _next_id(items),
        "nom": nom.strip(),
        "categorie": categorie.strip(),
        "montant": montant,
        "periodicite": periodicite,
        "date_echeance": date_echeance or None,
        "statut": "actif",
        "date_resiliation": None,
        "notes": notes or "",
    }
    items.append(item)
    _write(p, items)
    return item


def update_contract(
    contract_id: int,
    patch: dict,
    *,
    path: Optional[Path] = None,
) -> Optional[dict]:
    p = path or _contracts_path()
    items = _read(p)
    for i, item in enumerate(items):
        if item.get("id") == contract_id:
            items[i] = {**item, **{k: v for k, v in patch.items() if k != "id"}}
            _write(p, items)
            return items[i]
    return None


def remove_contract(contract_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or _contracts_path()
    items = _read(p)
    new = [i for i in items if i.get("id") != contract_id]
    if len(new) == len(items):
        return False
    _write(p, new)
    return True
