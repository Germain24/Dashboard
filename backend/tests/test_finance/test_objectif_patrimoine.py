"""Objectifs patrimoniaux indépendants : liberté financière et Japon."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api.finance import objectif as objectif_api
from app.core.db import get_session
from app.main import create_app
from app.services.finance import patrimoine


@pytest.fixture(name="client")
def client_fixture(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    preferences = {
        "objectif_patrimoine_eur": 300_000,
        "objectif_japon_eur": 8_000,
        "objectif_japon_date": "2028-01-11",
        "objectif_japon_date_reference": date.today().isoformat(),
    }

    monkeypatch.setattr(objectif_api, "get_preferences", lambda: dict(preferences))

    def update_preferences(patch):
        preferences.update(patch)
        return dict(preferences)

    monkeypatch.setattr(objectif_api, "set_preferences", update_preferences)
    monkeypatch.setattr(patrimoine, "financial_freedom_value_eur", lambda _session: 42_000)
    monkeypatch.setattr(patrimoine, "bank_account_value_eur", lambda _session: 1_500)

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client


def test_objectifs_have_separate_values_and_deadlines(client):
    response = client.get("/finance/objectif-patrimoine")

    assert response.status_code == 200
    liberte, japon = response.json()["objectifs"]
    assert liberte == {
        "id": "liberte_financiere",
        "label": "Liberté financière",
        "objectif_eur": 300_000,
        "valeur_eur": 42_000,
        "progression_pct": 14.0,
        "restant_eur": 258_000,
        "atteint": False,
        "echeance": None,
        "jours_restants": None,
        "epargne_journaliere_eur": None,
    }
    assert japon["id"] == "japon"
    assert japon["valeur_eur"] == 1_500
    assert japon["echeance"] == "2028-01-11"
    assert japon["epargne_journaliere_eur"] > 0


def test_updating_japan_does_not_change_financial_freedom(client):
    response = client.post(
        "/finance/objectif-patrimoine",
        json={
            "id": "japon",
            "objectif_eur": 10_000,
            "echeance": "2028-09-15",
        },
    )

    assert response.status_code == 200
    liberte, japon = response.json()["objectifs"]
    assert liberte["objectif_eur"] == 300_000
    assert liberte["valeur_eur"] == 42_000
    assert japon["objectif_eur"] == 10_000
    assert japon["valeur_eur"] == 1_500
    assert japon["echeance"] == "2028-09-15"


def test_japan_countdown_is_recomputed_each_day():
    day_one = objectif_api._progression(
        goal_id="japon",
        label="Voyage au Japon",
        objectif=12_000,
        valeur=3_000,
        echeance=date(2028, 1, 11),
        aujourdhui=date(2026, 7, 28),
    )
    day_two = objectif_api._progression(
        goal_id="japon",
        label="Voyage au Japon",
        objectif=12_000,
        valeur=3_000,
        echeance=date(2028, 1, 11),
        aujourdhui=date(2026, 7, 29),
    )

    assert day_two.jours_restants == day_one.jours_restants - 1
    assert day_two.restant_eur == day_one.restant_eur
    assert day_two.epargne_journaliere_eur > day_one.epargne_journaliere_eur


def test_japan_target_loses_one_initial_daily_share_each_day():
    reference = date(2025, 1, 1)
    deadline = date(2027, 3, 12)  # exactement 800 jours après la référence

    day_one = objectif_api._japan_target_for_day(
        initial_target=80_000,
        deadline=deadline,
        reference_date=reference,
        today=date(2025, 1, 2),
    )
    day_two = objectif_api._japan_target_for_day(
        initial_target=80_000,
        deadline=deadline,
        reference_date=reference,
        today=date(2025, 1, 3),
    )

    assert day_one == 79_900
    assert day_two == 79_800

    progression_one = objectif_api._progression(
        goal_id="japon",
        label="Voyage au Japon",
        objectif=day_one,
        valeur=10_000,
        echeance=deadline,
        aujourdhui=date(2025, 1, 2),
    )
    progression_two = objectif_api._progression(
        goal_id="japon",
        label="Voyage au Japon",
        objectif=day_two,
        valeur=10_000,
        echeance=deadline,
        aujourdhui=date(2025, 1, 3),
    )
    assert progression_two.epargne_journaliere_eur < progression_one.epargne_journaliere_eur
