"""Cadence Yahoo Finance globale — au plus 2 000 requêtes par heure."""

from __future__ import annotations

import threading
import time

from .config import Config

_active_limiter: RateLimiter | None = None


def set_active_limiter(limiter: RateLimiter | None) -> None:
    global _active_limiter
    _active_limiter = limiter


def active_paused_until() -> float | None:
    """Compatibilité API : l'espacement normal n'est pas une pause du run."""
    return _active_limiter.paused_until if _active_limiter is not None else None


class RateLimiter:
    """Espace chaque requête HTTP réelle selon un quota horaire.

    Le limiteur vit au niveau ``Session.request`` : un appel yfinance qui émet
    quatre requêtes consomme quatre créneaux. Les 429 sont comptés et différés
    par le runner, sans circuit exponentiel de 60/120/240 secondes.
    """

    def __init__(
        self,
        requests_per_hour: int = Config.YAHOO_REQUESTS_PER_HOUR,
        max_pause_seconds: float = Config.RATE_LIMIT_MAX_PAUSE_SEC,
        *,
        max_requests_per_minute: int | None = None,
    ) -> None:
        # Compatibilité des anciens appelants : une valeur /minute est convertie
        # en cadence horaire équivalente, mais le runtime utilise le nouveau
        # paramètre requests_per_hour.
        if max_requests_per_minute is not None:
            requests_per_hour = max_requests_per_minute * 60
        if requests_per_hour < 1:
            raise ValueError("requests_per_hour doit être >= 1")
        self.requests_per_hour = requests_per_hour
        self.min_interval_seconds = 3600.0 / requests_per_hour
        self.max_pause_seconds = max_pause_seconds
        self.request_timestamps: list[float] = []
        self.lock = threading.Lock()
        self.paused_until: float | None = None
        self._next_request_at = 0.0
        self._remote_failures = 0
        self.http_requests = 0
        self.deferred_rate_limits = 0

    def wait_for_slot(self) -> None:
        """Réserve le prochain départ HTTP en respectant l'intervalle global."""
        while True:
            sleep_time = self._try_reserve(time.monotonic())
            if sleep_time is None:
                return
            time.sleep(sleep_time)

    def wait_for_remote_recovery(self) -> None:
        """Compatibilité : un 429 n'ajoute plus aucune pause globale."""
        return None

    def _remote_wait(self, now: float) -> float:
        return 0.0

    def record_remote_rate_limit(
        self,
        retry_after_seconds: float | None = None,
    ) -> float:
        """Compte un 429; le ticker sera replacé en file par le runner."""
        with self.lock:
            self._remote_failures += 1
            self.deferred_rate_limits += 1
            self.paused_until = None
        return 0.0

    def record_remote_success(self) -> None:
        with self.lock:
            self._remote_failures = 0
            self.paused_until = None

    @property
    def remote_rate_limited(self) -> bool:
        return False

    def _try_reserve(self, now: float) -> float | None:
        """Réserve immédiatement ou renvoie l'attente avant le prochain départ."""
        with self.lock:
            if now >= self._next_request_at:
                self.request_timestamps.append(now)
                self._next_request_at = now + self.min_interval_seconds
                self.http_requests += 1
                self.paused_until = None
                return None
            return max(self._next_request_at - now, 0.001)
