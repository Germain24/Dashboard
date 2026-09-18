"""Comparaison période sur période (#229) — helper générique réutilisable.

Donne, pour une métrique, sa variation par rapport à la période précédente
(cette semaine vs précédente, ce mois vs le mois dernier, etc.). Réutilisable
par tous les modules (budget, santé, habitudes…).
"""

from __future__ import annotations

from typing import Optional, TypedDict


class Comparison(TypedDict):
    current: float
    previous: float
    delta: float
    delta_pct: Optional[float]
    direction: str  # "up" | "down" | "flat"


def period_over_period(current: float, previous: float) -> Comparison:
    """Compare `current` à `previous`.

    - `delta`      : différence absolue (current - previous)
    - `delta_pct`  : variation en % (sur |previous|) ; None si previous == 0
    - `direction`  : "up" / "down" / "flat" selon le signe de delta
    """
    delta = current - previous
    delta_pct: Optional[float] = None
    if previous != 0:
        delta_pct = delta / abs(previous) * 100.0
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "delta_pct": delta_pct,
        "direction": direction,
    }
