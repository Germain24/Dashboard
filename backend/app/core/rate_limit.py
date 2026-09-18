"""Rate limiting inbound léger (#193) : fenêtre glissante en mémoire par client.

Protège les routes coûteuses (analyses finance, chat robot) d'un usage abusif.
In-memory et process-local — adapté au déploiement local mono-process de Mission
Control. Pour un déploiement multi-process, remplacer le store par Redis.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Optional

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    """Autorise au plus ``max_calls`` appels par clé sur ``window_s`` secondes."""

    def __init__(self, max_calls: int, window_s: float) -> None:
        self.max_calls = max_calls
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self.window_s
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max_calls:
                return False
            dq.append(now)
            return True


def rate_limit(max_calls: int, window_s: float, name: str) -> Callable[[Request], None]:
    """Fabrique une dépendance FastAPI qui limite ``name`` par IP cliente.

    Renvoie 429 (avec en-tête ``Retry-After``) au-delà de ``max_calls`` sur
    ``window_s`` secondes.
    """
    limiter = SlidingWindowLimiter(max_calls, window_s)

    def _dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(f"{name}:{client}"):
            raise HTTPException(
                status_code=429,
                detail=f"Trop de requêtes ({name}). Réessaie dans un instant.",
                headers={"Retry-After": str(int(window_s))},
            )

    return _dependency
