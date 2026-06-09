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


def compute_sector_diversification(items: list[dict], seuil_pct: float = 30.0) -> dict:
    """Diversification sectorielle + détection de surpondération.

    ``items`` : liste de ``{"valeur": float, "secteur": str}``.
    Agrège la valeur par secteur, calcule le poids de chaque secteur, flague ceux
    au-dessus de ``seuil_pct``, et donne un HHI sectoriel (0=diversifié, 1=concentré).
    """
    total = sum(i.get("valeur", 0) for i in items if i.get("valeur", 0) > 0)
    if total <= 0:
        return {"secteurs": [], "hhi_secteur": 0.0, "n_secteurs": 0,
                "seuil_pct": seuil_pct, "n_surponderes": 0}

    by_sec: dict[str, float] = {}
    for i in items:
        v = i.get("valeur", 0)
        if v > 0:
            sec = i.get("secteur") or "Inconnu"
            by_sec[sec] = by_sec.get(sec, 0) + v

    secteurs = [
        {
            "secteur": s,
            "valeur": round(v, 2),
            "poids_pct": round(v / total * 100, 2),
            "surpondere": (v / total * 100) > seuil_pct,
        }
        for s, v in sorted(by_sec.items(), key=lambda kv: kv[1], reverse=True)
    ]
    hhi = sum((v / total) ** 2 for v in by_sec.values())
    return {
        "secteurs": secteurs,
        "hhi_secteur": round(hhi, 4),
        "n_secteurs": len(by_sec),
        "seuil_pct": seuil_pct,
        "n_surponderes": sum(1 for x in secteurs if x["surpondere"]),
    }


def get_sector_diversification(session, seuil_pct: float = 30.0) -> dict:
    """Diversification sectorielle réelle : joint les positions aux secteurs Buffett."""
    from app.services.finance.portfolio import get_positions
    from app.models.finance import BuffettRunResult
    from sqlmodel import select

    positions = get_positions(session)
    secteur_par_ticker = {
        r.ticker: r.secteur
        for r in session.exec(select(BuffettRunResult)).all()
        if r.secteur
    }
    items = [
        {"valeur": p.get("valeur_actuelle", 0), "secteur": secteur_par_ticker.get(p["ticker"], "Inconnu")}
        for p in positions
    ]
    return compute_sector_diversification(items, seuil_pct)


def get_treemap_data(
    positions: list[dict],
    group_by: str = "secteur",
    label_by_ticker: Optional[dict[str, str]] = None,
) -> list[dict]:
    """Treemap hiérarchique groupé par secteur / pays / devise.

    Renvoie des nodes plats ``{id, parent, label, valeur}`` (contrat
    ``TreemapNodeOut`` / ``FlatTreemap``) : une racine par groupe (``parent=""``)
    et un enfant par position rattaché à sa racine. ``group_by="devise"`` lit la
    devise sur la position ; secteur/pays passent par ``label_by_ticker`` (résolu
    en amont depuis les résultats Buffett).
    """
    label_by_ticker = label_by_ticker or {}
    held = [p for p in positions if p.get("valeur_actuelle", 0) > 0]
    if not held:
        return []

    groups: dict[str, list[dict]] = {}
    for p in held:
        if group_by == "devise":
            label = p.get("devise") or "Inconnu"
        else:
            label = label_by_ticker.get(p["ticker"]) or "Inconnu"
        groups.setdefault(label, []).append(p)

    def _val(items: list[dict]) -> float:
        return sum(i.get("valeur_actuelle", 0) for i in items)

    nodes: list[dict] = []
    for label, items in sorted(groups.items(), key=lambda kv: _val(kv[1]), reverse=True):
        nodes.append({"id": label, "parent": "", "label": label, "valeur": round(_val(items), 2)})
        for p in sorted(items, key=lambda x: x.get("valeur_actuelle", 0), reverse=True):
            nodes.append({
                "id": f"{label}/{p['ticker']}",
                "parent": label,
                "label": p["ticker"],
                "valeur": round(p.get("valeur_actuelle", 0), 2),
            })
    return nodes
