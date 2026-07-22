"""Métriques de risque portefeuille : volatilité, drawdown, HHI, corrélations."""

from __future__ import annotations

import math
import unicodedata
from functools import lru_cache
from typing import Optional

from app.services.finance.metrics import (
    adjusted_wealth_index,
    daily_returns_for_risk,
    prepare_metric_snapshots,
    return_observations,
)


def compute_max_drawdown(valeurs: list[float]) -> float:
    """Max drawdown depuis le plus haut (0-100 %)."""
    if len(valeurs) < 2:
        return 0.0
    peak = valeurs[0]
    mdd = 0.0
    for v in valeurs:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return round(mdd, 2)


def compute_volatility(
    valeurs: list[float] | None = None,
    rendements: list[float] | None = None,
    periods_per_year: float = 252.0,
) -> float:
    """Volatilité annualisée (std × racine du nombre de périodes annuelles).

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
    return round(math.sqrt(variance) * math.sqrt(periods_per_year) * 100, 2)


def _cashflow_adjusted_returns(snapshots: list[dict]) -> list[float]:
    """Rendements journaliers neutralisant l'effet des apports/retraits (même
    formule que portfolio.time_weighted_return) -- un jour de dépôt ne doit
    pas s'enregistrer comme un rendement massif et fausser volatilité/Sharpe."""
    return [
        observation.factor - 1.0
        for observation in return_observations(snapshots)
        if observation.valid
    ]


def _cashflow_adjusted_daily_returns(snapshots: list[dict]) -> list[float]:
    """Version date-aware utilisée par les ratios de risque.

    Un rendement observé après plusieurs jours est converti en rendements
    journaliers géométriquement équivalents. Les jours sans snapshot ne sont
    ainsi plus assimilés à une unique séance extrêmement volatile.
    """
    return daily_returns_for_risk(return_observations(snapshots))


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
    periods_per_year: float = 252.0,
) -> float | None:
    """Ratio de Sharpe annualisé selon la définition arithmétique standard."""
    if len(rendements) < 2:
        return 0.0
    n = len(rendements)
    mean = sum(rendements) / n
    variance = sum((r - mean) ** 2 for r in rendements) / (n - 1)
    if variance <= 0:
        return None
    std = math.sqrt(variance)
    mar = (1.0 + taux_sans_risque) ** (1.0 / periods_per_year) - 1.0
    return round((mean - mar) / std * math.sqrt(periods_per_year), 3)


def compute_sortino(
    rendements: list[float],
    taux_sans_risque: float = 0.04,
    periods_per_year: float = 252.0,
) -> float | None:
    """Ratio de Sortino annualisé : comme Sharpe, mais le dénominateur ne
    retient que la volatilité *baissière* (rendements sous le MAR).

    Renvoie ``None`` quand aucun rendement n'est sous le MAR : le ratio est alors
    mathématiquement infini, et 0.0 se lirait à tort comme « mauvais » alors que
    la série n'a subi aucune baisse. ``None`` signifie « non défini », comme le
    permet déjà le contrat de ``sharpe`` côté API.
    """
    if len(rendements) < 2:
        return 0.0
    n = len(rendements)
    mean = sum(rendements) / n
    # MAR périodique équivalent au taux annuel.
    mar = (1 + taux_sans_risque) ** (1 / periods_per_year) - 1
    pertes = [r - mar for r in rendements if r < mar]
    if not pertes:
        return None
    # Dénominateur n-1 sur l'échantillon complet (même correction de Bessel que
    # compute_sharpe) : seule la *somme* est restreinte aux rendements baissiers.
    downside = math.sqrt(sum(p ** 2 for p in pertes) / (n - 1))
    if downside <= 0:
        return None
    return round((mean - mar) / downside * math.sqrt(periods_per_year), 3)


_DIVERSIFIED_FUND_COMPONENTS = 100


def _fold_label(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode()
        .strip()
        .lower()
    )


