"""Cadence Yahoo : 2 000 requêtes réelles par heure."""

from __future__ import annotations

import pytest

from app.services.finance.buffett.rate_limiter import RateLimiter


def test_2000_per_hour_means_1_8_seconds_between_requests():
    limiter = RateLimiter(requests_per_hour=2000)
    assert limiter.min_interval_seconds == pytest.approx(1.8)
    assert limiter._try_reserve(now=1000.0) is None
    assert limiter._try_reserve(now=1000.0) == pytest.approx(1.8)
    assert limiter._try_reserve(now=1001.79) == pytest.approx(0.01)
    assert limiter._try_reserve(now=1001.8) is None


def test_wait_for_slot_sleeps_outside_lock_until_next_slot(monkeypatch):
    limiter = RateLimiter(requests_per_hour=2000)
    clock = {"value": 1000.0}
    sleeps: list[float] = []
    monkeypatch.setattr(
        "app.services.finance.buffett.rate_limiter.time.monotonic",
        lambda: clock["value"],
    )

    def advance(seconds):
        sleeps.append(seconds)
        clock["value"] += seconds

    monkeypatch.setattr(
        "app.services.finance.buffett.rate_limiter.time.sleep",
        advance,
    )
    limiter.wait_for_slot()
    limiter.wait_for_slot()
    assert sleeps == [pytest.approx(1.8)]
    assert limiter.request_timestamps == [1000.0, 1001.8]
    assert limiter.http_requests == 2


def test_429_is_counted_without_exponential_pause():
    limiter = RateLimiter(requests_per_hour=2000)
    assert limiter.record_remote_rate_limit() == 0.0
    assert limiter.record_remote_rate_limit() == 0.0
    assert limiter.deferred_rate_limits == 2
    assert limiter.remote_rate_limited is False
    assert limiter.paused_until is None


def test_remote_recovery_compatibility_method_never_sleeps(monkeypatch):
    limiter = RateLimiter(requests_per_hour=2000)
    monkeypatch.setattr(
        "app.services.finance.buffett.rate_limiter.time.sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("pause interdite")),
    )
    limiter.record_remote_rate_limit()
    limiter.wait_for_remote_recovery()
    assert limiter.request_timestamps == []


def test_legacy_per_minute_constructor_is_converted_to_equivalent_hourly_rate():
    limiter = RateLimiter(max_requests_per_minute=10)
    assert limiter.requests_per_hour == 600
    assert limiter.min_interval_seconds == pytest.approx(6.0)


def test_active_limiter_does_not_report_normal_spacing_as_pause():
    from app.services.finance.buffett.rate_limiter import (
        active_paused_until,
        set_active_limiter,
    )

    limiter = RateLimiter(requests_per_hour=2000)
    limiter._try_reserve(now=2000.0)
    limiter._try_reserve(now=2000.5)
    set_active_limiter(limiter)
    try:
        assert active_paused_until() is None
    finally:
        set_active_limiter(None)
