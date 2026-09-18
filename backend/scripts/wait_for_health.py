"""Attend que le backend réponde sur /health avant de continuer (#198).

Pratique pour les scripts de démarrage : ne lancer/ouvrir le front qu'une fois
l'API prête. Sort 0 dès que /health renvoie 2xx, 1 si le délai est dépassé.

Usage :
    uv run python scripts/wait_for_health.py [--url URL] [--timeout S] [--interval S]
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from typing import Callable


def is_ready(url: str, *, opener: Callable = urllib.request.urlopen) -> bool:
    """True si l'URL répond avec un statut 2xx (sinon False, sans lever)."""
    try:
        with opener(url, timeout=3) as resp:  # noqa: S310
            status = getattr(resp, "status", None) or resp.getcode()
            return 200 <= status < 300
    except Exception:
        return False


def wait_for_health(
    url: str,
    timeout: float = 60.0,
    interval: float = 1.0,
    *,
    ready: Callable[[str], bool] = is_ready,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> bool:
    """Sonde ``url`` jusqu'à 2xx ou expiration de ``timeout``. Retourne le succès."""
    deadline = now() + timeout
    while True:
        if ready(url):
            return True
        if now() >= deadline:
            return False
        sleep(interval)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Attend que /health soit prêt.")
    ap.add_argument("--url", default="http://127.0.0.1:8000/health")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args(argv)

    ok = wait_for_health(args.url, args.timeout, args.interval)
    print(f"{'ready' if ok else 'timeout'}: {args.url}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
