"""Horodatage UTC sans la déprécation de ``datetime.utcnow()``.

``datetime.utcnow()`` est déprécié (suppression prévue). Sa contrepartie
recommandée ``datetime.now(timezone.utc)`` renvoie un datetime *aware*, ce qui
casserait les comparaisons avec les datetimes *naïfs* déjà stockés en base et
manipulés partout dans le code. ``utcnow()`` ci-dessous est un remplacement
strictement équivalent : même valeur (UTC), même type (naïf), API non dépréciée.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Instant courant en UTC, *naïf* (sans tzinfo) — drop-in de ``datetime.utcnow()``."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
