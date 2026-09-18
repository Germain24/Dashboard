"""API /cuisine/meal-plan/generate : les cibles macros omises viennent de Santé.

`GeneratePlanRequest.cibles` avait pour défaut un profil générique codé en dur
(2500 kcal / 180 g de protéines). L'utilisateur pèse ~57 kg : tout appel qui
omettait `cibles` planifiait donc les repas sur les macros de quelqu'un d'autre,
silencieusement. L'UI passe bien les vraies cibles (`/sante/targets/today`), mais
le défaut restait un piège pour tout autre appelant.

Les cibles omises sont désormais dérivées de `calculate_daily_targets` (même
source que Santé) à partir du dernier poids connu.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(name="client")
def client_fixture(session):
    app_ = create_app()
    app_.dependency_overrides[get_session] = lambda: session
    with TestClient(app_) as c:
        yield c


def _cibles_utilisees(monkeypatch):
    """Capture les cibles réellement passées au générateur de plan."""
    vues: dict = {}
    from app.services.cuisine import meal_plan as mp

    def _fake(session, semaine, cibles):
        vues.update(cibles)
        return []

    monkeypatch.setattr(mp, "generate_meal_plan", _fake)
    from app.api.cuisine import planning

    monkeypatch.setattr(planning.plan_svc, "generate_meal_plan", _fake)
    return vues


def test_cibles_omises_derivees_du_poids_reel(client, session, monkeypatch):
    """Sans `cibles`, on utilise les cibles Santé du dernier poids connu."""
    from app.models.sante import MesureSante
    from app.services.sante.targets import calculate_daily_targets

    session.add(MesureSante(date=dt.date(2026, 7, 19), poids=57.0))
    session.commit()

    vues = _cibles_utilisees(monkeypatch)
    r = client.post("/api/v1/cuisine/meal-plan/generate", json={"semaine": "2026-W30"})

    assert r.status_code == 200, r.text
    _, comp = calculate_daily_targets(57.0, dt.date.today())
    assert vues["calories"] == pytest.approx(comp["Calories"], rel=1e-6)
    assert vues["proteines"] == pytest.approx(comp["Protéines"], rel=1e-6)
    # Le profil générique codé en dur ne doit plus jamais apparaître.
    assert vues["calories"] != 2500
    assert vues["proteines"] != 180


def test_cibles_explicites_respectees(client, session, monkeypatch):
    """Des cibles fournies explicitement priment (comportement de l'UI)."""
    vues = _cibles_utilisees(monkeypatch)
    cibles = {"calories": 1900, "proteines": 140, "glucides": 200, "lipides": 60}

    r = client.post(
        "/api/v1/cuisine/meal-plan/generate",
        json={"semaine": "2026-W30", "cibles": cibles},
    )

    assert r.status_code == 200, r.text
    assert vues["calories"] == 1900
    assert vues["proteines"] == 140


def test_sans_poids_connu_erreur_explicite(client, session, monkeypatch):
    """Aucun poids en base + aucune cible fournie -> 400 explicite.

    Mieux vaut refuser que planifier sur un profil inventé.
    """
    _cibles_utilisees(monkeypatch)
    r = client.post("/api/v1/cuisine/meal-plan/generate", json={"semaine": "2026-W30"})

    assert r.status_code == 400
    assert "poids" in r.text.lower()
