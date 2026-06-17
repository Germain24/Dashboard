import datetime as dt
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction
from app.services.budget.rules import (
    apply_rules_pure,
    learn_rules,
    suggest_rules_from_history,
)


def _tx(marchand, category_id):
    return SimpleNamespace(marchand=marchand, description="", category_id=category_id)


def test_no_match():
    rules = [{"pattern": "STARBUCKS", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("METRO GROCERY", rules) is None


def test_match_case_insensitive():
    rules = [{"pattern": "starbucks", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("STARBUCKS #42", rules) == 1


def test_priority_order():
    rules = [
        {"pattern": "METRO", "category_id": 2, "priorite": 0},
        {"pattern": "METRO", "category_id": 1, "priorite": 10},
    ]
    assert apply_rules_pure("METRO", rules) == 1


# ─── Règles apprenables (#258) ───────────────────────────────────────────────

def test_suggest_learns_from_repeated_pure_merchant():
    txs = [
        _tx("METRO INC", 1), _tx("METRO #123", 1), _tx("METRO PLATEAU", 1),
        _tx("UNIQUE SHOP", 2),  # une seule occurrence → pas de règle
    ]
    out = suggest_rules_from_history(txs, [], min_occurrences=3)
    assert out == [{"pattern": "METRO", "category_id": 1, "occurrences": 3}]


def test_suggest_skips_merchant_with_conflicting_categories():
    txs = [_tx("AMAZON", 1), _tx("AMAZON", 1), _tx("AMAZON", 2)]  # catégories mélangées
    assert suggest_rules_from_history(txs, [], min_occurrences=2) == []


def test_suggest_skips_already_covered_by_existing_rule():
    txs = [_tx("METRO INC", 1), _tx("METRO #1", 1), _tx("METRO #2", 1)]
    existing = [{"pattern": "METRO", "category_id": 1, "priorite": 0}]
    assert suggest_rules_from_history(txs, existing, min_occurrences=3) == []


def test_suggest_ignores_uncategorised():
    txs = [_tx("METRO", None), _tx("METRO", None), _tx("METRO", None)]
    assert suggest_rules_from_history(txs, [], min_occurrences=2) == []


@pytest.fixture()
def session():
    e = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(e)
    with Session(e) as s:
        yield s


def test_learn_rules_apply_creates_and_recategorises(session):
    cat = BudgetCategory(nom="Épicerie")
    session.add(cat); session.commit(); session.refresh(cat)
    for m in ("METRO INC", "METRO #5", "METRO PLATEAU"):
        session.add(BudgetTransaction(date=dt.date(2026, 6, 1), montant=-10, marchand=m, category_id=cat.id))
    # transaction non catégorisée du même marchand → doit être rattrapée par la règle apprise
    session.add(BudgetTransaction(date=dt.date(2026, 6, 2), montant=-12, marchand="METRO CENTRE", category_id=None))
    session.commit()

    preview = learn_rules(session, min_occurrences=3, apply=False)
    assert preview["created"] == 0
    assert preview["suggestions"][0]["pattern"] == "METRO"
    assert preview["suggestions"][0]["category_nom"] == "Épicerie"

    applied = learn_rules(session, min_occurrences=3, apply=True)
    assert applied["created"] == 1
    rules = session.exec(select(BudgetRule)).all()
    assert any(r.pattern == "METRO" and r.category_id == cat.id for r in rules)
    # la transaction non catégorisée a été rattrapée par la règle apprise
    rattrapee = session.exec(
        select(BudgetTransaction).where(BudgetTransaction.marchand == "METRO CENTRE")
    ).first()
    assert rattrapee.category_id == cat.id
