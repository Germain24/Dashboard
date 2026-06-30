"""API conseils d'achat combinatoires (GET /garderobe/recommendations)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app
from app.models.garderobe import Vetement


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_recommendations_combinatoire(client, session):
    session.add(Vetement(id="h", nom="Haut", categorie="Haut", couleur="Noir"))
    session.add(Vetement(id="p", nom="Pant", categorie="Pantalon", couleur="Noir"))
    session.commit()

    r = client.get("/garderobe/recommendations")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"total_tenues", "conseils"}
    assert data["total_tenues"] == 0  # pas de chaussures -> aucune tenue
    assert data["conseils"][0]["slot"] == "Chaussures"
    assert data["conseils"][0]["debloque"] >= 1
    assert set(data["conseils"][0].keys()) == {"slot", "couleur", "debloque", "total_apres"}
