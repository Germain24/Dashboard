from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api import api_router  # noqa: F401  (assure l'enregistrement)
from app.core.db import get_session
from app.main import create_app


def _client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_put_then_get_entry():
    client = _client()
    r = client.put("/journal/entries/2026-06-01", json={"humeur": 4, "energie": 3, "tags": ["calme"], "note": "ok"})
    assert r.status_code == 200
    assert r.json()["humeur"] == 4
    g = client.get("/journal/entries/2026-06-01")
    assert g.status_code == 200 and g.json()["tags"] == ["calme"]


def test_get_missing_entry_404():
    client = _client()
    assert client.get("/journal/entries/2030-01-01").status_code == 404


def test_trends_and_correlations_empty_ok():
    client = _client()
    assert client.get("/journal/trends?days=30").status_code == 200
    c = client.get("/journal/correlations?days=90")
    assert c.status_code == 200 and "caveat" in c.json()
