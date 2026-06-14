"""Tests — comparaison budget mois vs mois précédent (#229)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.services.budget.transactions import (
    _previous_month,
    create_transaction,
    get_monthly_comparison,
)


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/b.db", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_previous_month_wraps_january():
    assert _previous_month("2026-01") == "2025-12"
    assert _previous_month("2026-06") == "2026-05"


def test_comparison_computes_deltas(session):
    # Mois précédent (mai) : 100 de dépenses ; mois courant (juin) : 80.
    create_transaction(session, dt.date(2026, 5, 10), -100.0, "Mai")
    create_transaction(session, dt.date(2026, 6, 10), -80.0, "Juin")
    create_transaction(session, dt.date(2026, 6, 1), 2000.0, "Salaire juin")

    comp = get_monthly_comparison(session, "2026-06")
    assert comp["mois_precedent"] == "2026-05"
    # Dépenses : -80 vs -100 -> delta +20, hausse de 20 % (sur |précédent|).
    dep = comp["depenses"]
    assert dep["current"] == -80.0
    assert dep["previous"] == -100.0
    assert dep["delta"] == 20.0
    assert dep["direction"] == "up"
    # Revenus : 2000 ce mois vs 0 le mois dernier -> pct indéfini.
    assert comp["revenus"]["delta_pct"] is None
