"""Tests d'intégration — API Travail (shifts, summary, settings)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app
from app.services.travail import settings as travail_settings


@pytest.fixture(name="client")
def client_fixture(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    # Isole le JSON des settings du module dans un dossier temporaire.
    monkeypatch.setattr(travail_settings, "settings_file", lambda: tmp_path / "travail_settings.json")

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


def test_ping(client):
    r = client.get("/travail/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "travail"


def test_crud_shift(client):
    r = client.post("/travail/shifts", json={"date_jour": "2026-06-15", "heure_debut": "08:00", "heure_fin": "14:00", "pause_min": 30})
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.get("/travail/shifts?mois=2026-06")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["heures"] == 5.5  # 6h - 30 min de pause

    r = client.patch(f"/travail/shifts/{sid}", json={"statut": "fait"})
    assert r.status_code == 200
    assert r.json()["statut"] == "fait"

    r = client.delete(f"/travail/shifts/{sid}")
    assert r.status_code == 204
    assert client.get("/travail/shifts").json() == []


def test_shift_validation(client):
    assert client.post("/travail/shifts", json={"date_jour": "2026-06-15", "statut": "nimporte"}).status_code == 422
    assert client.post("/travail/shifts", json={"date_jour": "2026-06-15", "heure_debut": "25:00"}).status_code == 422


def test_summary_realise_vs_prevu(client):
    client.put("/travail/settings", json={"taux_horaire": 12.0})
    # Shift fait : 4h à 15 €/h (taux figé sur le shift).
    client.post("/travail/shifts", json={"date_jour": "2026-06-01", "heure_debut": "09:00", "heure_fin": "13:00", "statut": "fait", "taux_horaire": 15.0})
    # Shift prévu : 5h au taux par défaut (12 €/h).
    client.post("/travail/shifts", json={"date_jour": "2026-06-20", "heure_debut": "09:00", "heure_fin": "14:00", "statut": "prevu"})
    # Shift annulé : ignoré.
    client.post("/travail/shifts", json={"date_jour": "2026-06-21", "statut": "annule"})
    # Autre mois : ignoré.
    client.post("/travail/shifts", json={"date_jour": "2026-07-01", "statut": "fait"})

    r = client.get("/travail/summary?mois=2026-06")
    assert r.status_code == 200
    s = r.json()
    assert s["nb_shifts"] == 2
    assert s["heures_faites"] == 4.0
    assert s["heures_prevues"] == 5.0
    assert s["revenu_realise"] == 60.0
    assert s["revenu_prevu"] == 60.0


def test_summary_mois_invalide(client):
    assert client.get("/travail/summary?mois=juin").status_code == 422


def test_settings_roundtrip(client):
    r = client.get("/travail/settings")
    assert r.status_code == 200
    r = client.put("/travail/settings", json={"taux_horaire": 13.5})
    assert r.json()["taux_horaire"] == 13.5
    assert client.get("/travail/settings").json()["taux_horaire"] == 13.5
