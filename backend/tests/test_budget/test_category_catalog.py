from sqlmodel import select

import datetime as dt

from app.models.budget import BudgetCategory, BudgetEnvelope, BudgetTransaction
from app.services.budget.categories import seed_categories


def test_seed_categories_includes_broad_expense_and_income_subcategories(mem_session):
    seed_categories(mem_session)
    categories = mem_session.exec(select(BudgetCategory)).all()
    by_name = {category.nom: category for category in categories}

    assert len(categories) >= 100
    assert by_name["Logement"].parent_id == by_name["Dépenses"].id
    assert by_name["Loyer"].parent_id == by_name["Logement"].id
    assert by_name["Bourse"].parent_id == by_name["Investissements & épargne"].id
    assert by_name["PEA"].parent_id == by_name["Bourse"].id
    assert by_name["Bourse Direct"].parent_id == by_name["PEA"].id
    assert by_name["CELI"].parent_id == by_name["Comptes enregistrés"].id
    assert by_name["Salaire"].parent_id == by_name["Travail"].id
    assert by_name["Dividendes"].parent_id == by_name["Revenus de placements"].id
    assert by_name["Cinéma"].parent_id == by_name["Culture"].id
    assert by_name["Sorties"].parent_id == by_name["Divertissement"].id


def test_seed_reorganizes_legacy_categories_without_changing_references(mem_session):
    expenses = BudgetCategory(nom="Logement")
    leisure = BudgetCategory(nom="Loisirs")
    investments = BudgetCategory(nom="Investissements & épargne")
    income = BudgetCategory(nom="Revenus")
    mem_session.add_all([expenses, leisure, investments, income])
    mem_session.commit()
    mem_session.refresh(expenses)
    mem_session.refresh(leisure)
    mem_session.refresh(investments)
    mem_session.refresh(income)

    placements = BudgetCategory(nom="Placements", parent_id=investments.id)
    salary = BudgetCategory(nom="Salaire", parent_id=income.id)
    cinema = BudgetCategory(nom="Cinéma", parent_id=leisure.id)
    outing = BudgetCategory(nom="Sorties", parent_id=leisure.id)
    mem_session.add_all([placements, salary, cinema, outing])
    mem_session.commit()
    mem_session.refresh(expenses)
    mem_session.refresh(placements)
    mem_session.refresh(salary)
    mem_session.refresh(cinema)
    mem_session.refresh(outing)

    transaction = BudgetTransaction(
        date=dt.date(2026, 9, 1),
        montant=-125.0,
        marchand="Loyer",
        category_id=expenses.id,
    )
    mem_session.add(transaction)
    mem_session.add(
        BudgetEnvelope(category_id=expenses.id, mois="2026-09", montant=900.0)
    )
    mem_session.commit()
    original_category_ids = (expenses.id, placements.id, salary.id, cinema.id, outing.id)

    seed_categories(mem_session)
    first_count = len(mem_session.exec(select(BudgetCategory)).all())
    seed_categories(mem_session)

    categories = mem_session.exec(select(BudgetCategory)).all()
    by_name = {category.nom: category for category in categories}
    assert len(categories) == first_count
    assert (
        by_name["Logement"].id,
        by_name["Placements"].id,
        by_name["Salaire"].id,
        by_name["Cinéma"].id,
        by_name["Sorties"].id,
    ) == original_category_ids
    assert by_name["Logement"].parent_id == by_name["Dépenses"].id
    assert by_name["Placements"].parent_id == by_name["Bourse"].id
    assert by_name["Salaire"].parent_id == by_name["Travail"].id
    assert by_name["Cinéma"].parent_id == by_name["Culture"].id
    assert by_name["Sorties"].parent_id == by_name["Divertissement"].id
    assert mem_session.get(BudgetTransaction, transaction.id).category_id == expenses.id
    envelope = mem_session.exec(select(BudgetEnvelope)).one()
    assert envelope.category_id == expenses.id


def test_seed_does_not_override_a_custom_parent(mem_session):
    seed_categories(mem_session)
    categories = {category.nom: category for category in mem_session.exec(select(BudgetCategory)).all()}
    custom = BudgetCategory(nom="Organisation personnelle")
    mem_session.add(custom)
    mem_session.commit()
    mem_session.refresh(custom)

    transport = categories["Transport"]
    transport.parent_id = custom.id
    logement = categories["Logement"]
    logement.parent_id = None
    mem_session.add(transport)
    mem_session.add(logement)
    mem_session.commit()

    seed_categories(mem_session)

    assert mem_session.get(BudgetCategory, transport.id).parent_id == custom.id
    assert mem_session.get(BudgetCategory, logement.id).parent_id is None
