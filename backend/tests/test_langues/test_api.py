"""Tests d'intégration — API Langues (vocab/kanji + projets internationaux)."""

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
    r = client.get("/langues/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "langues"


def test_crud_vocab(client):
    r = client.post("/langues/vocab", json={"terme": "水", "lecture": "みず", "traduction": "eau", "type": "kanji", "tags": "JLPT N5"})
    assert r.status_code == 201
    vid = r.json()["id"]

    r = client.patch(f"/langues/vocab/{vid}", json={"maitrise": 3})
    assert r.json()["maitrise"] == 3

    assert len(client.get("/langues/vocab?type=kanji").json()) == 1
    assert client.get("/langues/vocab?type=vocab").json() == []

    assert client.delete(f"/langues/vocab/{vid}").status_code == 204


def test_vocab_stats(client):
    client.post("/langues/vocab", json={"terme": "食べる", "lecture": "たべる", "traduction": "manger", "type": "vocab", "maitrise": 2})
    client.post("/langues/vocab", json={"terme": "飲む", "lecture": "のむ", "traduction": "boire", "type": "vocab", "maitrise": 2})
    client.post("/langues/vocab", json={"terme": "火", "traduction": "feu", "type": "kanji"})

    s = client.get("/langues/vocab/stats").json()
    assert s["vocab"]["total"] == 2
    assert s["vocab"]["par_maitrise"]["2"] == 2
    assert s["kanji"]["total"] == 1


def test_crud_projet(client):
    r = client.post("/langues/projets", json={"titre": "Semestre à Tokyo", "type": "semestre", "echeance": "2027-04-01", "budget_estime": 8000})
    assert r.status_code == 201
    pid = r.json()["id"]

    r = client.patch(f"/langues/projets/{pid}", json={"statut": "planifie"})
    assert r.json()["statut"] == "planifie"

    client.post("/langues/projets", json={"titre": "Visa vacances-travail", "type": "visa", "echeance": "2026-11-01"})
    # Tri par échéance croissante, sans échéance en dernier.
    titres = [p["titre"] for p in client.get("/langues/projets").json()]
    assert titres == ["Visa vacances-travail", "Semestre à Tokyo"]

    assert client.delete(f"/langues/projets/{pid}").status_code == 204


def test_validation(client):
    assert client.post("/langues/vocab", json={"terme": "x", "traduction": "y", "type": "inconnu"}).status_code == 422
    assert client.post("/langues/vocab", json={"terme": "x", "traduction": "y", "maitrise": 9}).status_code == 422
    assert client.post("/langues/projets", json={"titre": "x", "type": "inconnu"}).status_code == 422
    assert client.post("/langues/projets", json={"titre": "x", "statut": "inconnu"}).status_code == 422
