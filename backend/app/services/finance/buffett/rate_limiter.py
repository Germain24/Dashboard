"""Rate limiter pour les requêtes yfinance — plafond horaire glissant, concurrent."""

from __future__ import annotations

import threading
import time

from .config import Config


# Limiter de l'analyse en cours, exposé au endpoint de progression (#193).
# Mono-process : une seule analyse Buffett tourne à la fois (verrou _ANALYSIS_LOCK).
_active_limiter: "RateLimiter | None" = None


def set_active_limiter(limiter: "RateLimiter | None") -> None:
    global _active_limiter
    _active_limiter = limiter


def active_paused_until() -> float | None:
    """Epoch de reprise estimée si l'analyse en cours est en pause (sinon None)."""
    lim = _active_limiter
    return lim.paused_until if lim is not None else None


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
        # Horodatage (epoch) de reprise estimée quand le plafond est atteint ;
        # None si on n'attend pas. Exposé à l'UI pour rendre la pause lisible (#193).
        self.paused_until: float | None = None

    def wait_for_slot(self) -> None:
        """Bloque jusqu'à ce qu'un créneau soit libre sous le plafond horaire.

        La comptabilité (purge + réservation des jetons) se fait SOUS le verrou,
        mais le `sleep` éventuel a lieu HORS du verrou : les workers progressent
        réellement en parallèle jusqu'au plafond, au lieu d'être sérialisés.
        """
        while True:
            sleep_time = self._try_reserve(time.time())
            if sleep_time is None:
                return
            time.sleep(sleep_time)

    def _try_reserve(self, now: float) -> float | None:
        """Réserve un créneau si possible (retourne None), sinon le délai d'attente.

        Effet de bord thread-safe : met à jour ``paused_until`` (epoch de reprise
        estimée) quand le plafond est atteint, le remet à None dès qu'un créneau
        est réservé. Séparé de ``wait_for_slot`` pour être testable sans dormir.
        """
        with self.lock:
            cutoff = now - 3600.0
            self.request_timestamps = [t for t in self.request_timestamps if t > cutoff]
            capacity = self.max_requests_per_hour - len(self.request_timestamps)
            if capacity >= self.requests_per_ticker:
                self.request_timestamps.extend([now] * self.requests_per_ticker)
                self.last_ticker_time = now
                self.paused_until = None
                return None
            # Plafond atteint : reprise quand le plus ancien jeton sort de la fenêtre.
            sleep_time = max((self.request_timestamps[0] + 3600.0) - now + 0.1, 0.5)
            self.paused_until = now + sleep_time
            return sleep_time
