"""Tests TDD — ratio de Sortino (#5.1).

Sortino = Sharpe qui ne penalise que la volatilite baissiere : seuls les
rendements sous le MAR (taux sans risque) entrent dans le denominateur.
"""

from __future__ import annotations

import math

from app.services.finance.risk import (
    compute_sharpe,
    compute_sortino,
    get_risk_metrics,
)


def test_compute_sortino_known_series():
    """Serie calculee a la main, MAR = 0 (taux sans risque nul).

    rendements = [+2 %, -1 %, +3 %, -2 %, +1 %] -> moyenne = 0.6 %/jour.
    Seuls -1 % et -2 % sont sous le MAR : deviation baissiere =
    sqrt((0.01^2 + 0.02^2) / (5 - 1)) = sqrt(0.000125) = 0.01118034.
    Annualisation arithmétique standard : moyenne * sqrt(252) / deviation.
    """
    rends = [0.02, -0.01, 0.03, -0.02, 0.01]

    dd_ann = math.sqrt((0.01 ** 2 + 0.02 ** 2) / 4) * math.sqrt(252)
    expected = round(0.006 * 252 / dd_ann, 3)

    assert compute_sortino(rends, taux_sans_risque=0.0) == expected
    # Garde-fou d'ordre de grandeur (vérifié à la main) : ~8,52.
    assert 8.0 < expected < 9.0


def test_compute_sortino_no_downside_returns_none():
    """Aucun rendement sous le MAR -> ratio mathematiquement infini.

    Convention retenue : None (« non defini »), jamais 0.0 qui se lirait comme
    « mauvais » alors que la serie n'a justement subi aucune baisse.
    """
    rends = [0.01, 0.02, 0.015, 0.03]
    assert compute_sortino(rends, taux_sans_risque=0.0) is None


def test_compute_sortino_greater_than_sharpe_when_downside_is_small():
    """Propriete definitionnelle : une serie dont la baisse est faible devant la
    volatilite totale (gros gains, petites pertes) a un Sortino > Sharpe."""
    rends = [0.05, -0.005, 0.06, -0.004, 0.05, -0.006, 0.04, -0.005]

    sharpe = compute_sharpe(rends)
    sortino = compute_sortino(rends)

    assert sortino is not None
    assert sortino > sharpe


def test_compute_sortino_too_few_points():
    """Meme garde que compute_sharpe : moins de 2 points -> 0.0."""
    assert compute_sortino([]) == 0.0
    assert compute_sortino([0.01]) == 0.0


def test_get_risk_metrics_exposes_sortino():
    snaps = [
        {"date": "2026-01-01", "valeur": 1000.0, "investit": 1000.0},
        {"date": "2026-01-02", "valeur": 1020.0, "investit": 1000.0},
        {"date": "2026-01-03", "valeur": 1010.0, "investit": 1000.0},
        {"date": "2026-01-04", "valeur": 1040.0, "investit": 1000.0},
    ]
    m = get_risk_metrics(snaps, [])
    assert "sortino" in m


def test_get_risk_metrics_insufficient_data_branch_has_sortino():
    """La branche « pas de valeurs » doit exposer la meme cle que la normale,
    sinon RiskMetricsOut perd le champ selon l'etat de la base."""
    m = get_risk_metrics([], [])
    assert "sortino" in m
