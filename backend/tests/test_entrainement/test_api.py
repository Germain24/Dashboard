"""Tests d'intégration sur les routes /entrainement/*.

DB SQLite isolée par test, client FastAPI avec override de get_session.
"""

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


def test_ping_ready(client):
    r = client.get("/entrainement/ping")
    assert r.status_code == 200
    assert r.json() == {"module": "entrainement", "ready": True}


def test_seed_exercices_robust_to_race_condition(client):
    """Régression : deux GET /exercises en parallèle ne doivent pas faire 500.

    Bug observé en prod (logs Germain 2026-05-20) : React strict mode + Next.js
    dev déclenche deux requêtes /exercises quasi simultanées. Le 1er seed
    réussit, le 2e voyait la table vide entre son SELECT et son COMMIT et
    plantait avec UNIQUE constraint failed: exercice.nom.

    Fix : try/except IntegrityError + rollback dans seed_exercices.
    """
    from concurrent.futures import ThreadPoolExecutor

    # Avec un TestClient, FastAPI exécute chaque requête sur un thread du pool
    # anyio. On lance 3 requêtes concurrentes : la première peuple la table,
    # les deux autres doivent retomber sur ses pieds (rollback silencieux).
    def _hit():
        r = client.get("/entrainement/exercises")
        return r.status_code, len(r.json()) if r.status_code == 200 else 0

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda _: _hit(), range(4)))

    # Aucune requête ne doit avoir 500
    statuses = [s for s, _ in results]
    assert all(s == 200 for s in statuses), f"Statuses: {statuses}"
    # Toutes voient la table seedée (au moins 30 exos)
    counts = [n for _, n in results]
    assert all(n >= 30 for n in counts), f"Counts: {counts}"


def test_list_exercises_seeds_catalogue(client):
    r = client.get("/entrainement/exercises")
    assert r.status_code == 200
    rows = r.json()
    # Le seed contient au moins 30 exos clés
    assert len(rows) >= 30
    noms = {e["nom"] for e in rows}
    assert "Squat barre" in noms
    assert "Développé couché barre" in noms
    assert "Course à pied" in noms


def test_filter_exercises_by_categorie(client):
    r = client.get("/entrainement/exercises?categorie=legs")
    assert r.status_code == 200
    rows = r.json()
    assert all(e["categorie"] == "legs" for e in rows)
    assert len(rows) >= 5


