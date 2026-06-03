"""Filtres garde-robe : saison, couleur, occasion (#78).

- saison : dérivée de la plage de confort [temp_min, temp_max] de la pièce.
  Climat type Montréal — bandes : hiver < 8 °C, été > 18 °C, mi-saison entre.
- couleur : correspondance insensible à la casse.
- occasion : présence dans la liste `style` (le style fait office d'occasion :
  Casual, Sport, Formel…) ou dans `extra.occasion`.
"""

from __future__ import annotations

from typing import Any, Optional

SAISONS = ("hiver", "mi-saison", "été")


def season_of(temp_min: Optional[float], temp_max: Optional[float]) -> str:
    """Saison principale d'une pièce selon le milieu de sa plage de confort.

    Retourne "hiver" | "mi-saison" | "été" | "toutes" (si plage inconnue).
    """
    if temp_min is None and temp_max is None:
        return "toutes"
    lo = temp_min if temp_min is not None else temp_max
    hi = temp_max if temp_max is not None else temp_min
    mid = (float(lo) + float(hi)) / 2.0
    if mid <= 8:
        return "hiver"
    if mid >= 18:
        return "été"
    return "mi-saison"


def _occasions_of(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    style = item.get("style")
    if isinstance(style, list):
        out.extend(str(s) for s in style if s)
    elif style:
        out.append(str(style))
    extra = item.get("extra") or {}
    occ = extra.get("occasion")
    if occ:
        out.append(str(occ))
    return out


def matches_filters(
    item: dict[str, Any],
    *,
    couleur: Optional[str] = None,
    saison: Optional[str] = None,
    occasion: Optional[str] = None,
) -> bool:
    """Vrai si la pièce satisfait tous les filtres fournis (None = ignoré)."""
    if couleur:
        c = (item.get("couleur") or "").strip().lower()
        if c != couleur.strip().lower():
            return False
    if saison:
        s = season_of(item.get("temp_min"), item.get("temp_max"))
        # une pièce "toutes saisons" passe tous les filtres de saison
        if s != "toutes" and s != saison.strip().lower():
            return False
    if occasion:
        occs = [o.lower() for o in _occasions_of(item)]
        if occasion.strip().lower() not in occs:
            return False
    return True
