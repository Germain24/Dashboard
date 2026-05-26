"""Tests d'intégration — API Agenda.

Utilise une DB SQLite in-memory isolée (même pattern que test_api.py Santé/Entraînement).
"""

from __future__ import annotations

import datetime as dt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session
from app.models.agenda import Evenement, Tache, RegleRecurrence


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()

    def override():
        return session

    app.dependency_overrides[get_session] = override
    return TestClient(app)


# ── /ping ────────────────────────────────────────────────────────────────────

def test_ping(client):
    r = client.get("/agenda/ping")
    assert r.status_code == 200
    assert r.json()["ready"] is True


# ── Events CRUD ───────────────────────────────────────────────────────────────

def test_create_and_get_event(client):
    payload = {
        "titre": "RDV médecin",
        "debut": "2026-09-10T14:00:00",
        "fin": "2026-09-10T15:00:00",
        "categorie": "rdv",
    }
    r = client.post("/agenda/events", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["titre"] == "RDV médecin"
    assert data["id"] is not None
    assert data["is_virtual"] is False


def test_list_events_in_window(client):
    for i in range(3):
        client.post("/agenda/events", json={
            "titre": f"Ev{i}",
            "debut": f"2026-09-0{i+1}T10:00:00",
        })
    r = client.get("/agenda/events?from=2026-09-01T00:00:00&to=2026-09-04T00:00:00&include_training=false")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_update_event(client):
    r = client.post("/agenda/events", json={"titre": "Old", "debut": "2026-09-15T09:00:00"})
    ev_id = r.json()["id"]
    r2 = client.patch(f"/agenda/events/{ev_id}", json={"titre": "New"})
    assert r2.status_code == 200
    assert r2.json()["titre"] == "New"


def test_delete_event(client):
    r = client.post("/agenda/events", json={"titre": "To delete", "debut": "2026-09-20T09:00:00"})
    ev_id = r.json()["id"]
    r2 = client.delete(f"/agenda/events/{ev_id}")
    assert r2.status_code == 204
    r3 = client.delete(f"/agenda/events/{ev_id}")
    assert r3.status_code == 404


# ── Recurrence CRUD ───────────────────────────────────────────────────────────

def test_create_recurrence_rule(client):
    payload = {
        "titre": "INF1000",
        "weekdays": [0, 2, 4],
        "start_time": "09:00",
        "end_time": "12:00",
        "categorie": "cours",
    }
    r = client.post("/agenda/recurrences", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["titre"] == "INF1000"
    assert data["weekdays"] == [0, 2, 4]


def test_recurrences_expand_in_events(client):
    """Une règle lun-mer-ven doit générer des occurrences dans GET /events."""
    client.post("/agenda/recurrences", json={
        "titre": "Cours", "weekdays": [0], "start_time": "09:00", "end_time": "12:00",
    })
    # Semaine du 7 au 13 sept 2026 (lundi = 7)
    r = client.get(
        "/agenda/events?from=2026-09-07T00:00:00&to=2026-09-14T00:00:00"
        "&include_recurrences=true&include_training=false"
    )
    events = r.json()
    virtual = [e for e in events if e["is_virtual"]]
    assert len(virtual) >= 1
    assert virtual[0]["titre"] == "Cours"


def test_delete_recurrence_rule(client):
    r = client.post("/agenda/recurrences", json={
        "titre": "Shift", "weekdays": [5], "start_time": "10:00", "end_time": "18:00",
    })
    rule_id = r.json()["id"]
    r2 = client.delete(f"/agenda/recurrences/{rule_id}")
    assert r2.status_code == 204


# ── Tâches CRUD ───────────────────────────────────────────────────────────────

def test_create_task(client):
    r = client.post("/agenda/tasks", json={
        "titre": "Remettre devoir INF1000",
        "deadline": "2026-09-20",
        "priorite": 2,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["statut"] == "todo"
    assert data["priorite"] == 2


def test_tasks_sorted_by_priority(client):
    for p in [5, 1, 3]:
        client.post("/agenda/tasks", json={"titre": f"T{p}", "priorite": p})
    r = client.get("/agenda/tasks")
    tasks = r.json()
    prios = [t["priorite"] for t in tasks]
    assert prios == sorted(prios)


def test_mark_task_done(client):
    r = client.post("/agenda/tasks", json={"titre": "À faire"})
    task_id = r.json()["id"]
    r2 = client.post(f"/agenda/tasks/{task_id}/done")
    assert r2.status_code == 200
    assert r2.json()["statut"] == "done"


def test_delete_task(client):
    r = client.post("/agenda/tasks", json={"titre": "Ephémère"})
    task_id = r.json()["id"]
    assert client.delete(f"/agenda/tasks/{task_id}").status_code == 204
    assert client.delete(f"/agenda/tasks/{task_id}").status_code == 404


# ── Slots libres ──────────────────────────────────────────────────────────────

def test_slots_empty_day(client):
    """Jour sans événement → un seul grand slot."""
    r = client.get("/agenda/slots?date=2026-09-07&min_duration=60")
    assert r.status_code == 200
    slots = r.json()
    assert len(slots) >= 1
    assert slots[0]["duree_min"] >= 60


def test_slots_with_event(client):
    """Un événement doit réduire les slots disponibles."""
    client.post("/agenda/events", json={
        "titre": "Cours",
        "debut": "2026-09-08T09:00:00",
        "fin": "2026-09-08T12:00:00",
    })
    r = client.get("/agenda/slots?date=2026-09-08&min_duration=60")
    slots = r.json()
    # Aucun slot ne doit chevaucher 9h-12h
    for s in slots:
        s_start = dt.datetime.fromisoformat(s["debut"])
        s_end = dt.datetime.fromisoformat(s["fin"])
        assert not (s_start < dt.datetime(2026, 9, 8, 12) and s_end > dt.datetime(2026, 9, 8, 9))


# ── Today ─────────────────────────────────────────────────────────────────────

def test_today_endpoint(client):
    r = client.get("/agenda/today")
    assert r.status_code == 200
    data = r.json()
    assert "date" in data
    assert "evenements" in data
    assert "slots_libres" in data
    assert "taches_urgentes" in data
