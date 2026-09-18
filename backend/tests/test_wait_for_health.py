"""Script healthcheck (#198) : attend /health avant de continuer."""

from __future__ import annotations

from scripts.wait_for_health import wait_for_health


def test_returns_true_as_soon_as_ready():
    calls = {"n": 0}

    def ready(_url):
        calls["n"] += 1
        return calls["n"] >= 3  # prêt au 3e essai

    slept: list[float] = []
    ok = wait_for_health("u", timeout=60, interval=0.5, ready=ready, sleep=slept.append)
    assert ok is True
    assert calls["n"] == 3
    assert slept == [0.5, 0.5]  # a attendu entre les 2 premiers échecs


def test_times_out_when_never_ready():
    clock = {"t": 0.0}

    def fake_now():
        clock["t"] += 1.0
        return clock["t"]

    ok = wait_for_health(
        "u", timeout=2, interval=0.1,
        ready=lambda _u: False, sleep=lambda _s: None, now=fake_now,
    )
    assert ok is False


def test_is_ready_handles_connection_error():
    from scripts.wait_for_health import is_ready

    def boom(*_a, **_k):
        raise ConnectionError("refused")

    assert is_ready("http://x", opener=boom) is False
