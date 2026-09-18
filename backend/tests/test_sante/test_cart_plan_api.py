import datetime as dt

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import app
from app.models.sante import MesureSante, NutritionGoal


def _fake_df():
    cols = ["Energie", "Proteines", "Lipides", "Glucides", "Prix", "VitC", "Fibres", "Fer",
            "Magnesium", "Omega 3", "VitA", "VitB1", "VitB2", "VitB3", "VitB5", "VitB6",
            "VitB9", "VitB12", "VitD", "VitE", "VitK", "Calcium", "Zinc", "Potassium",
            "Iode", "Selenium", "Phosphore", "Sodium", "Cholesterol", "AG satures", "TotalSugars"]
    data = {
        "Legume": [50, 3, 0.5, 8, 0.4] + [50] * (len(cols) - 5),
        "Riz":    [130, 3, 0.3, 28, 0.2] + [5] * (len(cols) - 5),
        "Poulet": [165, 31, 3.6, 0, 1.2] + [5] * (len(cols) - 5),
    }
    df = pd.DataFrame.from_dict(data, orient="index", columns=cols)
    df["MaxQty"] = 0.0
    df["MinQty"] = 0.0
    return df


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(NutritionGoal(actif=True))
        s.add(MesureSante(date=dt.date(2026, 7, 20), poids=51.0))
        s.commit()
    from app.services.sante import fenetre_service as fs
    monkeypatch.setattr(fs, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fs, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    monkeypatch.setattr(fs, "_refresh_prices_best_effort", lambda: None)
    monkeypatch.setattr(fs, "_load_pantry_items", lambda: [])
    import app.api.sante.fenetre as fenetre_api
    monkeypatch.setattr(fenetre_api, "load_aliments_dataframe", lambda *_a, **_k: _fake_df())
    monkeypatch.setattr(fenetre_api, "apply_superc_catalog_prices", lambda df, day=None: (df, []))
    # Cache Super C hermétique (l'import est local dans l'endpoint).
    monkeypatch.setattr("app.services.cuisine.store_pricing.load_cached_items", lambda store: [])
    app.dependency_overrides[get_session] = lambda: Session(engine)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_cart_plan_after_generate(client):
    r = client.post("/sante/fenetre/generate", json={"date": "2026-07-20", "poids": 51.0})
    assert r.status_code == 200, r.text
    r2 = client.get("/sante/fenetre/cart-plan", params={"date": "2026-07-20"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["anchor_date"] == "2026-07-20"
    assert len(body["items"]) >= 1
    assert all(it["qty"] >= 1 for it in body["items"])
    # cache vide -> aucun produit matché -> tout à vérifier
    assert all(it["a_verifier"] for it in body["items"])


def test_generate_can_use_recorded_prices_without_refreshing(client, monkeypatch):
    from app.services.sante import fenetre_service as fs

    def refresh_must_not_run():
        raise AssertionError("le mode prix enregistrés ne doit pas rafraîchir le catalogue")

    monkeypatch.setattr(fs, "_ensure_prices_before_optimization", refresh_must_not_run)
    response = client.post(
        "/sante/fenetre/generate",
        json={"date": "2026-07-20", "poids": 51.0, "force": True, "refresh_prices": False},
    )

    assert response.status_code == 200, response.text


def test_cart_plan_404_without_window(client):
    r = client.get("/sante/fenetre/cart-plan", params={"date": "2026-07-20"})
    assert r.status_code == 404


def test_cart_fill_starts_job_for_current_window(client, monkeypatch):
    client.post("/sante/fenetre/generate", json={"date": "2026-07-20", "poids": 51.0})
    seen = {}

    def fake_start(items, anchor_date):
        seen.update(items=items, anchor_date=anchor_date)
        return ({
            "job_id": "job-1", "anchor_date": anchor_date, "status": "queued",
            "message": "Chrome", "current": 0, "total": len(items),
            "results": [], "error": None,
        }, True)

    monkeypatch.setattr("app.services.sante.superc_cart.start_cart_fill", fake_start)
    response = client.post("/sante/fenetre/cart-fill", params={"date": "2026-07-20"})

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-1"
    assert response.json()["created"] is True
    assert seen["anchor_date"] == "2026-07-20"
    assert len(seen["items"]) >= 1


def test_cart_fill_status_404(client, monkeypatch):
    monkeypatch.setattr("app.services.sante.superc_cart.get_cart_fill", lambda job_id: None)
    assert client.get("/sante/fenetre/cart-fill/missing").status_code == 404
