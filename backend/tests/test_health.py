"""Test /health — vérifie que l'app démarre et que la DB répond."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["app"] == "mission-control"
    assert "version" in data
    assert data["db"] == "ok"


def test_ping_modules() -> None:
    """Chaque module a un /ping fonctionnel."""
    client = TestClient(app)
    modules = [
        "finance",
        "garderobe",
        "sante",
        "agenda",
        "etudes",
        "entrainement",
        "budget",
        "cuisine",
        "habitudes",
        "livres",
        "robot",
    ]
    for m in modules:
        r = client.get(f"/{m}/ping")
        assert r.status_code == 200, f"{m} failed: {r.status_code}"
        assert r.json()["module"] == m
