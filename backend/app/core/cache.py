"""Cache léger en mémoire avec TTL (sans dépendance externe).

Suffisant pour un déploiement mono-process (le cas de Mission Control). Pour
un usage multi-process/multi-machine, brancher Redis derrière la même API.

Deux usages :

- décorateur :func:`ttl_cache` sur une fonction à arguments hashables ;
- :class:`TTLCache` pour un cache à clés explicites (résultats dérivés de la DB).
"""

from __future__ import annotations

import functools
import threading
import time
from typing import Any, Callable, Optional


class TTLCache:
    """Cache clé→valeur thread-safe avec expiration."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl = ttl_seconds
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self.ttl, value)

    def get_or_set(self, key: Any, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def ttl_cache(ttl_seconds: float = 300.0) -> Callable:
    """Décorateur de cache TTL pour fonctions à arguments hashables."""

    def decorator(func: Callable) -> Callable:
        cache = TTLCache(ttl_seconds)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]  # accès pour invalidation
        return wrapper

    return decorator
