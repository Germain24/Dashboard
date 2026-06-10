"""#501 — pagination standardisée sur la liste des habitudes."""
from __future__ import annotations

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session
from app.models.habitudes import Habit


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="client")
def client_fixture(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as s:
        yield s


def test_habits_list_exposes_total_count(client, session):
    for i in range(3):
        session.add(Habit(nom=f"h{i}", ordre=i))
    session.commit()

    r = client.get("/habitudes/habits?limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.headers["X-Total-Count"] == "3"


def test_habits_list_default_unchanged(client, session):
    """Rétro-compat : sans query params, tout est renvoyé (corps = tableau)."""
    session.add(Habit(nom="seule"))
    session.commit()

    r = client.get("/habitudes/habits")
    assert r.status_code == 200
    assert [h["nom"] for h in r.json()] == ["seule"]
