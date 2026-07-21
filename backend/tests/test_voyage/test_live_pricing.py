from __future__ import annotations

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.services.voyage.live_pricing import fetch_live_itinerary


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class FakeResponse:
    status_code = 201

    def json(self):
        return {"data": {"offers": [
            {
                "total_amount": "780.00", "total_currency": "EUR",
                "slices": [
                    {"duration": "PT7H30M", "segments": [{
                        "operating_carrier": {"name": "Air Test"},
                    }]},
                    {"duration": "PT8H", "segments": [{
                        "operating_carrier": {"name": "Air Test"},
                    }]},
                ],
            },
        ]}}


def test_live_multi_city_price_is_cached(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    slices = [
        {"origin": "YUL", "destination": "CDG", "departure_date": "2026-09-01"},
        {"origin": "CDG", "destination": "YUL", "departure_date": "2026-09-10"},
    ]
    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    now = dt.datetime(2026, 7, 19, tzinfo=dt.timezone.utc)
    first = fetch_live_itinerary(session, slices, http_post=post, now=now)
    second = fetch_live_itinerary(session, slices, http_post=post, now=now)
    assert first == {
        "prix": 780.0, "duree_min": 930,
        "transporteur": "Air Test", "source": "live",
    }
    assert second["source"] == "cache_live"
    assert len(calls) == 1


def test_live_pricing_disabled_without_key(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "")
    assert fetch_live_itinerary(session, [{
        "origin": "YUL", "destination": "CDG", "departure_date": "2026-09-01",
    }]) is None
