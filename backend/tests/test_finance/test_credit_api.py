"""Intégration API : CRUD marge de crédit + calcul du plan (v2, règles à seuils)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


def _add_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    return dt.date(year, month + 1, 1)


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
    assert "date_cible" in r.json()

    r = client.patch("/finance/credit/profile", json={"date_cible": "2028-09-01"})
    assert r.status_code == 200
    assert r.json()["date_cible"] == "2028-09-01"


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


def test_rule_crud(client):
    r = client.post("/finance/credit/rules", json={"seuil_score": 720, "type": "hausse", "montant_estime": 1000})
    assert r.status_code == 201
    rule_id = r.json()["id"]
    assert client.get("/finance/credit/rules").json()[0]["seuil_score"] == 720
    assert client.delete(f"/finance/credit/rules/{rule_id}").status_code == 204
    assert client.delete(f"/finance/credit/rules/{rule_id}").status_code == 404


def test_plan_endpoint_produces_roadmap_and_growing_margin(client):
    today = dt.date.today()
    six_months_ago = _add_months(today, -6)
    date_cible = _add_months(today, 12)

    client.patch("/finance/credit/profile", json={"date_cible": date_cible.isoformat()})
    client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    client.post("/finance/credit/scores", json={"date": six_months_ago.isoformat(), "score": 650, "source": "Credit Karma"})
    client.post("/finance/credit/scores", json={"date": today.isoformat(), "score": 680, "source": "Credit Karma"})
    client.post("/finance/credit/rules", json={"seuil_score": 685, "type": "hausse", "montant_estime": 1000})

    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["projection_possible"] is True
    assert body["marge_actuelle"] == 700.0
    assert len(body["projection_score"]) > 1
    margins = [p["marge_totale"] for p in body["projection_marge"]]
    assert margins == sorted(margins)
    assert len(body["actions"]) >= 1
    assert body["actions"][0]["type"] == "hausse"


def test_voyage_budget_endpoint_chains_active_cards(client):
    client.post("/finance/credit/accounts", json={
        "institution": "A", "produit": "Carte", "limite_actuelle": 15000, "date_ouverture": "2025-09-01",
    })
    client.post("/finance/credit/accounts", json={
        "institution": "B", "produit": "Carte", "limite_actuelle": 5000, "date_ouverture": "2025-09-01",
    })
    client.post("/finance/credit/accounts", json={
        "institution": "C", "produit": "Carte", "limite_actuelle": 3000, "date_ouverture": "2025-09-01",
    })
    r = client.get("/finance/credit/voyage-budget")
    assert r.status_code == 200
    body = r.json()
    assert body["budget_total"] == 23000.0
    assert body["mois_total"] == 3
    assert [m["budget"] for m in body["mois"]] == [15000.0, 5000.0, 3000.0]


def test_plan_endpoint_without_enough_score_history_has_no_projection(client):
    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["projection_possible"] is False
    assert body["projection_score"] == []
    assert body["actions"] == []
