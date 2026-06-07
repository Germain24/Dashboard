"""Garde-manger : stock d'ingrédients avec suivi de péremption (#127).

Persisté dans `data/cuisine_pantry.json` (liste de dicts).
Pas de migration SQL — JSON local suffisant.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from app.core.config import settings


def _pantry_path() -> Path:
    return settings.data_dir / "cuisine_pantry.json"


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


def classify_expiry(date_peremption: Optional[str], today: str) -> str:
    """Pur : 'expired' | 'warning' (≤ 3 jours) | 'ok' | 'no_date'."""
    if not date_peremption:
        return "no_date"
    exp = date.fromisoformat(date_peremption)
    ref = date.fromisoformat(today)
    delta = (exp - ref).days
    if delta < 0:
        return "expired"
    if delta <= 3:
        return "warning"
    return "ok"


def list_items(*, path: Optional[Path] = None) -> list[dict]:
    return _read(path or _pantry_path())


def add_item(
    ingredient: str,
    quantite: float,
    unite: str,
    *,
    date_peremption: Optional[str] = None,
    rayon: str = "Autre",
    path: Optional[Path] = None,
) -> dict:
    p = path or _pantry_path()
    items = _read(p)
    item: dict = {
        "id": _next_id(items),
        "ingredient": ingredient.strip(),
        "quantite": quantite,
        "unite": unite.strip(),
        "date_peremption": date_peremption or None,
        "rayon": rayon or "Autre",
    }
    items.append(item)
    _write(p, items)
    return item


def update_item(
    item_id: int,
    patch: dict,
    *,
    path: Optional[Path] = None,
) -> Optional[dict]:
    p = path or _pantry_path()
    items = _read(p)
    for i, item in enumerate(items):
        if item.get("id") == item_id:
            items[i] = {**item, **{k: v for k, v in patch.items() if k != "id"}}
            _write(p, items)
            return items[i]
    return None


def remove_item(item_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or _pantry_path()
    items = _read(p)
    new = [i for i in items if i.get("id") != item_id]
    if len(new) == len(items):
        return False
    _write(p, new)
    return True
