"""Repositories du module Budget."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.budget import (
    BudgetCategory, BudgetEnvelope, BudgetRule, BudgetTransaction,
)


class BudgetCategoryRepository(Repository[BudgetCategory]):
    model = BudgetCategory


class BudgetRuleRepository(Repository[BudgetRule]):
    model = BudgetRule


class BudgetTransactionRepository(Repository[BudgetTransaction]):
    model = BudgetTransaction


class BudgetEnvelopeRepository(Repository[BudgetEnvelope]):
    model = BudgetEnvelope
