"""Rapport d'indépendance financière (FIRE) : taux d'épargne + années restantes (#268)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services.budget.fire import fire_projection, fire_report, savings_rate


# ── Taux d'épargne ───────────────────────────────────────────────────────────

def test_taux_epargne_nominal():
    assert savings_rate(4000.0, 3000.0) == 25.0


def test_taux_epargne_sans_revenus():
    assert savings_rate(0.0, 500.0) == 0.0


def test_taux_epargne_negatif_quand_on_depense_plus_que_ses_revenus():
    assert savings_rate(1000.0, 1500.0) == -50.0


# ── Projection FIRE ──────────────────────────────────────────────────────────

def test_objectif_fi_est_l_inverse_du_taux_de_retrait():
    out = fire_projection(0.0, 10000.0, 30000.0)
    assert out["objectif_fi"] == 750000.0        # 30 000 / 4 % = 25×
    assert out["taux_retrait_pct"] == 4.0


def test_taux_de_retrait_configurable():
    out = fire_projection(0.0, 10000.0, 30000.0, taux_retrait=0.03)
    assert out["objectif_fi"] == 1000000.0       # 30 000 / 3 %


def test_annees_restantes_sans_rendement_est_une_simple_division():
    out = fire_projection(0.0, 30000.0, 30000.0, rendement_reel=0.0)
    assert out["annees_restantes"] == 25.0       # 750 000 / 30 000
    assert out["atteint"] is False
    assert out["taux_epargne_pct"] == 50.0


def test_annees_restantes_avec_rendement_compose():
    out = fire_projection(100000.0, 20000.0, 30000.0, rendement_reel=0.05)
    assert out["annees_restantes"] is not None
    assert 17.0 <= out["annees_restantes"] <= 18.0
    assert out["progression_pct"] == round(100000 / 750000 * 100, 1)


def test_deja_independant_financierement():
    out = fire_projection(1000000.0, 20000.0, 30000.0)
    assert out["atteint"] is True
    assert out["annees_restantes"] == 0.0


def test_depenses_nulles_signifient_independance_immediate():
    out = fire_projection(0.0, 1000.0, 0.0)
    assert out["objectif_fi"] == 0.0
    assert out["atteint"] is True
    assert out["annees_restantes"] == 0.0


def test_epargne_nulle_ne_converge_jamais():
    out = fire_projection(0.0, 0.0, 30000.0)
    assert out["annees_restantes"] is None
    assert out["atteint"] is False


def test_epargne_negative_ne_boucle_pas_indefiniment():
    out = fire_projection(10000.0, -500.0, 30000.0)
    assert out["annees_restantes"] is None
    assert out["taux_epargne_pct"] < 0


def test_horizon_borne_la_projection():
    # 17 ans nécessaires, horizon volontairement plus court → pas de réponse.
    out = fire_projection(100000.0, 20000.0, 30000.0, rendement_reel=0.05, horizon_max=5)
    assert out["annees_restantes"] is None
    assert out["horizon_max"] == 5


# ── Wrapper DB ───────────────────────────────────────────────────────────────

@pytest.fixture
def _donnees(mem_session):
    from app.models.budget import BudgetTransaction
    from app.models.patrimoine import PatrimoineItem

    # 12 mois à 4 000 de revenus / 3 000 de dépenses (CAD).
    for i in range(12):
        y, m = (2025, 8 + i) if 8 + i <= 12 else (2026, 8 + i - 12)
        mem_session.add(BudgetTransaction(date=dt.date(y, m, 1), montant=4000.0, marchand="Paie"))
        mem_session.add(BudgetTransaction(date=dt.date(y, m, 2), montant=-3000.0, marchand="Vie"))
    mem_session.add(PatrimoineItem(type="actif", label="Bourse Direct", valeur=50000.0, devise="EUR"))
    mem_session.commit()
    return mem_session


def test_fire_report_combine_budget_et_patrimoine(_donnees):
    out = fire_report(_donnees, months=12, cad_eur=0.5, today=dt.date(2026, 7, 20))
    # Budget converti en EUR (taux injecté 0,5) : 48 000 CAD → 24 000 € de revenus.
    assert out["revenus_annuels"] == 24000.0
    assert out["depenses_annuelles"] == 18000.0
    assert out["epargne_annuelle"] == 6000.0
    assert out["taux_epargne_pct"] == 25.0
    assert out["patrimoine_net"] == 50000.0
    assert out["objectif_fi"] == 450000.0        # 18 000 / 4 %
    assert out["devise"] == "EUR"
    assert out["annees_restantes"] is not None


def test_fire_report_sans_donnees(mem_session):
    out = fire_report(mem_session, months=12, cad_eur=0.5, today=dt.date(2026, 7, 20))
    assert out["depenses_annuelles"] == 0.0
    assert out["atteint"] is True                # objectif nul : rien à financer
    assert out["annees_restantes"] == 0.0
