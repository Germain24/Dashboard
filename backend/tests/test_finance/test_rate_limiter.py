"""Rate limiter Buffett : réservation correcte + concurrence réelle (fix lenteur)."""

from __future__ import annotations

import threading
import time

from app.services.finance.buffett.rate_limiter import RateLimiter


def test_reserves_tokens_per_ticker():
    # On avance le temps de min_interval entre les deux tickers : l'espacement
    # est respecté, donc les 8 jetons sont bien réservés.
    rl = RateLimiter(max_requests_per_hour=8, requests_per_ticker=4)
    assert rl._try_reserve(now=0.0) is None
    assert rl._try_reserve(now=rl.min_interval) is None
    assert len(rl.request_timestamps) == 8


def test_smooths_requests_at_min_interval():
    """Lissage à 2000 req/h : deux tickers consécutifs sont espacés d'au moins
    min_interval (= 3600 / (2000/4) = 7,2 s) pour ne pas saturer en rafale."""
    rl = RateLimiter(max_requests_per_hour=2000, requests_per_ticker=4)
    assert abs(rl.min_interval - 7.2) < 0.01
    assert rl._try_reserve(now=1000.0) is None  # 1er ticker : réservé
    wait = rl._try_reserve(now=1000.0)          # immédiat -> doit attendre
    assert wait is not None
    assert abs(wait - rl.min_interval) < 0.5
    # Après l'intervalle, le créneau se libère.
    assert rl._try_reserve(now=1000.0 + rl.min_interval) is None


def test_blocks_when_hourly_cap_reached():
    rl = RateLimiter(max_requests_per_hour=4, requests_per_ticker=4)
    rl.wait_for_slot()  # remplit le plafond
    assert len(rl.request_timestamps) == 4

    done = threading.Event()
    threading.Thread(target=lambda: (rl.wait_for_slot(), done.set()), daemon=True).start()
    # Plus de capacité -> le 2e appel dort (hors verrou) et ne termine pas tout de suite.
    assert not done.wait(timeout=0.4)


def test_paused_until_set_when_cap_reached_and_cleared_on_reserve():
    """_try_reserve expose l'état de pause (#193) : reprise estimée quand plein."""
    rl = RateLimiter(max_requests_per_hour=4, requests_per_ticker=4)
    # 1er ticker : créneau libre -> réservé, pas de pause.
    assert rl._try_reserve(now=1000.0) is None
    assert rl.paused_until is None
    # 2e ticker : plafond atteint -> délai d'attente + paused_until renseigné.
    sleep_time = rl._try_reserve(now=1000.5)
    assert sleep_time is not None and sleep_time > 0
    assert rl.paused_until is not None
    # L'attente théorique (~3600 s) est bornée à max_pause_seconds (120 s par
    # défaut) : on re-tentera plutôt que d'attendre une heure d'un coup.
    assert sleep_time <= rl.max_pause_seconds
    assert abs(rl.paused_until - (1000.5 + rl.max_pause_seconds)) < 1.0


def test_pause_is_capped_at_max():
    """La pause ne dépasse jamais max_pause_seconds, même quota grand ouvert."""
    rl = RateLimiter(max_requests_per_hour=4, requests_per_ticker=4, max_pause_seconds=60.0)
    rl._try_reserve(now=5000.0)            # remplit le plafond
    sleep_time = rl._try_reserve(now=5000.1)  # plein -> pause
    assert sleep_time is not None
    assert sleep_time <= 60.0


def test_active_limiter_registry_exposes_pause():
    from app.services.finance.buffett.rate_limiter import (
        active_paused_until, set_active_limiter,
    )
    assert active_paused_until() is None  # aucune analyse
    rl = RateLimiter(max_requests_per_hour=4, requests_per_ticker=4)
    rl._try_reserve(now=2000.0)
    rl._try_reserve(now=2000.5)  # déclenche la pause
    set_active_limiter(rl)
    try:
        assert active_paused_until() == rl.paused_until
    finally:
        set_active_limiter(None)
    assert active_paused_until() is None
