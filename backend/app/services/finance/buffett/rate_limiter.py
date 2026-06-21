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

    Deux garde-fous : (1) une fenêtre glissante d'1 h qui plafonne le total, et
    (2) un lissage `min_interval` qui espace les réservations pour répartir la
    charge uniformément (2000/h ≈ 0,55 req/s) au lieu de saturer en rafale.
    La réservation des jetons est protégée par un verrou, mais aucun `sleep`
    n'est tenu sous ce verrou.
    """

    # Plafond d'attente quand le quota horaire est atteint. Plutôt qu'une pause
    # unique pouvant durer jusqu'à ~1 h, on dort au plus ce délai (2 min par
    # défaut, .env: BUFFETT_RATE_LIMIT_MAX_PAUSE_SEC) puis on re-tente : le quota
    # se libère par jetons, et entre-temps la session peut changer d'IP (proxy),
    # ce qui débloque souvent Yahoo avant la fin de la fenêtre théorique.
    MAX_PAUSE_SECONDS: float = Config.RATE_LIMIT_MAX_PAUSE_SEC

    def __init__(
        self,
        max_requests_per_hour: int = Config.MAX_REQUESTS_PER_HOUR,
        requests_per_ticker: int = Config.REQUESTS_PER_TICKER,
        max_pause_seconds: float = Config.RATE_LIMIT_MAX_PAUSE_SEC,
    ) -> None:
        self.max_requests_per_hour = max_requests_per_hour
        self.requests_per_ticker = requests_per_ticker
        self.max_pause_seconds = max_pause_seconds
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
        slept = False
        while True:
            sleep_time = self._try_reserve(time.time())
            if sleep_time is None:
                # Si on a dû attendre (quota saturé), on change d'IP avant de
                # repartir : la prochaine session utilisera un autre proxy.
                if slept:
                    try:
                        from app.services.finance.yf_session import rotate_session

                        rotate_session()
                    except Exception:
                        pass
                return
            slept = True
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
            # Lissage : on espace les réservations d'au moins min_interval pour
            # répartir les requêtes uniformément sur l'heure (2000/h ≈ 0,55 req/s)
            # plutôt que de saturer en rafale puis attendre. Borné à max_pause :
            # on re-tentera (l'IP a pu changer entre-temps).
            since_last = now - self.last_ticker_time
            if self.last_ticker_time and since_last < self.min_interval:
                wait = min(self.min_interval - since_last, self.max_pause_seconds)
                self.paused_until = now + wait
                return wait
            capacity = self.max_requests_per_hour - len(self.request_timestamps)
            if capacity >= self.requests_per_ticker:
                self.request_timestamps.extend([now] * self.requests_per_ticker)
                self.last_ticker_time = now
                self.paused_until = None
                return None
            # Plafond atteint : reprise quand le plus ancien jeton sort de la
            # fenêtre, MAIS borné à max_pause_seconds (on re-tentera après).
            sleep_time = max((self.request_timestamps[0] + 3600.0) - now + 0.1, 0.5)
            sleep_time = min(sleep_time, self.max_pause_seconds)
            self.paused_until = now + sleep_time
            return sleep_time