@lru_cache(maxsize=1)
def _load_diversified_tickers() -> frozenset[str]:
    """ETF actions larges et multi-pays connus de ToutBroker.

    Le HHI par ligne de courtier considère sinon CW8 comme une action unique.
    Faute de composition titre par titre dans l'API, on répartit ces fonds sur
    un minimum conservateur de 100 composantes effectives. La décote n'est
    accordée qu'aux ETF actions non sectoriels dont le look-through contient au
    moins deux pays significatifs. ARKK/BITO, les ETF sectoriels, obligataires
    et mono-actif restent ainsi concentrés faute de preuve de diversification.
    """
    try:
        from app.services.finance.buffett.breakdown import load_classification
        from app.services.finance.buffett.lookthrough import load_lookthrough

        classmap, sectmap = load_classification()
        _defensive, countries = load_lookthrough()
        return frozenset(
            str(ticker).upper()
            for ticker, sector in sectmap.items()
            if _fold_label(sector) == "actions diversifiees"
            and _fold_label(classmap.get(ticker, "")) == "actions"
            and sum(
                1
                for weight in countries.get(str(ticker).upper(), {}).values()
                if float(weight or 0) >= 0.02
            ) >= 2
        )
    except Exception:
        return frozenset()


def compute_portfolio_hhi(
    positions: list[dict],
    diversified_tickers: set[str] | frozenset[str] | None = None,
) -> float:
    """HHI économique, avec agrégation des brokers et look-through ETF prudent."""
    by_ticker: dict[str, float] = {}
    for index, position in enumerate(positions):
        value = float(position.get("valeur_actuelle", 0) or 0)
        if value <= 0:
            continue
        ticker = str(position.get("ticker") or f"__position_{index}").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + value
    total = sum(by_ticker.values())
    if total <= 0:
        return 0.0

    diversified = (
        _load_diversified_tickers()
        if diversified_tickers is None
        else frozenset(str(ticker).upper() for ticker in diversified_tickers)
    )
    hhi = 0.0
    for ticker, value in by_ticker.items():
        weight = value / total
        components = _DIVERSIFIED_FUND_COMPONENTS if ticker in diversified else 1
        hhi += weight**2 / components
    return round(hhi, 4)


def get_risk_metrics(
    snapshots: list[dict],
    positions: list[dict],
    diversified_tickers: set[str] | frozenset[str] | None = None,
) -> dict:
    """Calcule toutes les métriques de risque depuis les snapshots et positions."""
    prepared = prepare_metric_snapshots(snapshots)
    if not prepared:
        return {"max_drawdown_pct": 0, "volatilite_annualisee_pct": 0, "hhi": 0, "sharpe": 0,
                "sortino": None, "n_positions": 0, "concentration": "inconnu"}

    observations = return_observations(prepared, prepared=True)
    rets = daily_returns_for_risk(observations)
    wealth = adjusted_wealth_index(observations)

    # Les rendements sont calendaires après normalisation des dates : 365,25
    # remplace le multiplicateur 252 réservé à une série de séances de marché.
    periods_per_year = 365.25
    mdd = compute_max_drawdown(wealth)
    vol = compute_volatility(rendements=rets, periods_per_year=periods_per_year)
    # Un ratio annualisé sur quelques jours est numériquement calculable mais
    # statistiquement trompeur. Un mois calendaire est le minimum publié.
    if len(rets) >= 30:
        sharpe = compute_sharpe(rets, periods_per_year=periods_per_year)
        sortino = compute_sortino(rets, periods_per_year=periods_per_year)
    else:
        sharpe = None
        sortino = None

    # HHI économique : les lignes du même titre sont d'abord regroupées et les
    # ETF actions larges sont regardés au travers de leur diversification.
    hhi = compute_portfolio_hhi(positions, diversified_tickers)

    if not any(float(position.get("valeur_actuelle", 0) or 0) > 0 for position in positions):
        concentration = "inconnu"
    else:
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
        {
            "valeur": p.get("valeur_actuelle", 0),
            "secteur": secteur_par_ticker.get(p["ticker"], "Inconnu"),
        }
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
            contributions.append(
                {
                    "label": p.get("devise") or "Inconnu",
                    "ticker": p["ticker"],
                    "valeur": valeur,
                }
            )
            continue
        frac = frac_by_ticker.get(p["ticker"])
        if frac:
            for label, fraction in frac.items():
                contributions.append(
                    {
                        "label": label,
                        "ticker": p["ticker"],
                        "valeur": valeur * fraction,
                    }
                )
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
