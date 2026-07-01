"""Client Duffel (REST direct, pas de SDK — le SDK officiel `duffel-api` sur
PyPI est explicitement non maintenu par Duffel) : prix/durée de vol le moins
cher entre deux aéroports à une date donnée, avec cache DB.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from sqlmodel import Session

from app.core.config import settings
from app.models.voyage import DuffelPriceCache

_OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests?return_offers=true"
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _parse_iso_duration_min(duration: str) -> int:
    """« PT14H23M » -> 863 (minutes). Format ISO 8601 renvoyé par Duffel."""
    m = _DURATION_RE.fullmatch(duration)
    if not m:
        return 0
    heures = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return heures * 60 + minutes


def _cache_key(origine: str, destination: str, date_reference: str) -> str:
    return f"{origine}|{destination}|{date_reference}"


def fetch_offer(
    session: Session,
    origine_iata: str,
    destination_iata: str,
    date_reference: str,
    *,
    http_post: Optional[Callable[..., Any]] = None,
) -> Optional[dict]:
    """Prix/durée de l'offre la moins chère entre deux aéroports à `date_reference`.

    Résultat mis en cache en DB (clé aéroports+date) : un second appel pour la
    même paire ne re-sollicite pas Duffel. `http_post` est injectable pour les
    tests (même signature que `httpx.post` : `(url, **kwargs) -> response` avec
    `response.status_code` et `response.json()`) ; en production, `httpx.post`.

    Retourne `None` si pas de clé API configurée, pas d'offre disponible, ou
    statut HTTP différent de 201 (jamais de levée d'exception réseau/API).
    """
    if not settings.duffel_api_key:
        return None

    key = _cache_key(origine_iata, destination_iata, date_reference)
    cached = session.get(DuffelPriceCache, key)
    if cached:
        return {"prix": cached.prix, "devise": cached.devise, "duree_min": cached.duree_min}

    poster = http_post
    if poster is None:
        import httpx
        poster = httpx.post

    try:
        resp = poster(
            _OFFER_REQUESTS_URL,
            headers={
                "Authorization": f"Bearer {settings.duffel_api_key}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "data": {
                    "slices": [{"origin": origine_iata, "destination": destination_iata,
                                 "departure_date": date_reference}],
                    "passengers": [{"type": "adult"}],
                    "cabin_class": "economy",
                }
            },
            timeout=30,
        )
    except Exception:
        return None

    if resp.status_code != 201:
        return None
    offers = resp.json().get("data", {}).get("offers", [])
    if not offers:
        return None

    cheapest = min(offers, key=lambda o: float(o["total_amount"]))
    result = {
        "prix": float(cheapest["total_amount"]),
        "devise": cheapest["total_currency"],
        "duree_min": _parse_iso_duration_min(cheapest["slices"][0]["duration"]),
    }
    session.add(DuffelPriceCache(
        cache_key=key, origine_iata=origine_iata, destination_iata=destination_iata,
        date_reference=date_reference, **result,
    ))
    session.commit()
    return result
