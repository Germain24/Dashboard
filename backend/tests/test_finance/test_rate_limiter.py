"""Rate limiter Buffett : réservation correcte + concurrence réelle (fix lenteur)."""

from __future__ import annotations

import threading
import time

from app.services.finance.buffett.rate_limiter import RateLimiter


def test_reserves_tokens_per_ticker():
    rl = RateLimiter(max_requests_per_hour=8, requests_per_ticker=4)
    rl.wait_for_slot()
    rl.wait_for_slot()
    assert len(rl.request_timestamps) == 8


def test_concurrent_calls_do_not_serialize():
    """Avec une capacité ample, N appels concurrents finissent quasi instantanément
    (l'ancien code sérialisait à ~min_interval par ticker en tenant le verrou)."""
    rl = RateLimiter(max_requests_per_hour=400, requests_per_ticker=4)
    n = 20
    start = time.time()
    threads = [threading.Thread(target=rl.wait_for_slot) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start
    assert len(rl.request_timestamps) == n * 4  # tous les jetons réservés
    assert elapsed < 1.0  # pas de sérialisation 7,2 s/ticker


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
    # Reprise estimée ≈ (plus ancien jeton + 3600).
    assert abs(rl.paused_until - (1000.0 + 3600.0 + 0.1)) < 1.0


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
