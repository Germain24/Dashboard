"""Tests d'intégration — API Gaming (jeux + objectifs/builds/filtres)."""

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
    r = client.get("/gaming/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "gaming"


def test_crud_game(client):
    r = client.post("/gaming/games", json={"titre": "Elden Ring", "plateforme": "PS5"})
    assert r.status_code == 201
    gid = r.json()["id"]

    r = client.patch(f"/gaming/games/{gid}", json={"statut": "en_cours", "heures": 12.5})
    assert r.status_code == 200
    assert r.json()["heures"] == 12.5

    r = client.get("/gaming/games?statut=en_cours")
    assert len(r.json()) == 1
    assert r.json()[0]["nb_goals"] == 0

    r = client.delete(f"/gaming/games/{gid}")
    assert r.status_code == 204
    assert client.get("/gaming/games").json() == []


def test_goals_lifecycle(client):
    gid = client.post("/gaming/games", json={"titre": "Path of Exile"}).json()["id"]

    r = client.post(f"/gaming/games/{gid}/goals", json={"titre": "Build arc témoin", "type": "build", "contenu": "Crit + chaîne"})
    assert r.status_code == 201
    goal_id = r.json()["id"]
    client.post(f"/gaming/games/{gid}/goals", json={"titre": "Filtre loot endgame", "type": "filtre"})

    assert client.get(f"/gaming/games/{gid}/goals").status_code == 200
    assert len(client.get(f"/gaming/games/{gid}/goals").json()) == 2
    assert client.get("/gaming/games").json()[0]["nb_goals"] == 2

    r = client.patch(f"/gaming/goals/{goal_id}", json={"fait": True})
    assert r.json()["fait"] is True

    assert client.delete(f"/gaming/goals/{goal_id}").status_code == 204
    # Supprimer le jeu supprime ses objectifs restants (pas d'orphelins).
    assert client.delete(f"/gaming/games/{gid}").status_code == 204


def test_validation(client):
    assert client.post("/gaming/games", json={"titre": "X", "statut": "inconnu"}).status_code == 422
    assert client.post("/gaming/games", json={"titre": "X", "note": 11}).status_code == 422
    gid = client.post("/gaming/games", json={"titre": "Y"}).json()["id"]
    assert client.post(f"/gaming/games/{gid}/goals", json={"titre": "Z", "type": "inconnu"}).status_code == 422
    assert client.post("/gaming/games/999/goals", json={"titre": "Z"}).status_code == 404
