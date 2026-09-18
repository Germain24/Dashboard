"""Fonctions pures de l'onglet « Objectif » de la garde-robe.

L'échelle d'un type va de Qualité/Prix (index 0 → position 0) à Qualité Max
(dernier index → position 100). La position d'une marque possédée sur cette
échelle pilote la barre 0→100 de l'onglet.
"""
from __future__ import annotations

import re
import unicodedata


def _fold(s: str) -> str:
    """Clé de comparaison robuste : minuscule, sans accents ni ponctuation/espaces.

    Deux variantes d'écriture d'une même marque (« R.M. Williams » saisie sur
    une pièce vs « RM Williams » dans l'échelle Excel, ou l'inverse) doivent
    matcher — sinon la pièce tombe « hors échelle » et la barre reste au
    minimum malgré une marque placée en position max dans le classeur.
    """
    ascii_s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_s.lower())


def build_echelle(brands: list) -> list[str]:
    """Liste de marques ordonnée, dédupliquée (insensible à la casse), sans vides."""
    out: list[str] = []
    seen: set[str] = set()
    for b in brands:
        if not b:
            continue
        name = str(b).strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def brand_position(echelle: list[str], marque: str | None) -> float | None:
    """Position 0..100 de `marque` dans `echelle`, ou None si absente/None."""
    if not marque:
        return None
    key = _fold(str(marque))
    idx = next((i for i, b in enumerate(echelle) if _fold(b) == key), None)
    if idx is None:
        return None
    n = len(echelle)
    if n <= 1:
        return 0.0
    return round(idx / (n - 1) * 100.0, 1)


def _empty_slot() -> dict:
    return {
        "statut": "vide",
        "vetement_id": None,
        "vetement_nom": None,
        "marque": None,
        "position": None,
        "hors_echelle": False,
        "image": None,
    }


def fill_slots(echelle: list[str], quantite: int, owned: list[dict]) -> dict:
    """Répartit les pièces possédées sur `quantite` emplacements.

    Tri par qualité décroissante (meilleure marque d'abord) ; les pièces dont la
    marque n'est pas dans l'échelle (position None) passent en dernier. Les
    `quantite` premières remplissent les emplacements ; le reste = excédent.
    """
    enriched: list[dict] = []
    for o in owned:
        pos = brand_position(echelle, o.get("marque"))
        enriched.append(
            {
                "statut": "rempli",
                "vetement_id": o.get("id"),
                "vetement_nom": o.get("nom"),
                "marque": o.get("marque"),
                "position": pos,
                "hors_echelle": pos is None,
                "image": o.get("image"),
            }
        )
    enriched.sort(
        key=lambda e: (e["position"] is not None, e["position"] or 0.0),
        reverse=True,
    )
    filled = enriched[:quantite]
    excedent = enriched[quantite:]
    emplacements = list(filled) + [_empty_slot() for _ in range(quantite - len(filled))]
    return {"emplacements": emplacements, "excedent": excedent, "rempli": len(filled)}
