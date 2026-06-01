"""Tests d'intégration — API Études avec SQLite in-memory.

Couvre les endpoints CRUD + bridge Agenda silencieux.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


# ───────────────────── ping ──────────────────────────────────────

def test_ping(client):
    r = client.get("/etudes/ping")
    assert r.status_code == 200
    assert r.json()["ready"] is True


# ───────────────────── cours CRUD ────────────────────────────────

def _make_cours(client, code="INF1000", semestre="A2026"):
    return client.post("/etudes/cours", json={
        "code": code,
        "nom": f"Cours {code}",
        "semestre": semestre,
        "credits": 3,
    })


def test_create_cours(client):
    r = _make_cours(client)
    assert r.status_code == 201
    data = r.json()
    assert data["code"] == "INF1000"
    assert data["lettre"] is None        # pas encore de note
    assert data["total_minutes_etude"] == 0


def test_list_cours(client):
    _make_cours(client, "INF1000", "A2026")
    _make_cours(client, "MAT2000", "A2026")
    _make_cours(client, "PHI1000", "H2027")
    r = client.get("/etudes/cours?semestre=A2026")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_patch_cours_note_finale(client):
    cours_id = _make_cours(client).json()["id"]
    r = client.patch(f"/etudes/cours/{cours_id}", json={"note_finale": 88.5})
    assert r.status_code == 200
    data = r.json()
    assert data["note_finale"] == 88.5
    assert data["lettre"] == "A"
    assert data["points_gpa"] == 4.0


def test_delete_cours(client):
    cours_id = _make_cours(client).json()["id"]
    r = client.delete(f"/etudes/cours/{cours_id}")
    assert r.status_code == 204
    assert client.get(f"/etudes/cours/{cours_id}").status_code == 404


# ───────────────────── évaluations ───────────────────────────────

def _make_eval(client, cours_id, titre="Examen final", jours=14):
    deadline = (dt.date.today() + dt.timedelta(days=jours)).isoformat()
    return client.post("/etudes/evaluations", json={
        "cours_id": cours_id,
        "titre": titre,
        "type_eval": "exam",
        "date_limite": deadline,
    })


def test_create_evaluation_with_bridge(client):
    cours_id = _make_cours(client).json()["id"]
    r = _make_eval(client, cours_id)
    assert r.status_code == 201
    data = r.json()
    assert data["cours_id"] == cours_id
    assert data["jours_restants"] == 14
    # Le bridge Agenda peut échouer silencieusement (pas de module Agenda
    # complètement configuré dans la DB de test) → pas d'assertion sur
    # l'existence de la tâche Agenda ici


def test_create_evaluation_cours_manquant(client):
    r = client.post("/etudes/evaluations", json={
        "cours_id": 9999,
        "titre": "Ghost eval",
    })
    assert r.status_code == 404


def test_list_evals_for_cours(client):
    cours_id = _make_cours(client).json()["id"]
    _make_eval(client, cours_id, "TP1", jours=7)
    _make_eval(client, cours_id, "Examen", jours=21)
    r = client.get(f"/etudes/cours/{cours_id}/evaluations")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_patch_evaluation_note(client):
    cours_id = _make_cours(client).json()["id"]
    eval_id = _make_eval(client, cours_id).json()["id"]
    r = client.patch(f"/etudes/evaluations/{eval_id}", json={"note_obtenue": 78.0})
    assert r.status_code == 200
    assert r.json()["note_obtenue"] == 78.0


def test_delete_evaluation(client):
    cours_id = _make_cours(client).json()["id"]
    eval_id = _make_eval(client, cours_id).json()["id"]
    assert client.delete(f"/etudes/evaluations/{eval_id}").status_code == 204
    assert client.get(f"/etudes/evaluations/{eval_id}").status_code == 404


# ───────────────────── deadlines ─────────────────────────────────

def test_deadlines_horizon(client):
    cours_id = _make_cours(client).json()["id"]
    _make_eval(client, cours_id, "Intra", jours=5)
    _make_eval(client, cours_id, "Final", jours=60)
    r = client.get("/etudes/deadlines?days=30")
    assert r.status_code == 200
    titres = [e["titre"] for e in r.json()]
    assert "Intra" in titres
    assert "Final" not in titres


# ───────────────────── GPA ───────────────────────────────────────

def test_gpa_empty(client):
    r = client.get("/etudes/gpa")
    assert r.status_code == 200
    assert r.json()["gpa"] is None


def test_gpa_semestre(client):
    c1 = _make_cours(client, "INF1000", "A2026").json()["id"]
    c2 = _make_cours(client, "MAT2000", "A2026").json()["id"]
    client.patch(f"/etudes/cours/{c1}", json={"note_finale": 90.0})   # A+ 4.3
    client.patch(f"/etudes/cours/{c2}", json={"note_finale": 85.0})   # A  4.0
    r = client.get("/etudes/gpa?semestre=A2026")
    assert r.status_code == 200
    data = r.json()
    assert data["nb_cours"] == 2
    assert abs(data["gpa"] - 4.15) < 0.05


def test_gpa_cumulatif(client):
    c1 = _make_cours(client, "INF1000", "A2025").json()["id"]
    c2 = _make_cours(client, "MAT2000", "H2026").json()["id"]
    client.patch(f"/etudes/cours/{c1}", json={"note_finale": 90.0})   # 4.3
    client.patch(f"/etudes/cours/{c2}", json={"note_finale": 73.0})   # 3.0
    r = client.get("/etudes/gpa")
    data = r.json()
    assert data["semestre"] is None
    assert abs(data["gpa"] - 3.65) < 0.05


# ───────────────────── sessions d'étude ──────────────────────────

def test_create_session_etude(client):
    cours_id = _make_cours(client).json()["id"]
    r = client.post("/etudes/sessions", json={
        "cours_id": cours_id,
        "duree_min": 90,
        "sujet": "Révision chapitre 3",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["duree_min"] == 90


def test_session_date_auto(client):
    r = client.post("/etudes/sessions", json={"duree_min": 25})
    assert r.status_code == 201
    assert r.json()["date"] == dt.date.today().isoformat()


def test_total_minutes_dans_cours(client):
    cours_id = _make_cours(client).json()["id"]
    client.post("/etudes/sessions", json={"cours_id": cours_id, "duree_min": 60})
    client.post("/etudes/sessions", json={"cours_id": cours_id, "duree_min": 45})
    r = client.get(f"/etudes/cours/{cours_id}")
    assert r.json()["total_minutes_etude"] == 105


def test_delete_session(client):
    s_id = client.post("/etudes/sessions", json={"duree_min": 30}).json()["id"]
    assert client.delete(f"/etudes/sessions/{s_id}").status_code == 204


def test_delete_cours_cascade(client):
    """Supprimer un cours efface ses évaluations et sessions (cascade manuelle)."""
    cours_id = _make_cours(client).json()["id"]
    eval_id = _make_eval(client, cours_id).json()["id"]
    client.post("/etudes/sessions", json={"cours_id": cours_id, "duree_min": 30})
    assert client.delete(f"/etudes/cours/{cours_id}").status_code == 204
    assert client.get(f"/etudes/evaluations/{eval_id}").status_code == 404
