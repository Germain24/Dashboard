"""Planner marge de crédit v2 : simulation par seuils de score."""

import datetime as dt

from app.models.credit import CreditAccount, CreditActionRule, CreditScoreEntry
from app.services.finance.credit.planner import build_plan


def _account(limite=700, statut="actif"):
    return CreditAccount(
        institution="Desjardins", produit="Carte Mastercard", limite_actuelle=limite,
        date_ouverture=dt.date(2025, 9, 1), statut=statut,
    )


def test_less_than_two_score_points_returns_no_projection():
    plan = build_plan([_account()], [], [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["projection_possible"] is False
    assert plan["projection_score"] == []
    assert plan["projection_marge"] == []
    assert plan["actions"] == []
    assert plan["historique_marge"] == [{"date": dt.date(2026, 7, 1), "marge_totale": 700.0}]

    one_score = [CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x")]
    plan2 = build_plan([_account()], one_score, [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan2["projection_possible"] is False


def test_closed_accounts_excluded_from_marge_actuelle():
    accounts = [_account(limite=700, statut="actif"), _account(limite=5000, statut="ferme")]
    plan = build_plan(accounts, [], [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["marge_actuelle"] == 700.0


def test_no_rules_defined_still_projects_score_and_margin():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x"),
        CreditScoreEntry(date=dt.date(2026, 7, 1), score=680, source="y"),
    ]
    plan = build_plan([_account()], scores, [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["actions"] == []
    assert plan["projection_possible"] is True
    assert len(plan["projection_score"]) == 3  # juillet, août, septembre 2026
    assert plan["projection_marge"][-1]["marge_totale"] == 700.0  # jamais modifiée sans règle


def test_single_rule_triggers_at_correct_month_and_updates_margin_and_score():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x"),
        CreditScoreEntry(date=dt.date(2026, 7, 1), score=680, source="y"),
    ]
    # pente = (680-650)/6 = 5 pts/mois. Juillet: 685 (pas de trigger). Août: 690 (trigger).
    rules = [CreditActionRule(seuil_score=690, type="hausse", montant_estime=1000)]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))

    assert plan["actions"] == [
        {"date": dt.date(2026, 8, 1), "type": "hausse", "seuil_score": 690, "montant_estime": 1000.0},
    ]
    aout = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 8, 1))
    assert aout["marge_totale"] == 1700.0  # 700 + 1000
    aout_score = next(p for p in plan["projection_score"] if p["date"] == dt.date(2026, 8, 1))
    assert aout_score["score"] == 680.0  # 690 - 10 (impact de l'action)
    sept = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 9, 1))
    assert sept["marge_totale"] == 1700.0  # règle déjà consommée, ne se redéclenche pas


def test_multiple_rules_can_trigger_same_month_when_score_jumps_fast():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=600, source="x"),
        CreditScoreEntry(date=dt.date(2026, 3, 1), score=700, source="y"),
    ]
    # pente = (700-600)/2 = 50 pts/mois. Mars: 700+50=750 -> franchit 720 ET 740 le même mois.
    rules = [
        CreditActionRule(seuil_score=720, type="hausse", montant_estime=500),
        CreditActionRule(seuil_score=740, type="nouvelle_carte", montant_estime=1000),
    ]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 4, 1), today=dt.date(2026, 3, 1))

    assert [a["seuil_score"] for a in plan["actions"]] == [720, 740]
    assert all(a["date"] == dt.date(2026, 3, 1) for a in plan["actions"])
    mars = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 3, 1))
    assert mars["marge_totale"] == 2200.0  # 700 + 500 + 1000


def test_rules_consumed_in_ascending_threshold_order_regardless_of_input_order():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=600, source="x"),
        CreditScoreEntry(date=dt.date(2026, 3, 1), score=700, source="y"),
    ]
    rules = [
        CreditActionRule(seuil_score=740, type="nouvelle_carte", montant_estime=1000),
        CreditActionRule(seuil_score=720, type="hausse", montant_estime=500),
    ]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 4, 1), today=dt.date(2026, 3, 1))
    assert [a["seuil_score"] for a in plan["actions"]] == [720, 740]
