"""Rate limiter pour les requêtes yfinance — lissage + protection burst."""

from __future__ import annotations

import threading
import time

from .config import Config


class RateLimiter:
    """Limite les requêtes à MAX_REQUESTS_PER_HOUR en lissant le débit.

    Deux niveaux de protection :
    1. Steady pace : délai minimum entre deux tickers.
    2. Burst protection : fenêtre glissante d'1 heure.
    """

    def __init__(
        self,
        max_requests_per_hour: int = Config.MAX_REQUESTS_PER_HOUR,
        requests_per_ticker: int = Config.REQUESTS_PER_TICKER,
    ) -> None:
        self.max_requests_per_hour = max_requests_per_hour
        self.requests_per_ticker = requests_per_ticker
        self.request_timestamps: list[float] = []
        self.lock = threading.Lock()
        # Délai théorique pour une répartition uniforme sur 1 h
        self.min_interval = 3600.0 / (max_requests_per_hour / requests_per_ticker)
        self.last_ticker_time: float = 0.0

    def wait_for_slot(self) -> None:
        """Bloque jusqu'à ce qu'un slot soit disponible."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_ticker_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)

            while True:
                now = time.time()
                cutoff = now - 3600.0
                self.request_timestamps = [
                    t for t in self.request_timestamps if t > cutoff
                ]
                capacity = self.max_requests_per_hour - len(self.request_timestamps)
                if capacity >= self.requests_per_ticker:
                    for _ in range(self.requests_per_ticker):
                        self.request_timestamps.append(now)
                    self.last_ticker_time = now
                    return

                # Attendre que le plus vieux jeton expire
                sleep_time = (self.request_timestamps[0] + 3600.0) - now + 0.1
                time.sleep(max(sleep_time, 1.0))
