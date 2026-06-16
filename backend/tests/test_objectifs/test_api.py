"""Tests d'intégration — API Objectifs long terme."""

from __future__ import annotations

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


def test_ping(client):
    r = client.get("/objectifs/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "objectifs"


def test_crud_goal(client):
    r = client.post("/objectifs/goals", json={"titre": "Master finance quantitative", "categorie": "master", "echeance": "2027-09-01"})
    assert r.status_code == 201
    gid = r.json()["id"]
    assert r.json()["statut"] == "veille"

    r = client.patch(f"/objectifs/goals/{gid}", json={"statut": "preparation", "progression": 25})
    assert r.status_code == 200
    assert r.json()["progression"] == 25

    r = client.delete(f"/objectifs/goals/{gid}")
    assert r.status_code == 204
    assert client.get("/objectifs/goals").json() == []


def test_validation(client):
    assert client.post("/objectifs/goals", json={"titre": "X", "categorie": "inconnu"}).status_code == 422
    assert client.post("/objectifs/goals", json={"titre": "X", "statut": "inconnu"}).status_code == 422
    assert client.post("/objectifs/goals", json={"titre": "X", "progression": 150}).status_code == 422


def test_filtre_statut_et_tri_echeance(client):
    client.post("/objectifs/goals", json={"titre": "Sans échéance", "statut": "veille"})
    client.post("/objectifs/goals", json={"titre": "Gendarmerie", "categorie": "concours", "statut": "preparation", "echeance": "2027-03-01"})
    client.post("/objectifs/goals", json={"titre": "Stage gestion d'actifs", "categorie": "carriere", "statut": "preparation", "echeance": "2026-12-01"})

    r = client.get("/objectifs/goals?statut=preparation")
    assert [g["titre"] for g in r.json()] == ["Stage gestion d'actifs", "Gendarmerie"]
    # Les objectifs sans échéance arrivent en dernier dans la liste complète.
    assert [g["titre"] for g in client.get("/objectifs/goals").json()][-1] == "Sans échéance"
