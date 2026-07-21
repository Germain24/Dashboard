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


def compute_volatility(valeurs: list[float] | None = None, rendements: list[float] | None = None) -> float:
    """Volatilité annualisée des rendements quotidiens (std × √252).

    Accepte soit des valeurs brutes (rendements calculés en interne, comportement
    historique), soit des rendements déjà calculés (ex. ajustés des apports).
    """
    if rendements is None:
        if valeurs is None or len(valeurs) < 2:
            return 0.0
        rendements = [(valeurs[i] / valeurs[i-1]) - 1 for i in range(1, len(valeurs))]
    n = len(rendements)
    if n < 2:
        return 0.0
    mean = sum(rendements) / n
    variance = sum((r - mean) ** 2 for r in rendements) / (n - 1)
    return round(math.sqrt(variance) * math.sqrt(252) * 100, 2)


def _cashflow_adjusted_returns(snapshots: list[dict]) -> list[float]:
    """Rendements journaliers neutralisant l'effet des apports/retraits (même
    formule que portfolio.time_weighted_return) -- un jour de dépôt ne doit
    pas s'enregistrer comme un rendement massif et fausser volatilité/Sharpe."""
    rets: list[float] = []
    prev: dict | None = None
    for s in snapshots:
        v = s.get("valeur")
        inv = s.get("investit", 0) or 0
        if v is None:
            continue
        if prev is not None and prev["valeur"] > 0:
            apport = inv - prev["investit"]
            rets.append(((v - apport) / prev["valeur"]) - 1)
        prev = {"valeur": v, "investit": inv}
    return rets


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


def compute_sortino(
    rendements: list[float],
    taux_sans_risque: float = 0.04,
) -> float | None:
    """Ratio de Sortino annualisé : comme Sharpe, mais le dénominateur ne
    retient que la volatilité *baissière* (rendements sous le MAR).

    Renvoie ``None`` quand aucun rendement n'est sous le MAR : le ratio est alors
    mathématiquement infini, et 0.0 (la valeur que ``compute_sharpe`` renvoie
    pour un dénominateur nul) se lirait à tort comme « mauvais » alors que la
    série n'a subi aucune baisse. ``None`` = « non défini », déjà le contrat de
    ``sharpe`` côté API (``Optional[float]``).
    """
    if len(rendements) < 2:
        return 0.0
    n = len(rendements)
    mean = sum(rendements) / n
    # MAR quotidien équivalent au taux annuel, cohérent avec l'annualisation
    # géométrique de ann_ret ci-dessous.
    mar = (1 + taux_sans_risque) ** (1 / 252) - 1
    pertes = [r - mar for r in rendements if r < mar]
    if not pertes:
        return None
    # Dénominateur n-1 sur l'échantillon complet (même correction de Bessel que
    # compute_sharpe) : seule la *somme* est restreinte aux rendements baissiers.
    downside = math.sqrt(sum(p ** 2 for p in pertes) / (n - 1))
    ann_ret = (1 + mean) ** 252 - 1
    ann_downside = downside * math.sqrt(252)
    return round((ann_ret - taux_sans_risque) / ann_downside, 3) if ann_downside > 0 else None


def get_risk_metrics(
    snapshots: list[dict],
    positions: list[dict],
) -> dict:
    """Calcule toutes les métriques de risque depuis les snapshots et positions."""
    valeurs = [s["valeur"] for s in snapshots if s.get("valeur")]
    if not valeurs:
        return {"max_drawdown_pct": 0, "volatilite_annualisee_pct": 0, "hhi": 0, "sharpe": 0,
                "sortino": None, "n_positions": 0, "concentration": "inconnu"}

    has_investit = all("investit" in s for s in snapshots)
    if has_investit:
        rets = _cashflow_adjusted_returns(snapshots)
    else:
        rets = [(valeurs[i] / valeurs[i-1]) - 1 for i in range(1, len(valeurs))]

    mdd = compute_max_drawdown(valeurs)
    vol = compute_volatility(rendements=rets)
    sharpe = compute_sharpe(rets)
    sortino = compute_sortino(rets)

    # HHI sur les valeurs actuelles des positions
    poids_pos = [p.get("valeur_actuelle", 0) for p in positions if p.get("valeur_actuelle", 0) > 0]
    hhi = compute_hhi(poids_pos)

    concentration = "élevée" if hhi > 0.25 else ("modérée" if hhi > 0.10 else "faible")
    return {
        "max_drawdown_pct": mdd,
        "volatilite_annualisee_pct": vol,
        "hhi": hhi,
        "sharpe": sharpe,
        "sortino": sortino,
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
    from app.services.finance.buffett.reporting import get_latest_results_by_ticker
    from app.services.finance.portfolio import get_positions

    positions = get_positions(session)
    latest = get_latest_results_by_ticker(session, (p["ticker"] for p in positions))
    secteur_par_ticker = {
        r.ticker: r.secteur
        for r in latest.values()
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
    frac_by_ticker: Optional[dict[str, dict[str, float]]] = None,
) -> list[dict]:
    """Treemap hiérarchique groupé par secteur / pays / devise.

    Renvoie des nodes plats ``{id, parent, label, valeur}`` (contrat
    ``TreemapNodeOut`` / ``FlatTreemap``) : une racine par groupe (``parent=""``)
    et un enfant par position rattaché à sa racine. ``group_by="devise"`` lit la
    devise sur la position ; secteur/pays passent par ``label_by_ticker`` (résolu
    en amont depuis les résultats Buffett).

    ``frac_by_ticker`` (pays uniquement) : {ticker: {label: fraction 0-1}} pour
    les ETF connus du look-through (``buffett.lookthrough.load_lookthrough``) —
    répartit leur valeur sur plusieurs racines au lieu de tout attribuer à leur
    seul pays de cotation. Un ticker absent de ce mapping garde le comportement
    ``label_by_ticker`` habituel.
    """
    label_by_ticker = label_by_ticker or {}
    frac_by_ticker = frac_by_ticker or {}
    held = [p for p in positions if p.get("valeur_actuelle", 0) > 0]
    if not held:
        return []

    # Chaque contribution = une part (ticker, valeur) rattachée à un label ;
    # un ETF look-through produit plusieurs contributions pour un seul ticker.
    contributions: list[dict] = []
    for p in held:
        valeur = p.get("valeur_actuelle", 0)
        if group_by == "devise":
            contributions.append({"label": p.get("devise") or "Inconnu", "ticker": p["ticker"], "valeur": valeur})
            continue
        frac = frac_by_ticker.get(p["ticker"])
        if frac:
            for label, fraction in frac.items():
                contributions.append({"label": label, "ticker": p["ticker"], "valeur": valeur * fraction})
        else:
            label = label_by_ticker.get(p["ticker"]) or "Inconnu"
            contributions.append({"label": label, "ticker": p["ticker"], "valeur": valeur})

    groups: dict[str, list[dict]] = {}
    for c in contributions:
        groups.setdefault(c["label"], []).append(c)

    def _val(items: list[dict]) -> float:
        return sum(i["valeur"] for i in items)

    nodes: list[dict] = []
    for label, items in sorted(groups.items(), key=lambda kv: _val(kv[1]), reverse=True):
        nodes.append({"id": label, "parent": "", "label": label, "valeur": round(_val(items), 2)})
        for c in sorted(items, key=lambda x: x["valeur"], reverse=True):
            nodes.append({
                "id": f"{label}/{c['ticker']}",
                "parent": label,
                "label": c["ticker"],
                "valeur": round(c["valeur"], 2),
            })
    return nodes
