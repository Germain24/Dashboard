"""Tests d'intégration légers sur les routes /sante/*.

On bascule la DB sur SQLite en mémoire via une factory de session, on insère
un minimum de données (aliments + mesures) et on vérifie le bon comportement
des endpoints critiques.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import get_session
from app.main import app
from app.models.sante import Aliment, MesureSante

# Catalogue minimal — suffit pour que l'optimiseur converge
_MINI_FOODS = {
    "Poulet":      {"Prix": 1.2, "Proteines": 30.0, "Lipides": 5.0, "Glucides": 0.0, "Energie": 165.0, "Fibres": 0.0},
    "Riz blanc":   {"Prix": 0.3, "Proteines": 7.0,  "Lipides": 0.5, "Glucides": 78.0, "Energie": 350.0, "Fibres": 1.0},
    "Brocoli":     {"Prix": 0.4, "Proteines": 3.0,  "Lipides": 0.4, "Glucides": 7.0,  "Energie": 35.0,  "Fibres": 3.0},
    "Huile olive": {"Prix": 0.8, "Proteines": 0.0,  "Lipides": 100.0, "Glucides": 0.0, "Energie": 900.0, "Fibres": 0.0},
}


@pytest.fixture
def client(tmp_path):
    """Client FastAPI avec une DB SQLite isolée par test."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    # Seed catalogue
    with Session(engine) as s:
        for nom, props in _MINI_FOODS.items():
            s.add(Aliment(nom=nom, proprietes=props))
        s.commit()

    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_ping_ready(client):
    r = client.get("/sante/ping")
    assert r.status_code == 200
    assert r.json() == {"module": "sante", "ready": True}


def test_list_aliments(client):
    r = client.get("/sante/aliments")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == len(_MINI_FOODS)
    assert {a["nom"] for a in rows} == set(_MINI_FOODS.keys())


def test_create_then_read_mesure(client):
    today = dt.date.today().isoformat()
    r = client.post("/sante/mesures", json={"date": today, "poids": 51.0, "note": "post-petit-dej"})
    assert r.status_code == 201
    data = r.json()
    assert data["poids"] == 51.0
    # GET listing inclut la mesure
    r2 = client.get("/sante/mesures")
    assert r2.status_code == 200
    assert any(m["date"] == today for m in r2.json())


def test_upsert_mesure_overwrites(client):
    today = dt.date.today().isoformat()
    client.post("/sante/mesures", json={"date": today, "poids": 51.0})
    r = client.post("/sante/mesures", json={"date": today, "poids": 51.5})
    assert r.status_code in (200, 201)
    # GET → 51.5
    rows = client.get("/sante/mesures").json()
    today_row = next(m for m in rows if m["date"] == today)
    assert today_row["poids"] == 51.5


def test_goal_singleton_autocreated(client):
    r = client.get("/sante/goal")
    assert r.status_code == 200
    g = r.json()
    assert g["actif"] is True
    # Défauts compatibles legacy
    assert g["surplus_kcal_sport"] == 500.0
    assert g["rest_factor"] == 1.1
    assert g["sport_days"] == [0, 1, 2, 4, 5]


def test_goal_patch_updates_fields(client):
    r = client.patch("/sante/goal", json={"poids_cible": 71.0, "body_fat_target_pct": 10.0, "type": "bulk"})
    assert r.status_code == 200
    g = r.json()
    assert g["poids_cible"] == 71.0
    assert g["body_fat_target_pct"] == 10.0


def test_targets_today_requires_weight(client):
    """Sans mesure préalable et sans param `poids`, /targets/today refuse."""
    r = client.get("/sante/targets/today")
    assert r.status_code == 400


def test_targets_today_with_provided_weight(client):
    r = client.get("/sante/targets/today?poids=51&intensity=medium")
    assert r.status_code == 200
    data = r.json()
    assert data["poids"] == 51.0
    assert data["intensity"] == "medium"
    assert data["base_targets"]["Calories"] > 1000


def test_generate_plan_end_to_end(client):
    today = dt.date.today().isoformat()
    # Pré-requis : une mesure pour fixer le poids
    client.post("/sante/mesures", json={"date": today, "poids": 51.0})
    r = client.post(
        "/sante/plan/generate",
        json={"intensity": "medium", "budget_max_daily": 18.0},
    )
    # Avec un catalogue minimal mais sain, ça doit converger
    assert r.status_code in (200, 422)  # 422 = optimiseur n'a pas convergé
    if r.status_code == 200:
        plan = r.json()
        assert plan["intensite"] == "medium"
        assert plan["poids_used"] == 51.0
        assert plan["items"]
        assert "Calories" in plan["totals"]


def test_projection_needs_target_weight(client):
    """Sans poids cible défini, /projection refuse."""
    r = client.get("/sante/projection")
    assert r.status_code == 400


def test_projection_with_target(client):
    """Avec quelques mesures et un poids cible, on retourne une projection."""
    today = dt.date.today()
    # 15 jours de gain stable
    for i in range(15):
        d = (today - dt.timedelta(days=14 - i)).isoformat()
        client.post("/sante/mesures", json={"date": d, "poids": 50.0 + i * 0.1})
    client.patch("/sante/goal", json={"poids_cible": 71.0})
    r = client.get("/sante/projection")
    assert r.status_code == 200
    proj = r.json()
    assert proj["target_weight"] == 71.0
    assert proj["current_weight"] == pytest.approx(51.4, abs=0.1)
    # Tendance positive cohérente
    assert proj["slope_kg_per_week"] > 0
