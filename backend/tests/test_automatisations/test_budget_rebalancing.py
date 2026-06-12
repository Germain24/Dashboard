"""Tests TDD pour le rééquilibrage budgétaire auto en fin de mois (#211)."""
import datetime as dt
import pytest
from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.scheduler import Notification
from app.services.automatisations.budget_rebalancing import (
    compute_rebalancing,
    run_monthly_rebalancing,
)


# ─── Fonctions pures ─────────────────────────────────────────────────────────

class TestComputeRebalancing:
    def test_over_spent_category_flagged(self):
        statuts = [
            {"category_id": 1, "budget": 200.0, "depense": 250.0, "reste": -50.0, "pct": 125.0, "status": "over"},
            {"category_id": 2, "budget": 100.0, "depense": 60.0, "reste": 40.0, "pct": 60.0, "status": "ok"},
        ]
        result = compute_rebalancing(statuts)
        over = [r for r in result if r["action"] == "over"]
        under = [r for r in result if r["action"] == "under"]
        assert len(over) == 1
        assert over[0]["category_id"] == 1
        assert len(under) == 1
        assert under[0]["category_id"] == 2

    def test_all_on_budget_returns_empty(self):
        statuts = [
            {"category_id": 1, "budget": 200.0, "depense": 190.0, "reste": 10.0, "pct": 95.0, "status": "warning"},
        ]
        result = compute_rebalancing(statuts)
        assert result == []

    def test_no_budget_category_skipped(self):
        statuts = [
            {"category_id": 1, "budget": 0.0, "depense": 50.0, "reste": -50.0, "pct": 0.0, "status": "ok"},
        ]
        result = compute_rebalancing(statuts)
        assert result == []

    def test_under_threshold_ignored(self):
        statuts = [
            {"category_id": 1, "budget": 200.0, "depense": 30.0, "reste": 170.0, "pct": 15.0, "status": "ok"},
        ]
        result = compute_rebalancing(statuts)
        assert result == []


# ─── Intégration DB ──────────────────────────────────────────────────────────

class TestRunMonthlyRebalancing:
    def test_creates_notification_for_over_budget(self, mem_session):
        from app.models.budget import BudgetEnvelope, BudgetTransaction, BudgetCategory
        cat = BudgetCategory(nom="Restauration", couleur="#FF0000")
        mem_session.add(cat)
        mem_session.commit()
        mem_session.refresh(cat)

        mois = "2026-06"
        env = BudgetEnvelope(category_id=cat.id, mois=mois, montant=100.0)
        mem_session.add(env)
        # Dépense > budget
        tx = BudgetTransaction(
            date=dt.date(2026, 6, 15),
            montant=-150.0,
            marchand="Restaurant",
            category_id=cat.id,
        )
        mem_session.add(tx)
        mem_session.commit()

        run_monthly_rebalancing(mem_session, mois=mois)
        notifs = list(mem_session.exec(select(Notification)).all())
        assert any("Restauration" in n.message or "budget" in n.titre.lower() for n in notifs)

    def test_no_notification_when_balanced(self, mem_session):
        run_monthly_rebalancing(mem_session, mois="2026-06")
        notifs = list(mem_session.exec(select(Notification)).all())
        assert notifs == []

    def test_suggests_next_month_envelope_update(self, mem_session):
        from app.models.budget import BudgetEnvelope, BudgetTransaction, BudgetCategory
        cat = BudgetCategory(nom="Épicerie", couleur="#00FF00")
        mem_session.add(cat)
        mem_session.commit()
        mem_session.refresh(cat)

        mois = "2026-06"
        env = BudgetEnvelope(category_id=cat.id, mois=mois, montant=300.0)
        mem_session.add(env)
        tx = BudgetTransaction(
            date=dt.date(2026, 6, 20),
            montant=-350.0,
            marchand="Metro",
            category_id=cat.id,
        )
        mem_session.add(tx)
        mem_session.commit()

        suggestions = run_monthly_rebalancing(mem_session, mois=mois)
        assert any(s.get("action") == "over" for s in suggestions)
