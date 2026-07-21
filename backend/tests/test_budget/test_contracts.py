"""Tests suivi manuel des abonnements/contrats (#362)."""

import pytest

from app.services.budget.contracts import (
    classify_echeance,
    monthly_cost,
    upcoming_renewals,
    list_contracts,
    add_contract,
    update_contract,
    remove_contract,
)


# ── Fonctions pures ──────────────────────────────────────────────────────────

def test_classify_no_date():
    assert classify_echeance(None, "2026-07-16") == "no_date"


def test_classify_depassee():
    assert classify_echeance("2026-07-15", "2026-07-16") == "depassee"


def test_classify_proche_same_day():
    assert classify_echeance("2026-07-16", "2026-07-16") == "proche"


def test_classify_proche_within_30_days():
    assert classify_echeance("2026-08-10", "2026-07-16") == "proche"


def test_classify_ok():
    assert classify_echeance("2026-12-01", "2026-07-16") == "ok"


def test_monthly_cost_mensuel_only():
    contracts = [
        {"montant": 20.0, "periodicite": "mensuel", "statut": "actif"},
        {"montant": 30.0, "periodicite": "mensuel", "statut": "actif"},
    ]
    assert monthly_cost(contracts) == 50.0


def test_monthly_cost_annuel_converted():
    contracts = [{"montant": 120.0, "periodicite": "annuel", "statut": "actif"}]
    assert monthly_cost(contracts) == 10.0


def test_monthly_cost_ignores_resilie():
    contracts = [
        {"montant": 50.0, "periodicite": "mensuel", "statut": "actif"},
        {"montant": 999.0, "periodicite": "mensuel", "statut": "resilie"},
    ]
    assert monthly_cost(contracts) == 50.0


def test_monthly_cost_rounding():
    contracts = [{"montant": 100.0, "periodicite": "annuel", "statut": "actif"}]
    assert monthly_cost(contracts) == pytest.approx(8.33, abs=0.01)


def test_upcoming_renewals_filters_and_sorts():
    today = "2026-07-16"
    contracts = [
        {"id": 1, "nom": "A", "date_echeance": "2026-12-01", "statut": "actif"},  # ok, exclu
        {"id": 2, "nom": "B", "date_echeance": "2026-07-20", "statut": "actif"},  # proche
        {"id": 3, "nom": "C", "date_echeance": "2026-07-01", "statut": "actif"},  # depassee
        {"id": 4, "nom": "D", "date_echeance": "2026-07-18", "statut": "resilie"},  # exclu (resilie)
        {"id": 5, "nom": "E", "date_echeance": None, "statut": "actif"},  # no_date, exclu
    ]
    result = upcoming_renewals(contracts, today)
    assert [c["id"] for c in result] == [3, 2]


def test_upcoming_renewals_none_dates_last():
    today = "2026-07-16"
    contracts = [
        {"id": 1, "nom": "A", "date_echeance": "2026-07-10", "statut": "actif"},
    ]
    result = upcoming_renewals(contracts, today)
    assert len(result) == 1


# ── Fonctions avec store JSON ────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path):
    return tmp_path / "budget_contracts.json"


def test_list_empty(store):
    assert list_contracts(path=store) == []


def test_add_contract(store):
    c = add_contract("Assurance auto", "assurance", 80.0, "mensuel", path=store)
    assert c["nom"] == "Assurance auto"
    assert c["categorie"] == "assurance"
    assert c["montant"] == 80.0
    assert c["periodicite"] == "mensuel"
    assert c["statut"] == "actif"
    assert c["date_echeance"] is None
    assert c["date_resiliation"] is None
    assert c["notes"] == ""
    assert c["id"] >= 1


def test_add_contract_with_echeance(store):
    c = add_contract(
        "Box internet", "telecom", 45.0, "mensuel",
        date_echeance="2026-09-01", notes="engagement 24 mois", path=store,
    )
    assert c["date_echeance"] == "2026-09-01"
    assert c["notes"] == "engagement 24 mois"


def test_list_persists(store):
    add_contract("Salle de sport", "abonnement", 30.0, "mensuel", path=store)
    add_contract("Assurance habitation", "assurance", 200.0, "annuel", path=store)
    items = list_contracts(path=store)
    assert len(items) == 2
    assert {i["nom"] for i in items} == {"Salle de sport", "Assurance habitation"}


def test_update_contract(store):
    c = add_contract("Netflix", "abonnement", 15.0, "mensuel", path=store)
    updated = update_contract(c["id"], {"montant": 18.0}, path=store)
    assert updated is not None
    assert updated["montant"] == 18.0
    assert updated["nom"] == "Netflix"


def test_update_contract_resiliation(store):
    c = add_contract("Gym", "abonnement", 40.0, "mensuel", path=store)
    updated = update_contract(
        c["id"], {"statut": "resilie", "date_resiliation": "2026-07-16"}, path=store,
    )
    assert updated["statut"] == "resilie"
    assert updated["date_resiliation"] == "2026-07-16"


def test_update_nonexistent(store):
    assert update_contract(999, {"montant": 5}, path=store) is None


def test_remove_contract(store):
    c = add_contract("Assurance vie", "assurance", 60.0, "mensuel", path=store)
    assert remove_contract(c["id"], path=store) is True
    assert list_contracts(path=store) == []


def test_remove_nonexistent(store):
    assert remove_contract(999, path=store) is False
