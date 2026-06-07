"""Rate limiter pour les requêtes yfinance — plafond horaire glissant, concurrent."""

from __future__ import annotations

import threading
import time

from .config import Config


class RateLimiter:
    """Limite les requêtes à MAX_REQUESTS_PER_HOUR via une fenêtre glissante d'1 h.

    Conçu pour un pool de workers : la réservation des jetons est protégée par un
    verrou, mais aucun `sleep` n'est tenu sous ce verrou — les threads avancent en
    parallèle jusqu'au plafond horaire, puis attendent l'expiration des jetons.
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
        """Bloque jusqu'à ce qu'un créneau soit libre sous le plafond horaire.

        La comptabilité (purge + réservation des jetons) se fait SOUS le verrou,
        mais le `sleep` éventuel a lieu HORS du verrou : les workers progressent
        réellement en parallèle jusqu'au plafond, au lieu d'être sérialisés.
        """
        while True:
            with self.lock:
                now = time.time()
                cutoff = now - 3600.0
                self.request_timestamps = [
                    t for t in self.request_timestamps if t > cutoff
                ]
                capacity = self.max_requests_per_hour - len(self.request_timestamps)
                if capacity >= self.requests_per_ticker:
                    self.request_timestamps.extend([now] * self.requests_per_ticker)
                    self.last_ticker_time = now
                    return
                # Plafond atteint : calculer l'attente puis dormir hors du verrou.
                sleep_time = max((self.request_timestamps[0] + 3600.0) - now + 0.1, 0.5)
            time.sleep(sleep_time)
