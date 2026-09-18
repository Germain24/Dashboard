"""Budget de voyage finançable en chaînant les cartes de crédit actives."""

import datetime as dt

from app.models.credit import CreditAccount
from app.services.finance.credit.voyage_budget import compute_voyage_budget


def _account(limite, institution="Desjardins", produit="Carte Mastercard", statut="actif"):
    return CreditAccount(
        institution=institution, produit=produit, limite_actuelle=limite,
        date_ouverture=dt.date(2025, 9, 1), statut=statut,
    )


def test_example_from_user_15000_5000_3000():
    accounts = [_account(15000, "A"), _account(5000, "B"), _account(3000, "C")]
    out = compute_voyage_budget(accounts)
    assert out["budget_total"] == 23000.0
    assert out["mois_total"] == 3
    assert [m["budget"] for m in out["mois"]] == [15000.0, 5000.0, 3000.0]
    assert [m["mois"] for m in out["mois"]] == [1, 2, 3]


def test_default_order_is_largest_card_first():
    accounts = [_account(3000, "C"), _account(15000, "A"), _account(5000, "B")]
    out = compute_voyage_budget(accounts)
    assert [m["institution"] for m in out["mois"]] == ["A", "B", "C"]


def test_ascending_order_option():
    accounts = [_account(15000, "A"), _account(5000, "B"), _account(3000, "C")]
    out = compute_voyage_budget(accounts, ordre="asc")
    assert [m["budget"] for m in out["mois"]] == [3000.0, 5000.0, 15000.0]


def test_closed_accounts_excluded():
    accounts = [_account(15000, "A", statut="actif"), _account(5000, "B", statut="ferme")]
    out = compute_voyage_budget(accounts)
    assert out["budget_total"] == 15000.0
    assert out["mois_total"] == 1


def test_zero_limit_accounts_excluded():
    accounts = [_account(0, "A"), _account(1000, "B")]
    out = compute_voyage_budget(accounts)
    assert out["mois_total"] == 1
    assert out["budget_total"] == 1000.0


def test_no_active_accounts_returns_empty():
    out = compute_voyage_budget([])
    assert out == {"mois": [], "budget_total": 0.0, "mois_total": 0}
