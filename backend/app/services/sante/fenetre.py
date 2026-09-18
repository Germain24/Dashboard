"""Logique pure de la fenêtre batch-cook (cadence, cibles, répartition).

Cadence figée (spec §1) : lundi → 3 jours [lun,mar,mer] ; jeudi → 4 jours
[jeu,ven,sam,dim]. Les autres jours appartiennent à l'une de ces deux fenêtres.

Les jours COUVERTS par chaque fenêtre sont distincts du jour où l'on ACHÈTE et
CUISINE : depuis 2026-08-11, les courses se font le lundi et le mercredi pour
profiter du rabais étudiant Super C (lun→mer), donc la fenêtre jeu-dim est
achetée la veille de son premier jour. Cf. `shopping_day_for`.
"""
from __future__ import annotations

import datetime as dt

_MONDAY, _THURSDAY = 0, 3


def anchor_for(day: dt.date) -> dt.date:
    """Ancre (lun ou jeu) de la fenêtre contenant `day`."""
    wd = day.weekday()
    if wd in (0, 1, 2):
        return day - dt.timedelta(days=wd)          # → lundi
    return day - dt.timedelta(days=wd - _THURSDAY)  # jeu..dim → jeudi


def window_days(anchor: dt.date) -> list[dt.date]:
    """Jours couverts par une fenêtre ancrée lun (3) ou jeu (4)."""
    wd = anchor.weekday()
    if wd == _MONDAY:
        n = 3
    elif wd == _THURSDAY:
        n = 4
    else:
        raise ValueError(f"Ancre invalide {anchor} (weekday={wd}) : attendu lundi ou jeudi.")
    return [anchor + dt.timedelta(days=i) for i in range(n)]


def shopping_day_for(anchor: dt.date) -> dt.date:
    """Jour où l'on fait les courses ET cuisine pour la fenêtre ancrée `anchor`.

    Ancre lundi   -> ce lundi même (la fenêtre lun-mer démarre le jour des courses).
    Ancre jeudi   -> le mercredi PRÉCÉDENT, veille du premier jour couvert.

    Le rabais étudiant Super C ne s'applique que du lundi au mercredi : acheter
    le mercredi pour jeu-dim le capte, acheter le jeudi le perdrait. Les jours
    couverts, eux, ne changent pas (cf. `window_days`).
    """
    wd = anchor.weekday()
    if wd == _MONDAY:
        return anchor
    if wd == _THURSDAY:
        return anchor - dt.timedelta(days=1)   # mercredi
    raise ValueError(f"Ancre invalide {anchor} (weekday={wd}) : attendu lundi ou jeudi.")


def window_targets(daily: list[dict[str, float]]) -> dict[str, float]:
    """Somme clé-à-clé des cibles journalières (Calories, micros, Prix_Max,
    Poids_Corps… tout est additif : la fenêtre vise le total des jours)."""
    out: dict[str, float] = {}
    for d in daily:
        for k, v in d.items():
            try:
                out[k] = out.get(k, 0.0) + float(v)
            except (TypeError, ValueError):
                continue
    return out


def split_by_day(
    food_set: dict[str, float], calorie_targets: list[float],
    max_daily_g: dict[str, float] | None = None,
) -> list[dict[str, float]]:
    """Répartit les grammes totaux par jour au prorata des calories-cibles.

    Σ (jours) = food_set exactement (le dernier jour absorbe l'arrondi flottant).
    """
    total_cal = sum(calorie_targets)
    n = len(calorie_targets)
    if n == 0:
        return []
    # total_cal <= 0 (cas dégénéré, jamais atteint en pratique : les calories-cibles
    # sont toujours positives) → répartition égale, la conservation reste exacte.
    shares = [1.0 / n] * n if total_cal <= 0 else [c / total_cal for c in calorie_targets]
    per_day: list[dict[str, float]] = [{} for _ in range(n)]
    caps = max_daily_g or {}
    for aliment, grams in food_set.items():
        cap = float(caps.get(aliment, 0.0) or 0.0)
        if cap > 0.0 and grams <= cap * n + 1e-6:
            # Répartition proportionnelle avec saturation (« water filling »).
            # Quand un jour sportif dépasserait le plafond, son surplus est
            # redistribué aux autres jours tout en conservant le total exact.
            allocation = [0.0] * n
            remaining = float(grams)
            active = set(range(n))
            while active and remaining > 1e-9:
                weight_sum = sum(shares[i] for i in active)
                weights = {
                    i: (shares[i] / weight_sum if weight_sum > 0 else 1.0 / len(active))
                    for i in active
                }
                saturated = [
                    i for i in active if remaining * weights[i] > cap + 1e-9
                ]
                if not saturated:
                    for i in active:
                        allocation[i] += remaining * weights[i]
                    remaining = 0.0
                    break
                for i in saturated:
                    room = max(0.0, cap - allocation[i])
                    allocation[i] += room
                    remaining -= room
                    active.remove(i)
            # Le dernier jour absorbe uniquement l'imprécision flottante.
            allocation[-1] += float(grams) - sum(allocation)
            for i, value in enumerate(allocation):
                per_day[i][aliment] = value
            continue
        assigned = 0.0
        for i in range(n - 1):
            g = grams * shares[i]
            per_day[i][aliment] = g
            assigned += g
        per_day[n - 1][aliment] = grams - assigned  # reste exact
    return per_day