def test_create_custom_exercise(client):
    r = client.post(
        "/entrainement/exercises",
        json={"nom": "Hack squat Garmin", "categorie": "legs", "muscles": ["quadriceps"], "source": "garmin"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["source"] == "garmin"
    assert data["nom"] == "Hack squat Garmin"


def test_program_autocreated(client):
    r = client.get("/entrainement/program")
    assert r.status_code == 200
    prog = r.json()
    assert prog["actif"] is True
    assert prog["nom"] == "PPL/UL"
    labels_by_weekday = {j["weekday"]: j["label"] for j in prog["jours"]}
    assert labels_by_weekday[0] == "Push"
    assert labels_by_weekday[2] == "Legs"
    assert labels_by_weekday[3] == "Repos"
    assert labels_by_weekday[6] == "Repos"


def test_program_day_patch(client):
    client.get("/entrainement/program")  # autocrée
    r = client.patch(
        "/entrainement/program/jours/0",
        json={"label": "Push lourd", "slots": [{"exercice_id": 1, "sets_target": 4}]},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["label"] == "Push lourd"
    assert j["slots"][0]["sets_target"] == 4


def test_session_create_with_sets(client):
    # Récupère un exercice du seed
    ex = client.get("/entrainement/exercises").json()
    bench_id = next(e["id"] for e in ex if "Développé couché barre" in e["nom"])
    payload = {
        "date": dt.datetime(2026, 5, 18, 18, 0).isoformat(),
        "type": "push",
        "duree_min": 50,
        "sets": [
            {"exercice_id": bench_id, "reps": 5, "poids_kg": 60.0, "rpe": 8.0},
            {"exercice_id": bench_id, "reps": 5, "poids_kg": 65.0, "rpe": 9.0},
        ],
    }
    r = client.post("/entrainement/sessions", json=payload)
    assert r.status_code == 201
    s = r.json()
    assert len(s["sets"]) == 2
    assert s["sets"][0]["ordre"] == 0
    assert s["sets"][1]["ordre"] == 1
    # #108 : tonnage total = 5×60 + 5×65 = 625 kg
    assert s["tonnage_kg"] == 625.0
    # #111 : RPE moyen de la séance = (8 + 9) / 2 = 8.5
    assert s["rpe_moyen"] == 8.5


def test_progression_endpoint(client):
    ex = client.get("/entrainement/exercises").json()
    sq_id = next(e["id"] for e in ex if "Squat barre" == e["nom"])
    # Log une séance avec une bonne série
    today = dt.datetime.utcnow().isoformat()
    client.post(
        "/entrainement/sessions",
        json={
            "date": today,
            "type": "legs",
            "duree_min": 50,
            "sets": [{"exercice_id": sq_id, "reps": 5, "poids_kg": 100.0}],
        },
    )
    r = client.get(f"/entrainement/progression/{sq_id}")
    assert r.status_code == 200
    p = r.json()
    assert p["current_1rm_kg"] > 100  # Epley > poids brut


def test_one_rm_endpoint(client):
    ex = client.get("/entrainement/exercises").json()
    bench_id = next(e["id"] for e in ex if "Développé couché barre" in e["nom"])
    r = client.get(f"/entrainement/1rm/{bench_id}")
    assert r.status_code == 200
    assert r.json()["formula"] == "epley"


def test_cardio_create_and_list(client):
    today = dt.date.today().isoformat()
    r = client.post(
        "/entrainement/cardio",
        json={"date": today, "distance_km": 5.0, "duree_sec": 1500},
    )
    assert r.status_code == 201
    c = r.json()
    assert c["distance_km"] == 5.0
    assert c["pace_str"] == "5:00/km"

    r2 = client.get("/entrainement/cardio")
    assert r2.status_code == 200
    rows = r2.json()
    assert any(row["distance_km"] == 5.0 for row in rows)


def test_intensity_for_date_endpoint_contract(client):
    """Contrat figé : retour {date, intensity in none/low/medium/high}."""
    r = client.get("/entrainement/intensity/2026-05-21")  # jeudi
    assert r.status_code == 200
    data = r.json()
    assert data["date"] == "2026-05-21"
    assert data["intensity"] in ("none", "low", "medium", "high")
    assert data["intensity"] == "none"  # jeudi = repos par défaut


def test_intensity_today_endpoint(client):
    r = client.get("/entrainement/intensity/today")
    assert r.status_code == 200
    data = r.json()
    assert data["intensity"] in ("none", "low", "medium", "high")
    assert data["date"] == dt.date.today().isoformat()


def test_intensity_program_overrides_default(client):
    """Sans programme : jeudi = none. Avec programme actif où jeudi='Push' → medium."""
    client.get("/entrainement/program")  # autocrée
    # Force jeudi (weekday=3) en Push
    client.patch("/entrainement/program/jours/3", json={"label": "Push"})
    r = client.get("/entrainement/intensity/2026-05-21")  # jeudi
    assert r.json()["intensity"] == "medium"


def test_intensity_session_overrides_program(client):
    """Séance loggée prime sur le label du programme."""
    client.get("/entrainement/program")
    # Force jeudi en Repos
    client.patch("/entrainement/program/jours/3", json={"label": "Repos"})

    ex = client.get("/entrainement/exercises").json()
    bench_id = next(e["id"] for e in ex if "Développé couché barre" in e["nom"])
    client.post(
        "/entrainement/sessions",
        json={
            "date": dt.datetime(2026, 5, 21, 18, 0).isoformat(),  # jeudi
            "type": "push",
            "duree_min": 50,
            "sets": [{"exercice_id": bench_id, "reps": 5, "poids_kg": 60.0}],
        },
    )
    r = client.get("/entrainement/intensity/2026-05-21")
    # Séance 50 min normale → medium (même si le programme dit Repos)
    assert r.json()["intensity"] == "medium"
