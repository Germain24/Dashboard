"""Tests d'intégration — API Skincare avec SQLite in-memory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session


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
    r = client.get("/skincare/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "skincare"


def test_create_list_update_delete(client):
    r = client.post("/skincare/products", json={"nom": "Sérum", "type": "serum", "moment": "AM"})
    assert r.status_code == 201
    pid = r.json()["id"]

    r = client.get("/skincare/products")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.patch(f"/skincare/products/{pid}", json={"ordre": 5})
    assert r.status_code == 200
    assert r.json()["ordre"] == 5

    r = client.delete(f"/skincare/products/{pid}")
    assert r.status_code == 204
    # suppression logique → plus dans la liste des actifs
    assert client.get("/skincare/products").json() == []


def test_routine_ordered_and_includes_les_deux(client):
    client.post("/skincare/products", json={"nom": "B", "moment": "AM", "ordre": 2})
    client.post("/skincare/products", json={"nom": "A", "moment": "AM", "ordre": 1})
    client.post("/skincare/products", json={"nom": "SPF", "moment": "les_deux", "ordre": 3})
    r = client.get("/skincare/routine?moment=AM")
    assert [p["nom"] for p in r.json()] == ["A", "B", "SPF"]


def test_today_structure(client):
    r = client.get("/skincare/today")
    body = r.json()
    assert set(body.keys()) == {"date", "AM", "PM", "due"}


def test_update_404(client):
    assert client.patch("/skincare/products/999", json={"ordre": 1}).status_code == 404
