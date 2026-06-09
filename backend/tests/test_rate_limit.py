"""Rate limiting inbound (#193) : fenêtre glissante + dépendance 429."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import SlidingWindowLimiter, rate_limit


def test_allows_up_to_max_then_blocks():
    lim = SlidingWindowLimiter(max_calls=3, window_s=60)
    assert lim.allow("a", now=0.0)
    assert lim.allow("a", now=0.1)
    assert lim.allow("a", now=0.2)
    assert not lim.allow("a", now=0.3)  # 4e dans la fenêtre -> refusé


def test_window_slides_and_frees_slots():
    lim = SlidingWindowLimiter(max_calls=1, window_s=10)
    assert lim.allow("a", now=0.0)
    assert not lim.allow("a", now=5.0)   # encore dans la fenêtre
    assert lim.allow("a", now=11.0)      # fenêtre passée -> ok


def test_keys_are_independent():
    lim = SlidingWindowLimiter(max_calls=1, window_s=60)
    assert lim.allow("a", now=0.0)
    assert lim.allow("b", now=0.0)       # autre clé, pas impactée
    assert not lim.allow("a", now=0.0)


def test_dependency_returns_429_when_exceeded():
    app = FastAPI()

    @app.get("/x", dependencies=[Depends(rate_limit(max_calls=2, window_s=60, name="x"))])
    def x():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    r = client.get("/x")
    assert r.status_code == 429
    assert "Retry-After" in r.headers
