"""Intégration API : CRUD marge de crédit + calcul du plan."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


def test_profile_get_and_patch(client):
    r = client.get("/finance/credit/profile")
    assert r.status_code == 200
    assert r.json()["revenu_annuel"] == 0.0

    r = client.patch("/finance/credit/profile", json={"revenu_annuel": 40000})
    assert r.status_code == 200
    assert r.json()["revenu_annuel"] == 40000.0


def test_account_crud(client):
    r = client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    assert r.status_code == 201
    account_id = r.json()["id"]

    r = client.get("/finance/credit/accounts")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.patch(f"/finance/credit/accounts/{account_id}", json={"limite_actuelle": 1200})
    assert r.status_code == 200
    assert r.json()["limite_actuelle"] == 1200.0

    r = client.delete(f"/finance/credit/accounts/{account_id}")
    assert r.status_code == 204
    r = client.delete(f"/finance/credit/accounts/{account_id}")
    assert r.status_code == 404


def test_score_crud(client):
    r = client.post("/finance/credit/scores", json={"date": "2026-01-01", "score": 650, "source": "Credit Karma"})
    assert r.status_code == 201
    entry_id = r.json()["id"]
    assert client.get("/finance/credit/scores").json()[0]["score"] == 650
    assert client.delete(f"/finance/credit/scores/{entry_id}").status_code == 204


def test_plan_endpoint_returns_current_margin(client):
    client.patch("/finance/credit/profile", json={
        "revenu_annuel": 40000, "date_arrivee_canada": "2025-09-01", "date_cible": "2025-12-01",
    })
    client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["marge_actuelle"] == 700.0
    assert "actions" in body and "projection" in body


def test_plan_endpoint_produces_roadmap_and_growing_projection(client):
    today = dt.date.today()
    date_cible = today.replace(year=today.year + 1)
    client.patch("/finance/credit/profile", json={
        "revenu_annuel": 40000,
        "date_arrivee_canada": today.isoformat(),
        "date_cible": date_cible.isoformat(),
    })
    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert len(body["projection"]) > 1
    margins = [p["marge_totale"] for p in body["projection"]]
    assert margins == sorted(margins)  # la marge totale ne diminue jamais dans cette simulation
    assert len(body["actions"]) > 0
    assert any(a["type"] == "ouverture" for a in body["actions"])
