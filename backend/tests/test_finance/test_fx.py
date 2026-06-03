"""Taux de change avec cache quotidien."""

from __future__ import annotations

import datetime as dt

from app.services.finance import fx


def test_same_currency_is_one():
    assert fx.get_rate("EUR", "EUR") == 1.0


def test_rate_cached_same_day():
    fx.clear_cache()
    calls = []

    def fake(b, q):
        calls.append((b, q))
        return 1.1 if (b, q) == ("EUR", "USD") else None

    day = dt.date(2026, 6, 3)
    assert fx.get_rate("EUR", "USD", fetcher=fake, today=day) == 1.1
    assert fx.get_rate("EUR", "USD", fetcher=fake, today=day) == 1.1
    assert len(calls) == 1  # un seul appel le même jour


def test_convert():
    fx.clear_cache()
    r = fx.convert(100.0, "EUR", "USD", fetcher=lambda b, q: 1.1, today=dt.date(2026, 6, 3))
    assert r == 110.0


def test_fallback_inverse():
    fx.clear_cache()

    def fake(b, q):
        # seul USD->EUR connu = 0.5 ; EUR->USD doit être déduit = 2.0
        return 0.5 if (b, q) == ("USD", "EUR") else None

    r = fx.get_rate("EUR", "USD", fetcher=fake, today=dt.date(2026, 6, 3))
    assert r == 2.0
