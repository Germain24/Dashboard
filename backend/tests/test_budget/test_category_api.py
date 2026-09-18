from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app
from app.models.budget import BudgetCategory, BudgetTransaction


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def create_category(client: TestClient, name: str, parent_id: int | None = None) -> int:
    response = client.post("/budget/categories", json={"nom": name, "parent_id": parent_id})
    assert response.status_code == 201
    return response.json()["id"]


def test_update_category_moves_and_renames_without_changing_transaction_reference(client, session):
    root_id = create_category(client, "Dépenses")
    destination_id = create_category(client, "Investissement", root_id)
    old_parent_id = create_category(client, "Divers", root_id)
    category_id = create_category(client, "Placements", old_parent_id)
    transaction = BudgetTransaction(
        date=dt.date(2026, 9, 1),
        montant=-250.0,
        marchand="Virement courtier",
        category_id=category_id,
    )
    session.add(transaction)
    session.commit()

    response = client.patch(
        f"/budget/categories/{category_id}",
        json={"nom": "Bourse", "parent_id": destination_id},
    )

    assert response.status_code == 200
    assert response.json()["nom"] == "Bourse"
    assert response.json()["parent_id"] == destination_id
    assert session.get(BudgetTransaction, transaction.id).category_id == category_id


def test_update_category_rejects_duplicate_sibling_and_cycles(client):
    root_id = create_category(client, "Dépenses")
    first_id = create_category(client, "Transport", root_id)
    second_id = create_category(client, "Loisirs", root_id)
    child_id = create_category(client, "Train", first_id)

    duplicate = client.patch(
        f"/budget/categories/{second_id}",
        json={"nom": "Transport", "parent_id": root_id},
    )
    cycle = client.patch(
        f"/budget/categories/{first_id}",
        json={"parent_id": child_id},
    )

    assert duplicate.status_code == 409
    assert cycle.status_code == 422
