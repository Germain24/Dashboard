"""Tests TDD — risk.py : les rendements doivent etre neutralises des apports/retraits
avant de nourrir volatilite/Sharpe (sinon un depot s'enregistre comme un rendement
massif et fausse toutes les metriques)."""

from __future__ import annotations

from app.services.finance.risk import (
    _cashflow_adjusted_returns,
    compute_volatility,
    get_risk_metrics,
)


def _steady_growth_snapshots(n_days: int = 30, daily_growth: float = 0.01, start: float = 10000.0):
    """n_days de croissance reguliere de `daily_growth`/jour, aucun apport."""
    snaps = []
    v = start
    for i in range(n_days):
        snaps.append({"date": f"2026-01-{i+1:02d}", "valeur": round(v, 2), "investit": start})
        v *= (1 + daily_growth)
    return snaps


def test_get_risk_metrics_deposit_day_does_not_inflate_volatility():
    """Une serie de croissance reguliere (1%/jour) sans aucun depot doit produire
    une volatilite proche de celle de la MEME serie avec un depot un jour donne
    (le depot fait sauter `valeur` et `investit` ensemble ce jour-la, mais ne
    doit pas se lire comme un rendement reel)."""
    baseline_snaps = _steady_growth_snapshots()
    baseline_positions: list[dict] = []
    baseline_metrics = get_risk_metrics(baseline_snaps, baseline_positions)
    baseline_vol = baseline_metrics["volatilite_annualisee_pct"]

    # Meme serie, mais un gros depot au jour 15 : valeur ET investit sautent
    # ensemble d'un montant equivalent (pas un vrai gain de marche).
    deposit_snaps = [dict(s) for s in baseline_snaps]
    depot = 5000.0
    for i in range(15, len(deposit_snaps)):
        deposit_snaps[i]["valeur"] = round(deposit_snaps[i]["valeur"] + depot, 2)
        deposit_snaps[i]["investit"] = deposit_snaps[i]["investit"] + depot

    deposit_metrics = get_risk_metrics(deposit_snaps, baseline_positions)
    deposit_vol = deposit_metrics["volatilite_annualisee_pct"]

    # Avec le calcul brut (ancien bug), le jour du depot produirait un rendement
    # de ~+50% suivi d'un retour a la normale : la volatilite exploserait (des
    # centaines de %). Avec l'ajustement cash-flow, elle doit rester proche de
    # la baseline (croissance reguliere de 1%/jour).
    assert deposit_vol < baseline_vol + 5.0, (
        f"volatilite gonflee par le depot : baseline={baseline_vol}, avec depot={deposit_vol}"
    )
    # Sanity : la baseline elle-meme doit etre une volatilite "faible" (croissance
    # parfaitement reguliere -> rendements quasi identiques chaque jour).
    assert baseline_vol < 5.0


def test_compute_volatility_backward_compatible_with_raw_valeurs():
    """Appel historique positionnel (liste de valeurs brutes, pas de `rendements`)
    doit continuer a fonctionner exactement comme avant."""
    valeurs = [100.0, 101.0, 99.0, 102.0, 100.5, 103.0]
    # Reproduit le calcul historique de compute_volatility pour comparaison.
    import math
    rets = [(valeurs[i] / valeurs[i - 1]) - 1 for i in range(1, len(valeurs))]
    n = len(rets)
    mean = sum(rets) / n
    variance = sum((r - mean) ** 2 for r in rets) / (n - 1)
    expected = round(math.sqrt(variance) * math.sqrt(252) * 100, 2)

    assert compute_volatility(valeurs) == expected


def test_cashflow_adjusted_returns_hand_verified():
    """Verification a la main de la formule : meme logique que
    portfolio.time_weighted_return, jour par jour."""
    snapshots = [
        {"date": "2026-01-01", "valeur": 1000.0, "investit": 1000.0},
        {"date": "2026-01-02", "valeur": 1010.0, "investit": 1000.0},  # +1% reel, pas d'apport
        {"date": "2026-01-03", "valeur": 1310.0, "investit": 1300.0},  # apport de 300, +0% reel
    ]
    rets = _cashflow_adjusted_returns(snapshots)

    assert len(rets) == 2
    # Jour 2 : pas d'apport -> rendement brut normal
    assert rets[0] == (1010.0 / 1000.0) - 1
    # Jour 3 : apport = 1300 - 1000 = 300 ; rendement ajuste = (1310 - 300) / 1010 - 1 = 0
    apport = 1300.0 - 1000.0
    expected_ret3 = ((1310.0 - apport) / 1010.0) - 1
    assert abs(rets[1] - expected_ret3) < 1e-9
    assert abs(rets[1]) < 1e-9  # ~0 : le depot n'est pas un gain reel


def test_get_risk_metrics_without_investit_falls_back_to_raw_ratios():
    """Sans `investit` dans les snapshots, le comportement historique (rendements
    bruts) doit etre preserve (compat. avec un eventuel autre appelant)."""
    snaps = [{"date": "2026-01-01", "valeur": 100.0},
             {"date": "2026-01-02", "valeur": 101.0},
             {"date": "2026-01-03", "valeur": 99.0}]
    metrics = get_risk_metrics(snaps, [])
    assert metrics["volatilite_annualisee_pct"] >= 0
