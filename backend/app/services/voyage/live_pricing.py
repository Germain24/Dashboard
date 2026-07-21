"""Tarification de vols datés via Duffel, avec cache et fallback explicite."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.models.voyage import VoyagePriceCache
from app.services.finance import fx

_URL = "https://api.duffel.com/air/offer_requests?return_offers=true&supplier_timeout=15000"
_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _duration_minutes(value: str) -> int:
    match = _DURATION_RE.fullmatch(value or "")
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0) if match else 0


def _key(slices: list[dict]) -> str:
    raw = json.dumps(slices, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _to_eur(amount: float, currency: str) -> float | None:
    if currency.upper() == "EUR":
        return round(amount, 2)
    converted = fx.convert(amount, currency.upper(), "EUR", stale_ok=True)
    return converted or None


def fetch_live_itinerary(
    session: Session,
    slices: list[dict],
    *,
    http_post: Callable[..., Any] | None = None,
    now: dt.datetime | None = None,
) -> dict | None:
    """Retourne le vol multi-destinations le moins cher pour les dates exactes.

    Le résultat contient toujours un prix en EUR. Une devise impossible à
    convertir est rejetée afin de ne jamais additionner silencieusement EUR et
    CAD/USD.
    """
    if not settings.duffel_api_key or not slices:
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    key = _key(slices)
    cached = session.get(VoyagePriceCache, key)
    if cached:
        fetched = dt.datetime.fromisoformat(cached.fetched_at)
        if now - fetched <= dt.timedelta(hours=settings.voyage_live_price_cache_hours):
            eur = _to_eur(cached.prix, cached.devise)
            if eur is not None:
                return {
                    "prix": eur, "duree_min": cached.duree_min,
                    "transporteur": cached.transporteur, "source": "cache_live",
                }

    if http_post is None:
        import httpx
        http_post = httpx.post
    try:
        response = http_post(
            _URL,
            headers={
                "Authorization": f"Bearer {settings.duffel_api_key}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            json={"data": {
                "slices": slices,
                "passengers": [{"type": "adult"}],
                "cabin_class": "economy",
                "max_connections": 1,
            }},
            timeout=25,
        )
    except Exception:
        return None
    if response.status_code != 201:
        return None
    offers = response.json().get("data", {}).get("offers", [])
    if not offers:
        return None
    offer = min(offers, key=lambda item: float(item["total_amount"]))
    amount = float(offer["total_amount"])
    currency = offer["total_currency"]
    eur = _to_eur(amount, currency)
    if eur is None:
        return None
    duration = sum(_duration_minutes(s.get("duration", "")) for s in offer.get("slices", []))
    carriers = []
    for slice_ in offer.get("slices", []):
        for segment in slice_.get("segments", []):
            name = (segment.get("operating_carrier") or {}).get("name")
            if name and name not in carriers:
                carriers.append(name)
    carrier = ", ".join(carriers) or None
    session.merge(VoyagePriceCache(
        cache_key=key,
        itineraire=" > ".join([s["origin"] for s in slices] + [slices[-1]["destination"]]),
        dates=",".join(s["departure_date"] for s in slices),
        prix=amount,
        devise=currency,
        duree_min=duration,
        transporteur=carrier,
        fetched_at=now.isoformat(),
    ))
    session.commit()
    return {"prix": eur, "duree_min": duration, "transporteur": carrier, "source": "live"}
