"""API GET /finance/impots/calcul."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app
from app.models.finance import Transaction


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_get_calcul_impots(client, session):
    session.add(Transaction(date=dt.datetime(2025, 1, 1), ticker="AAA", broker="trading212",
                             type="achat", quantite=10, prix_unitaire=100.0, devise="EUR"))
    session.add(Transaction(date=dt.datetime(2025, 6, 1), ticker="AAA", broker="trading212",
                             type="vente", quantite=10, prix_unitaire=150.0, devise="EUR"))
    session.commit()

    r = client.get("/finance/impots/calcul", params={"annee": 2025})
    assert r.status_code == 200
    data = r.json()
    assert data["gain_brut"] == 500.0
    assert data["pfu"]["total"] == 157.0
    assert data["recommande"] == "bareme"


def test_get_calcul_impots_no_transactions(client):
    r = client.get("/finance/impots/calcul", params={"annee": 2025})
    assert r.status_code == 200
    data = r.json()
    assert data["gain_brut"] == 0.0
    assert data["gain_net_imposable"] == 0.0


def test_get_ventes_detail(client, session):
    session.add(Transaction(date=dt.datetime(2025, 1, 1), ticker="AAA", broker="trading212",
                             type="achat", quantite=10, prix_unitaire=100.0, devise="EUR"))
    session.add(Transaction(date=dt.datetime(2025, 6, 1), ticker="AAA", broker="trading212",
                             type="vente", quantite=10, prix_unitaire=150.0, devise="EUR"))
    session.commit()

    r = client.get("/finance/impots/ventes", params={"annee": 2025})
    assert r.status_code == 200
    data = r.json()["ventes"]
    assert len(data) == 1
    assert data[0]["ticker"] == "AAA"
    assert data[0]["prix_achat_moyen"] == 100.0
    assert data[0]["prix_vente"] == 150.0
    assert data[0]["plus_value"] == 500.0
    assert data[0]["calculable"] is True
    assert data[0]["produit_net"] == 1500.0


def test_get_ventes_detail_empty_when_no_sales(client):
    r = client.get("/finance/impots/ventes")
    assert r.status_code == 200
    assert r.json()["ventes"] == []
