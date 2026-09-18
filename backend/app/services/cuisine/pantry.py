"""Garde-manger : stock d'ingrédients avec suivi de péremption (#127).

Persisté dans `data/cuisine_pantry.json` (liste de dicts).
Pas de migration SQL — JSON local suffisant.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
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


def _write(path: Path, items: list[dict], *, backup_existing: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup_existing and path.is_file():
        from app.services.backup_storage import backup_file

        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_file(
            path,
            category="cuisine/pantry",
            filename=f"{path.stem}-{stamp}-{digest}{path.suffix}",
        )
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_id(items: list[dict]) -> int:
    return max((i.get("id", 0) for i in items), default=0) + 1


def _shelf_stable_rayon(rayon: str | None) -> bool:
    normalized = (rayon or "").casefold()
    return any(marker in normalized for marker in ("épicerie sèche", "epicerie seche", "conserves", "surgelés", "surgeles"))


def classify_expiry(
    date_peremption: Optional[str], today: str, rayon: str | None = None
) -> str:
    """Classify hard dates separately from best-before dates on shelf-stable food."""
    if not date_peremption:
        return "no_date"
    exp = date.fromisoformat(date_peremption)
    ref = date.fromisoformat(today)
    delta = (exp - ref).days
    if _shelf_stable_rayon(rayon):
        if delta < 0:
            return "best_before_passed"
        if delta <= 3:
            return "best_before_soon"
        return "ok"
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
    _write(p, items, backup_existing=path is None)
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
            _write(p, items, backup_existing=path is None)
            return items[i]
    return None


def remove_item(item_id: int, *, path: Optional[Path] = None) -> bool:
    p = path or _pantry_path()
    items = _read(p)
    new = [i for i in items if i.get("id") != item_id]
    if len(new) == len(items):
        return False
    _write(p, new, backup_existing=path is None)
    return True
