"""Optimiseur de tenue — refondu pour CONV 2.

Différences vs legacy :
1. La **cible thermique** se base sur la moyenne du ressenti horaire entre
   `GARDEROBE_HOUR_START` et `GARDEROBE_HOUR_END` (par défaut 7h-23h), au lieu
   de `(t_min + t_max) / 2`. La moyenne est fournie par `weather.py`.
2. Le **body coton** est inclus dans l'espace de recherche : pour chaque
   combinaison de slots, on évalue les deux variantes (avec/sans body) et on
   garde celle qui a le **meilleur style** parmi les combos thermalement
   valides. Plus de post-traitement « si gap > 1.5 alors active body ».

Reste port à l'identique :
- Slots actifs selon météo (cold_or_rain, cool, very_cold)
- Bloquer l'item le plus sale dans son slot (rotation forcée)
- Filtre cohérence haut/bas (|thermal(haut) - thermal(bas)| <= 3.5)
- Ajout greedy d'accessoires optionnels après le solveur
"""

from __future__ import annotations

import itertools
from typing import Any, Iterable, Optional

from app.services.garderobe.constants import SLOTS
from app.services.garderobe.state import disponible
from app.services.garderobe.style import style_score
from app.services.garderobe.thermal import (
    calculate_thermal_gap,
    target_thermal,
    thermal_score,
)


def _score_rotation(item: dict[str, Any]) -> int:
    """Plus grand = plus proche du seuil de lavage."""
    p = item.get("portes", 0)
    ep = item.get("etat_propre", 60) or 60
    return p % ep


def _active_slots(mean_temp: float, rain: bool) -> list[dict]:
    out = []
    for slot in SLOTS:
        need = slot["need"]
        if need == "ALWAYS":
            out.append(slot)
        elif need == "METEO":
            sid = slot["id"]
            if sid == "Manteau" and (mean_temp < 18 or rain):
                out.append(slot)
            elif sid == "Veste" and mean_temp < 15:
                out.append(slot)
            elif sid == "Echarpe" and mean_temp < 10:
                out.append(slot)
    return out


def _slot_for_category(categorie: str) -> Optional[str]:
    for slot in SLOTS:
        if categorie in slot["categories"]:
            return slot["id"]
    return None


