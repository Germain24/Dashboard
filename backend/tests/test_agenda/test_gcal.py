"""Google Calendar — conversions pures + garde-fous (#83)."""

from __future__ import annotations

import datetime as dt

from app.services.agenda import gcal


def test_is_configured_false_by_default(monkeypatch):
    # Hermétique : on force l'absence d'identifiants Google, sinon le test
    # dépend du .env réel du poste (où l'intégration peut être active).
    monkeypatch.setattr(gcal.settings, "google_client_id", "", raising=False)
    monkeypatch.setattr(gcal.settings, "google_client_secret", "", raising=False)
    monkeypatch.setattr(gcal.settings, "google_refresh_token", "", raising=False)
    assert gcal.is_configured() is False


def test_gcal_to_evenement_timed():
    g = {
        "id": "abc123",
        "summary": "Cours INF",
        "location": "PK-1140",
        "description": "Salle info",
        "start": {"dateTime": "2026-06-03T09:00:00-04:00"},
        "end": {"dateTime": "2026-06-03T10:30:00-04:00"},
    }
    ev = gcal.gcal_to_evenement(g)
    assert ev["titre"] == "Cours INF"
    assert ev["debut"] == dt.datetime(2026, 6, 3, 9, 0)
    assert ev["fin"] == dt.datetime(2026, 6, 3, 10, 30)
    assert ev["source"] == "gcal"
    assert ev["source_id"] == "abc123"


def test_gcal_to_evenement_all_day():
    g = {"id": "x", "summary": "Congé", "start": {"date": "2026-06-03"}, "end": {"date": "2026-06-04"}}
    ev = gcal.gcal_to_evenement(g)
    assert ev["debut"] == dt.datetime(2026, 6, 3, 0, 0)


def test_evenement_to_gcal_roundtrip_fields():
    ev = {
        "titre": "Réunion",
        "debut": dt.datetime(2026, 6, 3, 14, 0),
        "fin": dt.datetime(2026, 6, 3, 15, 0),
        "lieu": "Zoom",
    }
    body = gcal.evenement_to_gcal(ev)
    assert body["summary"] == "Réunion"
    assert body["start"]["dateTime"].startswith("2026-06-03T14:00:00")
    assert body["end"]["dateTime"].startswith("2026-06-03T15:00:00")
    assert body["location"] == "Zoom"


def test_evenement_to_gcal_defaults_one_hour():
    ev = {"titre": "X", "debut": dt.datetime(2026, 6, 3, 9, 0), "fin": None}
    body = gcal.evenement_to_gcal(ev)
    assert body["end"]["dateTime"].startswith("2026-06-03T10:00:00")
