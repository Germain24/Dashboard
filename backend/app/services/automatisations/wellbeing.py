"""Score de bien-être quotidien (#222) — agrégat cross-modules, pur et déterministe.

Score 0-100 : habitudes (30 pts) + humeur/énergie (25 pts) +
nutrition (25 pts) + entraînement (20 pts).
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def compute_wellbeing_score(snapshot_data: dict[str, Any]) -> dict[str, Any]:
    """Calcule le score à partir d'un snapshot déjà construit.

    Fonction pure : ne lit pas la base.
    """
    components: dict[str, int] = {}

    # ── Habitudes (max 30 pts) ─────────────────────────────────────────────
    habits = snapshot_data.get("habitudes", {})
    pct_habits = habits.get("pct", 0)
    components["habitudes"] = int(pct_habits * 0.30)

    # ── Humeur/énergie (max 25 pts) ────────────────────────────────────────
    humeur = snapshot_data.get("humeur", {})
    if humeur:
        valeur = humeur.get("valeur", 5)
        energie = humeur.get("energie", 5)
        mood_score = ((valeur + energie) / 20) * 25
        components["humeur"] = int(mood_score)
    else:
        components["humeur"] = 12  # score neutre si pas de données

    # ── Nutrition (max 25 pts) ─────────────────────────────────────────────
    sante = snapshot_data.get("sante", {})
    calories_consommees = sante.get("calories")
    calories_cible = sante.get("calories_cible")
    if calories_consommees and calories_cible and calories_cible > 0:
        ratio = calories_consommees / calories_cible
        if 0.90 <= ratio <= 1.10:
            components["nutrition"] = 25  # dans la cible ±10%
        elif 0.80 <= ratio <= 1.20:
            components["nutrition"] = 15
        else:
            components["nutrition"] = 5
    else:
        components["nutrition"] = 12  # neutre

    # ── Entraînement (max 20 pts) ──────────────────────────────────────────
    entrainement = snapshot_data.get("entrainement", {})
    if entrainement.get("nb_seances", 0) >= 1:
        components["entrainement"] = 20
    else:
        components["entrainement"] = 8  # repos compte pour la moitié

    total = sum(components.values())
    total = min(100, max(0, total))

    label = _label_from_score(total)
    return {"score": total, "components": components, "label": label}


def _label_from_score(score: int) -> str:
    if score >= 85:
        return "Excellente journée"
    if score >= 70:
        return "Bonne journée"
    if score >= 55:
        return "Journée correcte"
    if score >= 40:
        return "Journée difficile"
    return "Journée compliquée"
