"""Score thermique d'un item + cible thermique d'une tenue.

Port quasi-identique du legacy. Une seule évolution :
- `target_thermal(mean_temp)` accepte directement la **moyenne horaire 7h-23h**
  (calculée côté `weather.py`) au lieu de la moyenne brute (t_min + t_max)/2.
  Cf. décision CONV 2 — body coton refonte.
"""

from __future__ import annotations

from typing import Any

from app.services.garderobe.constants import (
    BODY_THERMAL_BONUS,
    MATIERE_THERMIQUE,
    THERMAL_NEUTRAL_CATS,
)


def thermal_score(item: dict[str, Any] | None) -> float:
    """Capacité thermique d'un item (0..N). Plus c'est élevé, plus ça tient chaud."""
    if not item:
        return 0.0

    # Champ direct s'il existe
    if "chaleur" in item:
        return float(item["chaleur"])

    if item.get("categorie") in THERMAL_NEUTRAL_CATS:
        return 0.0

    # Si aucune borne de température n'est définie, on considère neutre
    if item.get("temp_min") is None and item.get("temp_max") is None:
        return 0.0

    # Heuristique de base — plus l'item est conçu pour le froid, plus il chauffe
    base_score = max(0.0, 25.0 - float(item.get("temp_min") or 20)) / 2.0

    # Pondération par matière (le layering bonus est dans calculate_thermal_gap)
    matiere = (item.get("matiere") or "Coton").lower()
    coef = 1.0
    for key, val in MATIERE_THERMIQUE.items():
        if key.lower() in matiere:
            coef = val
            break

    return base_score * coef


def target_thermal(mean_temp: float) -> float:
    """Cible thermique pour une tenue, étant donnée une température moyenne.

    Identique au legacy : on vise un total thermique inversement proportionnel
    à la température ressentie moyenne.
    """
    return 50.0 - (mean_temp * 1.5)


def calculate_thermal_gap(
    tenue: dict[str, Any],
    mean_temp: float,
    use_body: bool,
) -> tuple[float, float, float]:
    """Calcule (total_thermal, target, gap) pour une tenue.

    `tenue` est un dict {slot_id: item_dict | None}.
    `gap > 0` = on est en dessous de la cible (il fait trop froid pour la tenue).
    """
    target = target_thermal(mean_temp)
    worn = [v for v in tenue.values() if v is not None]
    total = sum(thermal_score(i) for i in worn)

    # Layering bonus sur le torse (3 couches max)
    torso_layers = 0
    if tenue.get("Haut"):
        torso_layers += 1
    if tenue.get("Veste"):
        torso_layers += 1
    if tenue.get("Manteau"):
        torso_layers += 1
    if torso_layers > 1:
        total *= 1 + (torso_layers - 1) * 0.1

    if use_body:
        total += BODY_THERMAL_BONUS

    return total, target, target - total
