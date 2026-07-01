"""Conseils d'achat combinatoires : quel achat (slot × couleur) débloque le plus de tenues.

Une tenue = triplet (Haut, Pantalon, Chaussures) dont les couleurs sont 2-à-2
compatibles (`colors_compat`). On évalue chaque achat candidat par son gain
marginal de tenues.
"""
from __future__ import annotations

from typing import Any

from app.services.garderobe.constants import ACCENTS, NEUTRES, SECONDAIRES, SLOTS
from app.services.garderobe.style import colors_compat

_BASE_SLOTS = ["Haut", "Pantalon", "Chaussures"]
PALETTE: list[str] = list(NEUTRES) + list(SECONDAIRES) + list(ACCENTS)

# categorie -> slot de base (depuis les slots ALWAYS de SLOTS)
def _build_cat_to_slot() -> dict[str, str]:
    d: dict[str, str] = {}
    for s in SLOTS:
        if s["id"] in _BASE_SLOTS:
            for c in s["categories"]:
                d[c] = s["id"]
    return d


_CAT_TO_SLOT: dict[str, str] = _build_cat_to_slot()


def base_slot_of(item: dict[str, Any]) -> str | None:
    return _CAT_TO_SLOT.get(item.get("categorie"))


def count_outfits(wardrobe: list[dict[str, Any]]) -> int:
    by_slot: dict[str, list[dict[str, Any]]] = {sid: [] for sid in _BASE_SLOTS}
    for it in wardrobe:
        sid = base_slot_of(it)
        if sid:
            by_slot[sid].append(it)
    n = 0
    for h in by_slot["Haut"]:
        for p in by_slot["Pantalon"]:
            if not colors_compat(h.get("couleur"), p.get("couleur")):
                continue
            for c in by_slot["Chaussures"]:
                if colors_compat(h.get("couleur"), c.get("couleur")) and colors_compat(
                    p.get("couleur"), c.get("couleur")
                ):
                    n += 1
    return n


def purchase_advice(wardrobe: list[dict[str, Any]], top: int = 5) -> list[dict[str, Any]]:
    base = count_outfits(wardrobe)
    out: list[dict[str, Any]] = []
    for slot in _BASE_SLOTS:
        for couleur in PALETTE:
            gain = count_outfits(wardrobe + [{"categorie": slot, "couleur": couleur}]) - base
            if gain > 0:
                out.append(
                    {"slot": slot, "couleur": couleur, "debloque": gain, "total_apres": base + gain}
                )
    out.sort(key=lambda c: (-c["debloque"], _BASE_SLOTS.index(c["slot"]), PALETTE.index(c["couleur"])))
    return out[:top]
