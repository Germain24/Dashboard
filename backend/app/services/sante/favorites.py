"""Favoris d'aliments pour saisie rapide (#64).

Le catalogue d'aliments est en lecture seule (CSV, cf. aliments.py). Les favoris
sont une simple liste de noms, curée par l'utilisateur, persistée dans un JSON
local (`data/sante_favorites.json`) — pas de migration SQL.

On ne référence que des aliments présents dans le catalogue : un favori dont
l'aliment a disparu du CSV est silencieusement filtré à la lecture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services.sante.aliments import aliment_names


def favorites_file() -> Path:
    return settings.data_dir / "sante_favorites.json"


def _read(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [str(x) for x in data] if isinstance(data, list) else []


def _write(path: Path, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")


def list_favorites(*, path: Optional[Path] = None, valid_names: Optional[list[str]] = None) -> list[str]:
    """Favoris existant encore dans le catalogue, triés."""
    p = path or favorites_file()
    catalog = set(valid_names if valid_names is not None else aliment_names())
    return sorted(n for n in _read(p) if not catalog or n in catalog)


def add_favorite(nom: str, *, path: Optional[Path] = None, valid_names: Optional[list[str]] = None) -> list[str]:
    """Ajoute un aliment aux favoris (no-op si déjà présent ou hors catalogue)."""
    nom = (nom or "").strip()
    if not nom:
        raise ValueError("Nom d'aliment vide")
    catalog = valid_names if valid_names is not None else aliment_names()
    if catalog and nom not in catalog:
        raise ValueError(f"Aliment inconnu : {nom}")
    p = path or favorites_file()
    current = _read(p)
    if nom not in current:
        current.append(nom)
        _write(p, current)
    return list_favorites(path=p, valid_names=valid_names)


def remove_favorite(nom: str, *, path: Optional[Path] = None, valid_names: Optional[list[str]] = None) -> list[str]:
    """Retire un aliment des favoris."""
    p = path or favorites_file()
    current = [n for n in _read(p) if n != nom]
    _write(p, current)
    return list_favorites(path=p, valid_names=valid_names)