def suggest_outfit(
    wardrobe: Iterable[dict[str, Any]],
    weather_mean_temp: float,
    rain: bool = False,
    *,
    max_candidates_per_slot: int = 15,
    thermal_tolerance: float = 4.0,
    haut_bas_tolerance: float = 3.5,
) -> dict[str, Any]:
    """Suggère une tenue.

    Retourne un dict :
        {
            slot_id: item_dict | None,    # 12 slots
            "__use_body": bool,
            "__t_outfit": float,           # mean_temp utilisée
            "__target_thermal": float,
            "__total_thermal": float,
            "__style": float,
        }
    """
    result: dict[str, Any] = {s["id"]: None for s in SLOTS}
    available = [i for i in wardrobe if disponible(i)]
    if not available:
        result.update({
            "__use_body": False,
            "__t_outfit": weather_mean_temp,
            "__target_thermal": target_thermal(weather_mean_temp),
            "__total_thermal": 0.0,
            "__style": 0.0,
        })
        return result

    target = target_thermal(weather_mean_temp)

    # 1) Bloquer l'item le plus sale → forcer la rotation
    #    Important : on ne bloque que si l'item a déjà été porté (score > 0).
    #    Sinon, une garde-robe neuve verrait son premier item arbitrairement
    #    forcé dans chaque suggestion, ce qui casse la sélection thermique.
    dirtiest = max(available, key=_score_rotation, default=None)
    blocked_slot_id: Optional[str] = None
    if dirtiest and _score_rotation(dirtiest) > 0:
        blocked_slot_id = _slot_for_category(dirtiest.get("categorie", ""))

    # 2) Slots actifs aujourd'hui + slot bloqué (s'il est OPTIONAL)
    active_slots = _active_slots(weather_mean_temp, rain)
    if blocked_slot_id and not any(s["id"] == blocked_slot_id for s in active_slots):
        for s in SLOTS:
            if s["id"] == blocked_slot_id:
                active_slots.append(s)
                break

    # 3) Candidats par slot. Veste peut être None (manteau seul).
    slot_candidates: dict[str, list[Optional[dict]]] = {}
    for slot in active_slots:
        sid = slot["id"]
        if sid == blocked_slot_id and dirtiest is not None:
            slot_candidates[sid] = [dirtiest]
            continue
        cats = slot["categories"]
        options = [i for i in available if i.get("categorie") in cats]
        if not options:
            continue
        # Tri : on garde une diversité thermique en triant par chaleur décroissante
        options.sort(key=lambda i: thermal_score(i), reverse=True)
        options = options[:max_candidates_per_slot]
        if sid == "Veste":
            slot_candidates[sid] = [None] + options
        else:
            slot_candidates[sid] = list(options)

    if not slot_candidates:
        result.update({
            "__use_body": False,
            "__t_outfit": weather_mean_temp,
            "__target_thermal": target,
            "__total_thermal": 0.0,
            "__style": 0.0,
        })
        return result

    # 4) Cartesian product
    keys = list(slot_candidates.keys())
    values = list(slot_candidates.values())

    valid: list[dict[str, Any]] = []
    all_combos: list[dict[str, Any]] = []

    for combo in itertools.product(*values):
        outfit = dict(zip(keys, combo))

        # Unicité (ex: Bijoux 1 ≠ Bijoux 2)
        worn_ids = [i["id"] for i in outfit.values() if i is not None]
        if len(worn_ids) != len(set(worn_ids)):
            continue

        # Filtre cohérence haut/bas
        haut = outfit.get("Haut")
        bas = outfit.get("Pantalon")
        if haut and bas:
            if abs(thermal_score(haut) - thermal_score(bas)) > haut_bas_tolerance:
                continue

        for use_body in (False, True):
            total, _t, _gap = calculate_thermal_gap(outfit, weather_mean_temp, use_body)
            entry = {
                "outfit": outfit,
                "use_body": use_body,
                "total_thermal": total,
                "thermal_dist": abs(total - target),
            }
            all_combos.append(entry)
            if abs(total - target) <= thermal_tolerance:
                valid.append(entry)

    # 5) Sélection : meilleur style parmi valides ; sinon fallback
    if valid:
        # Pour chaque combo valide, on calcule le score de style
        for v in valid:
            v["style"] = style_score(list(v["outfit"].values()))
        valid.sort(key=lambda v: v["style"], reverse=True)
        best = valid[0]
    else:
        # Fallback : meilleur style parmi tous, on accepte le gap thermique
        for v in all_combos:
            v["style"] = style_score(list(v["outfit"].values()))
        all_combos.sort(key=lambda v: (v["style"], -v["thermal_dist"]), reverse=True)
        best = all_combos[0] if all_combos else None

    if not best:
        result.update({
            "__use_body": False,
            "__t_outfit": weather_mean_temp,
            "__target_thermal": target,
            "__total_thermal": 0.0,
            "__style": 0.0,
        })
        return result

    result.update(best["outfit"])

    # 6) Ajout greedy d'accessoires optionnels (style maximisé)
    current_items = [v for v in result.values() if isinstance(v, dict)]
    optional_slots = [s for s in SLOTS if s["need"] == "OPTIONAL" and s["id"] != blocked_slot_id]

    for slot in optional_slots:
        sid = slot["id"]
        if result.get(sid):
            continue
        cats = slot["categories"]
        current_ids = {i["id"] for i in result.values() if isinstance(i, dict)}
        options = [
            i for i in available
            if i.get("categorie") in cats and i["id"] not in current_ids
        ]
        if not options:
            continue
        best_acc = None
        baseline = style_score(current_items)
        for opt in options:
            new_score = style_score(current_items + [opt])
            if new_score > baseline:
                baseline = new_score
                best_acc = opt
        if best_acc:
            result[sid] = best_acc
            current_items.append(best_acc)

    # 7) Métadonnées
    total_final, target_final, _ = calculate_thermal_gap(
        {k: v for k, v in result.items() if not k.startswith("__")},
        weather_mean_temp,
        best["use_body"],
    )
    result["__use_body"] = best["use_body"]
    result["__t_outfit"] = float(weather_mean_temp)
    result["__target_thermal"] = float(target_final)
    result["__total_thermal"] = float(total_final)
    result["__style"] = float(style_score(current_items))
    return result
    result["__use_body"] = best["use_body"]
    result["__t_outfit"] = float(weather_mean_temp)
    result["__target_thermal"] = float(target_final)
    result["__total_thermal"] = float(total_final)
    result["__style"] = float(style_score(current_items))
    return result
