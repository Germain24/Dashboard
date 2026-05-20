"""Tests du seed Garmin (4 programmes Push/Pull/Legs/Upper de Germain)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.db import get_session
from app.main import app
from app.services.entrainement.garmin_seed import (
    GARMIN_EXERCICES,
    GARMIN_WEEKDAYS,
    seed_garmin_programs,
)


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


def test_endpoint_seeds_programs(client):
    r = client.post("/entrainement/program/seed-garmin", json={})
    assert r.status_code == 200
    data = r.json()
    # Tous les jours Garmin (Push/Pull/Legs/Upper/Lower) doivent être seedés au 1er appel.
    # Décision Germain 2026-05-18 : Lower (samedi) = mêmes slots que Legs.
    assert set(data["jours_seedes"]) == {"Push", "Pull", "Legs", "Upper", "Lower"}
    assert data["jours_skipped"] == []
    assert data["exos_crees"] >= 1   # au moins quelques nouveaux exos
    assert data["lower_a_definir"] is False


def test_seed_is_idempotent(client):
    client.post("/entrainement/program/seed-garmin", json={})
    # 2e appel : déjà peuplé → tout skipped
    r = client.post("/entrainement/program/seed-garmin", json={})
    data = r.json()
    assert data["jours_seedes"] == []
    assert set(data["jours_skipped"]) == {"Push", "Pull", "Legs", "Upper", "Lower"}
    assert data["exos_crees"] == 0   # aucun nouveau exo


def test_seed_force_overrides_existing(client):
    client.post("/entrainement/program/seed-garmin", json={})
    # Avec force=true, on écrase
    r = client.post("/entrainement/program/seed-garmin", json={"force": True})
    data = r.json()
    assert set(data["jours_seedes"]) == {"Push", "Pull", "Legs", "Upper", "Lower"}


def test_seeded_program_has_slots(client):
    client.post("/entrainement/program/seed-garmin", json={})
    prog = client.get("/entrainement/program").json()
    by_wd = {j["weekday"]: j for j in prog["jours"]}
    # Lundi = Push avec 9 slots (warmups + 7 exos)
    assert by_wd[0]["label"] == "Push"
    assert len(by_wd[0]["slots"]) == 9
    # Vérifie qu'un slot bien typé est présent
    push_labels = [s["label"] for s in by_wd[0]["slots"]]
    assert "Incline Barbell Bench Press" in push_labels
    assert "Diamond Push-up" in push_labels
    # Samedi (Lower) = mêmes slots que mercredi (Legs) — décision Germain 2026-05-18
    assert by_wd[5]["label"] == "Lower"
    assert by_wd[5]["slots"] == by_wd[2]["slots"]


def test_seeded_exercices_have_garmin_source(client):
    client.post("/entrainement/program/seed-garmin", json={})
    rows = client.get("/entrainement/exercises").json()
    garmin = [e for e in rows if e["source"] == "garmin"]
    # Le seed crée ~23 exos Garmin (certains peuvent être déjà présents si Germain
    # a ajouté manuellement). Au minimum > 10.
    assert len(garmin) >= 10
    noms = {e["nom"] for e in garmin}
    assert "Dumbbell Lying Triceps Extension" in noms  # Skullcrusher
    assert "Kneeling Lat Pull-down" in noms
    assert "GHD Back Extensions" in noms


def test_garmin_seed_constants_well_formed():
    """Vérifie que les constantes du seed sont cohérentes."""
    # Tous les jours référencent un weekday valide
    for wd in GARMIN_WEEKDAYS:
        assert 0 <= wd <= 6
    # Chaque exo a 6 champs (nom, cat, muscles, type_mvt, uni, note)
    for tup in GARMIN_EXERCICES:
        assert len(tup) == 6
        nom, cat, muscles, tm, uni, _note = tup
        assert nom and cat
        assert isinstance(muscles, list)
        assert tm in ("compose", "isolation")
        assert isinstance(uni, bool)


def test_seed_via_service_directly(tmp_path):
    """Le service est appelable directement (utile pour scripts de provisioning)."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/t.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        result = seed_garmin_programs(s)
        assert result["lower_a_definir"] is False
        assert len(result["jours_seedes"]) == 5
