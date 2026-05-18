"""Estimation 1RM (one-rep max) — formule Epley.

Décision CONV 7 : Epley uniquement.

    1RM = poids × (1 + reps / 30)

- Valide cliniquement pour 1-10 reps (au-delà, la formule sous-estime).
- Pour 1 rep, 1RM = poids (formule cohérente : 1 + 1/30 ≈ 1.033 ; on retourne
  directement `poids` si reps == 1 pour rester exact).
- Pour 0 rep ou poids 0 : retourne 0.0 (cas dégénéré, pas d'erreur).
"""

from __future__ import annotations


def epley_1rm(poids_kg: float, reps: int) -> float:
    """Estime le 1RM via Epley.

    >>> epley_1rm(100, 1)
    100.0
    >>> round(epley_1rm(100, 10), 2)
    133.33
    >>> epley_1rm(0, 5)
    0.0
    """
    if poids_kg <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return float(poids_kg)
    return float(poids_kg) * (1.0 + reps / 30.0)


def best_1rm_from_sets(sets: list[dict]) -> float:
    """Meilleur 1RM estimé d'une liste de séries.

    `sets` : liste de dicts avec au moins `reps` et `poids_kg`.

    Retourne 0.0 si la liste est vide ou si toutes les séries sont nulles.
    """
    if not sets:
        return 0.0
    best = 0.0
    for s in sets:
        reps = int(s.get("reps", 0) or 0)
        poids = float(s.get("poids_kg", 0.0) or 0.0)
        e = epley_1rm(poids, reps)
        if e > best:
            best = e
    return best
