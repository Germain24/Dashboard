"""Test /health - app demarre, DB repond, et modules non portes ont leur /ping."""

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
    """Chaque module non encore porté a un /ping stub fonctionnel.

    Modules portés (CONV 2 = garderobe, CONV 3 = sante) ont leurs propres
    tests dans tests/test_<module>/ et ne sont plus dans cette liste.
    """
    client = TestClient(app)
    # Modules conservant un /ping stub. Les modules portés qui ont depuis
    # remplacé leur stub par de vraies routes (budget, cuisine, habitudes,
    # livres, garderobe, sante) ont leurs propres tests dédiés.
    modules = [
        "finance",
        "agenda",
        "etudes",
        "entrainement",
        "robot",
    ]
    for m in modules:
        r = client.get(f"/{m}/ping")
        assert r.status_code == 200, f"{m} failed: {r.status_code}"
        assert r.json()["module"] == m
