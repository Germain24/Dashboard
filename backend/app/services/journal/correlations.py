"""Corrélations déterministes humeur ↔ autres modules (#476). Aucune IA."""
from __future__ import annotations

import math


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de Pearson, ou None si < 2 paires ou variance nulle."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return round(cov / math.sqrt(vx * vy), 3)


def interpret(r: float) -> dict:
    a = abs(r)
    force = "forte" if a >= 0.6 else "modérée" if a >= 0.4 else "faible" if a >= 0.2 else "négligeable"
    return {"force": force, "signe": "positif" if r >= 0 else "négatif"}


def correlate_series(source_by_date: dict[str, float], target_by_date: dict[str, float]) -> dict:
    """Corrèle deux séries datées sur l'intersection de leurs dates."""
    dates = sorted(set(source_by_date) & set(target_by_date))
    xs = [source_by_date[d] for d in dates]
    ys = [target_by_date[d] for d in dates]
    r = pearson(xs, ys)
    if r is None:
        return {"r": None, "force": "indéterminée", "signe": "", "n": len(dates)}
    return {"r": r, "n": len(dates), **interpret(r)}
