"""Backtest simple d'une allocation cible (buy-and-hold) sur des séries de prix.

Cœur pur (sans réseau) : à partir de séries de prix alignées et de poids cibles,
calcule la courbe d'équité normalisée à 100 et le rendement total. La
récupération des prix (yfinance) est faite par l'appelant / l'endpoint.
"""

from __future__ import annotations


def simulate_allocation(
    prices: dict[str, list[float]],
    weights: dict[str, float],
) -> dict:
    """Courbe d'équité d'un portefeuille buy-and-hold.

    ``prices`` : ticker -> série de prix (même longueur, alignée dans le temps).
    ``weights`` : ticker -> poids (en %). Seuls les tickers présents dans les deux
    sont utilisés ; les poids sont renormalisés à 100 %.

    Retourne ``{"equity": [...], "rendement_pct": x, "n_points": n}`` où ``equity``
    démarre à 100. Buy-and-hold : chaque titre évolue selon ``prix_t / prix_0``.
    """
    common = [t for t in weights if t in prices and prices[t]]
    common = [t for t in common if (weights[t] or 0) > 0 and prices[t][0] > 0]
    if not common:
        return {"equity": [], "rendement_pct": 0.0, "n_points": 0}

    n = min(len(prices[t]) for t in common)
    total_w = sum(weights[t] for t in common)
    norm = {t: weights[t] / total_w for t in common}

    equity: list[float] = []
    for i in range(n):
        val = sum(norm[t] * (prices[t][i] / prices[t][0]) for t in common)
        equity.append(round(val * 100, 4))

    rendement = round(equity[-1] - 100, 2) if equity else 0.0
    return {"equity": equity, "rendement_pct": rendement, "n_points": n}
