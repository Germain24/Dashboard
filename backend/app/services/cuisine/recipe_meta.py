"""Favoris et notes personnelles par recette (#128).

Persisté dans `data/cuisine_recipe_meta.json` :
  { "favorites": [1, 5], "notes": {"1": "...", "5": "..."} }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings


def _meta_path() -> Path:
    return settings.data_dir / "cuisine_recipe_meta.json"


def _read(path: Path) -> dict:
    if not path.exists():
        return {"favorites": [], "notes": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"favorites": [], "notes": {}}
    if not isinstance(data, dict):
        return {"favorites": [], "notes": {}}
    data.setdefault("favorites", [])
    data.setdefault("notes", {})
    return data


def _write(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def get_favorites(*, path: Optional[Path] = None) -> dict:
    meta = _read(path or _meta_path())
    return {"favorites": meta["favorites"]}


def toggle_favorite(recipe_id: int, *, path: Optional[Path] = None) -> dict:
    p = path or _meta_path()
    meta = _read(p)
    favs: list = meta["favorites"]
    if recipe_id in favs:
        favs.remove(recipe_id)
        is_fav = False
    else:
        favs.append(recipe_id)
        is_fav = True
    meta["favorites"] = favs
    _write(p, meta)
    return {"is_favorite": is_fav, "favorites": favs}


def get_note(recipe_id: int, *, path: Optional[Path] = None) -> str:
    meta = _read(path or _meta_path())
    return meta["notes"].get(str(recipe_id), "")


def set_note(recipe_id: int, note: str, *, path: Optional[Path] = None) -> str:
    p = path or _meta_path()
    meta = _read(p)
    meta["notes"][str(recipe_id)] = note
    _write(p, meta)
    return note
