"""Client Duffel — prix/durée de vol avec cache DB."""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.models.voyage import DuffelPriceCache
from app.services.voyage.duffel_client import fetch_offer


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


_OFFERS_PAYLOAD = {
    "data": {
        "offers": [
            {"total_amount": "500.00", "total_currency": "USD",
             "slices": [{"duration": "PT10H0M"}]},
            {"total_amount": "375.78", "total_currency": "USD",  # moins cher -> retenu
             "slices": [{"duration": "PT14H23M"}]},
        ]
    }
}


def test_fetch_offer_returns_cheapest_and_caches(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(201, _OFFERS_PAYLOAD)

    result = fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=fake_post)

    assert result == {"prix": 375.78, "devise": "USD", "duree_min": 863}
    assert len(calls) == 1

    # deuxième appel : servi depuis le cache, pas de nouvel appel HTTP
    result2 = fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=fake_post)
    assert result2 == result
    assert len(calls) == 1

    cached = session.get(DuffelPriceCache, "YUL|NRT|2026-09-01")
    assert cached is not None
    assert cached.duree_min == 863


def test_fetch_offer_returns_none_without_api_key(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "")
    assert fetch_offer(session, "YUL", "NRT", "2026-09-01", http_post=lambda *a, **k: None) is None


def test_fetch_offer_returns_none_on_error_status(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    result = fetch_offer(session, "YUL", "XXX", "2026-09-01",
                          http_post=lambda *a, **k: _FakeResponse(422, {"errors": []}))
    assert result is None


def test_fetch_offer_returns_none_when_no_offers(session, monkeypatch):
    monkeypatch.setattr(settings, "duffel_api_key", "duffel_test_fake")
    result = fetch_offer(session, "YUL", "XXX", "2026-09-01",
                          http_post=lambda *a, **k: _FakeResponse(201, {"data": {"offers": []}}))
    assert result is None
