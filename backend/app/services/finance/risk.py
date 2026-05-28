"""Métriques de risque portefeuille : volatilité, drawdown, HHI, corrélations."""

from __future__ import annotations

import math
from typing import Optional


def compute_max_drawdown(valeurs: list[float]) -> float:
    """Max drawdown depuis le plus haut (0-100 %)."""
    if len(valeurs) < 2:
        return 0.0
    peak = valeurs[0]; mdd = 0.0
    for v in valeurs:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return round(mdd, 2)


def compute_volatility(valeurs: list[float]) -> float:
    """Volatilité annualisée des rendements quotidiens (std × √252)."""
    if len(valeurs) < 2:
        return 0.0
    rets = [(valeurs[i] / valeurs[i-1]) - 1 for i in range(1, len(valeurs))]
    n = len(rets)
    if n < 2:
        return 0.0
    mean = sum(rets) / n
    variance = sum((r - mean) ** 2 for r in rets) / (n - 1)
    return round(math.sqrt(variance) * math.sqrt(252) * 100, 2)


def compute_hhi(poids: list[float]) -> float:
    """Indice Herfindahl-Hirschman (concentration, 0=diversifié, 1=concentré)."""
    total = sum(poids)
    if total == 0:
        return 0.0
    normalized = [p / total for p in poids]
    return round(sum(w ** 2 for w in normalized), 4)


def compute_sharpe(
    rendements: list[float],
    taux_sans_risque: float = 0.04,
) -> float:
    """Ratio de Sharpe annualisé."""
    if len(rendements) < 2:
        return 0.0
    n = len(rendements)
    mean = sum(rendements) / n
    variance = sum((r - mean) ** 2 for r in rendements) / (n - 1)
    if variance == 0:
        return 0.0
    std = math.sqrt(variance)
    ann_ret = (1 + mean) ** 252 - 1
    ann_vol = std * math.sqrt(252)
    return round((ann_ret - taux_sans_risque) / ann_vol, 3) if ann_vol > 0 else 0.0


def get_risk_metrics(
    snapshots: list[dict],
    positions: list[dict],
) -> dict:
    """Calcule toutes les métriques de risque depuis les snapshots et positions."""
    valeurs = [s["valeur"] for s in snapshots if s.get("valeur")]
    if not valeurs:
        return {"max_drawdown_pct": 0, "volatilite_pct": 0, "hhi": 0, "sharpe": 0,
                "n_positions": 0, "concentration": "inconnu"}

    rets = [(valeurs[i] / valeurs[i-1]) - 1 for i in range(1, len(valeurs))]
    mdd = compute_max_drawdown(valeurs)
    vol = compute_volatility(valeurs)
    sharpe = compute_sharpe(rets)

    # HHI sur les valeurs actuelles des positions
    poids_pos = [p.get("valeur_actuelle", 0) for p in positions if p.get("valeur_actuelle", 0) > 0]
    hhi = compute_hhi(poids_pos)

    concentration = "élevée" if hhi > 0.25 else ("modérée" if hhi > 0.10 else "faible")
    return {
        "max_drawdown_pct": mdd,
        "volatilite_annualisee_pct": vol,
        "hhi": hhi,
        "sharpe": sharpe,
        "n_positions": len(positions),
        "concentration": concentration,
    }


def get_treemap_data(positions: list[dict]) -> list[dict]:
    """Données pour treemap secteurs/pays/devises."""
    total = sum(p.get("valeur_actuelle", 0) for p in positions)
    if total == 0:
        return []
    return [
        {
            "ticker": p["ticker"],
            "broker": p.get("broker", ""),
            "valeur": round(p.get("valeur_actuelle", 0), 2),
            "pct": round(p.get("valeur_actuelle", 0) / total * 100, 2),
        }
        for p in sorted(positions, key=lambda x: x.get("valeur_actuelle", 0), reverse=True)
        if p.get("valeur_actuelle", 0) > 0
    ]
