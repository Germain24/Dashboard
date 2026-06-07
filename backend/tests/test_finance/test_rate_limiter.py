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
