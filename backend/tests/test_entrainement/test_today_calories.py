"""Tests des endpoints /entrainement/today et /entrainement/calories/{date}."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import get_session
from app.main import app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_today_returns_program_day(client):
    client.post("/entrainement/program/seed-garmin", json={})
    r = client.get("/entrainement/today")
    assert r.status_code == 200
    data = r.json()
    today = dt.date.today()
    assert data["date"] == today.isoformat()
    assert data["weekday"] == today.weekday()
    assert data["jour_label"] in ("Push", "Pull", "Legs", "Upper", "Lower", "Repos")
    assert data["programme_jour_id"] is not None
    assert "poids_corps_kg" in data
    assert data["poids_corps_kg"] > 0


def test_today_enriches_slots_with_exercice_id(client):
    """Les labels du seed Garmin doivent matcher des exercices du catalogue."""
    client.post("/entrainement/program/seed-garmin", json={})
    r = client.get("/entrainement/today")
    data = r.json()
    if data["jour_label"] == "Repos":
        # Test n'est pas applicable un jour de repos
        return
    # Au moins un slot d'exercice (hors warm-ups) doit avoir un exercice_id
    non_warmup_slots = [
        s for s in data["slots"]
        if "warm-up" not in (s["label"] or "").lower()
    ]
    if non_warmup_slots:
        assert any(s["exercice_id"] is not None for s in non_warmup_slots)


def test_today_seance_en_cours_after_start(client):
    """Après POST /sessions, /today expose la séance en cours."""
    client.post("/entrainement/program/seed-garmin", json={})
    r0 = client.get("/entrainement/today").json()
    assert r0["seance_en_cours"] is None

    client.post(
        "/entrainement/sessions",
        json={
            "date": dt.datetime.utcnow().isoformat(),
            "type": "push",
            "programme_jour_id": r0["programme_jour_id"],
        },
    )
    r1 = client.get("/entrainement/today").json()
    assert r1["seance_en_cours"] is not None


def test_today_kcal_live_after_adding_set(client):
    """kcal_estimees doit croître à mesure qu'on ajoute des séries."""
    client.post("/entrainement/program/seed-garmin", json={})
    ex = client.get("/entrainement/exercises").json()
    sq = next((e for e in ex if e["nom"] == "Squat barre"), None)
    if sq is None:
        return  # seed bizarre, on skip
    s = client.post(
        "/entrainement/sessions",
        json={"date": dt.datetime.utcnow().isoformat(), "type": "legs"},
    ).json()
    r_before = client.get("/entrainement/today").json()
    kcal_before = r_before["kcal_estimees"]

    client.post(
        f"/entrainement/sessions/{s['id']}/sets",
        json={"exercice_id": sq["id"], "reps": 5, "poids_kg": 100.0},
    )
    r_after = client.get("/entrainement/today").json()
    assert r_after["kcal_estimees"] > kcal_before


def test_calories_for_date_format(client):
    """Format stable pour la CONV nutrition future."""
    r = client.get(f"/entrainement/calories/{dt.date.today().isoformat()}")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {
        "date", "kcal_muscu", "kcal_cardio", "total_kcal", "poids_corps_kg",
    }
    assert data["kcal_muscu"] == 0  # pas de séance encore
    assert data["kcal_cardio"] == 0
    assert data["total_kcal"] == 0


def test_calories_for_date_with_activity(client):
    """Une séance + une course doivent toutes deux compter."""
    today = dt.date.today()
    ex = client.get("/entrainement/exercises").json()
    bench = next(e for e in ex if "Développé couché barre" in e["nom"])
    client.post(
        "/entrainement/sessions",
        json={
            "date": dt.datetime.combine(today, dt.time(18, 0)).isoformat(),
            "type": "push",
            "duree_min": 50,
            "sets": [{"exercice_id": bench["id"], "reps": 8, "poids_kg": 50.0}],
        },
    )
    client.post(
        "/entrainement/cardio",
        json={"date": today.isoformat(), "distance_km": 5.0, "duree_sec": 1500},
    )
    r = client.get(f"/entrainement/calories/{today.isoformat()}")
    data = r.json()
    assert data["kcal_muscu"] > 0
    assert data["kcal_cardio"] > 0
    assert data["total_kcal"] == round(data["kcal_muscu"] + data["kcal_cardio"], 1)
