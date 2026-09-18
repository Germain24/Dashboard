import datetime as dt

from app.api.budget.schemas import TransactionCategoryUpdate
from app.api.budget.transactions import update_transaction_category
from app.models.budget import BudgetCategory, BudgetTransaction


def test_transaction_category_can_be_assigned_and_cleared(mem_session):
    category = BudgetCategory(nom="Salaire")
    transaction = BudgetTransaction(date=dt.date(2026, 9, 1), montant=2500, marchand="Paie")
    mem_session.add(category)
    mem_session.add(transaction)
    mem_session.commit()

    assigned = update_transaction_category(
        transaction.id,
        TransactionCategoryUpdate(category_id=category.id),
        mem_session,
    )
    assert assigned.category_id == category.id

    cleared = update_transaction_category(
        transaction.id,
        TransactionCategoryUpdate(category_id=None),
        mem_session,
    )
    assert cleared.category_id is None
