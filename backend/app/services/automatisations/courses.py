"""Courses auto (#208) — vérifie le garde-manger et notifie quand un ingrédient
est sous son seuil minimal."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlmodel import Session

from app.models.scheduler import Notification
from app.services.cuisine.pantry import _read


def items_below_threshold(items: list[dict]) -> list[dict]:
    """Pur : retourne les items dont quantite < seuil_min (si seuil_min défini)."""
    out = []
    for item in items:
        seuil = item.get("seuil_min")
        if seuil is None:
            continue
        if item.get("quantite", 0) < seuil:
            out.append(item)
    return out


def check_pantry_low_stock(*, path: Optional[Path] = None) -> list[dict]:
    """Lit le garde-manger et retourne les ingrédients sous seuil."""
    from app.services.cuisine.pantry import _pantry_path
    p = path or _pantry_path()
    return items_below_threshold(_read(p))


def run_courses_check(session: Session, *, path: Optional[Path] = None) -> int:
    """Vérifie le stock du garde-manger et crée une Notification consolidée
    si des ingrédients sont sous seuil. Retourne le nombre d'ingrédients concernés."""
    low = check_pantry_low_stock(path=path)
    if not low:
        return 0
    noms = ", ".join(item["ingredient"] for item in low)
    session.add(Notification(
        source="courses_auto",
        level="warning",
        titre="Courses à prévoir",
        message=f"{len(low)} ingrédient(s) sous le seuil : {noms}",
    ))
    session.commit()
    return len(low)
