"""Intégration Google Calendar — lecture/écriture autonome (#83).

Implémentée en HTTP pur (httpx) pour éviter les dépendances Google lourdes :
- OAuth 2.0 « installed app » : on échange un refresh_token (obtenu une fois via
  scripts/google_oauth_setup.py) contre un access_token de courte durée, mis en
  cache mémoire.
- API REST Calendar v3 pour lister/créer/mettre à jour/supprimer des événements.

Si les identifiants ne sont pas configurés, `is_configured()` renvoie False et
les routes renvoient 503 — le reste du module Agenda fonctionne sans.

Les fonctions de conversion (`gcal_to_evenement`, `evenement_to_gcal`) sont
pures et testables sans réseau.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Optional

import httpx

from app.core.config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar"

# Cache mémoire de l'access token : (token, expiry_epoch)
_token_cache: tuple[str, float] | None = None


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_refresh_token)


def _get_access_token(*, force: bool = False) -> str:
    """Access token Google, rafraîchi via le refresh_token (caché ~55 min)."""
    global _token_cache
    if not force and _token_cache and _token_cache[1] > time.time() + 60:
        return _token_cache[0]
    resp = httpx.post(TOKEN_URL, data={
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": settings.google_refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    _token_cache = (token, time.time() + float(data.get("expires_in", 3600)))
    return token


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token()}", "Content-Type": "application/json"}


def _cal_id() -> str:
    return settings.google_calendar_id or "primary"


# ── Conversions pures ─────────────────────────────────────────────────────────

def _parse_g_datetime(node: dict[str, Any]) -> Optional[dt.datetime]:
    """Parse un noeud {dateTime|date} Google en datetime naïf (local ignoré)."""
    if not node:
        return None
    if "dateTime" in node:
        raw = node["dateTime"]
        # ex. 2026-06-03T09:00:00-04:00 → on tronque l'offset
        try:
            return dt.datetime.fromisoformat(raw).replace(tzinfo=None)
        except ValueError:
            return None
    if "date" in node:  # all-day
        try:
            d = dt.date.fromisoformat(node["date"])
            return dt.datetime(d.year, d.month, d.day)
        except ValueError:
            return None
    return None


def gcal_to_evenement(g: dict[str, Any]) -> dict[str, Any]:
    """Événement Google → dict compatible Evenement (source='gcal')."""
    debut = _parse_g_datetime(g.get("start", {})) or dt.datetime.utcnow()
    fin = _parse_g_datetime(g.get("end", {}))
    return {
        "titre": g.get("summary") or "Sans titre",
        "debut": debut,
        "fin": fin,
        "lieu": g.get("location"),
        "description": g.get("description"),
        "source": "gcal",
        "source_id": g.get("id"),
    }


def evenement_to_gcal(ev: dict[str, Any]) -> dict[str, Any]:
    """Dict Evenement → corps d'événement Google Calendar."""
    debut: dt.datetime = ev["debut"]
    fin: dt.datetime = ev.get("fin") or debut + dt.timedelta(hours=1)
    body: dict[str, Any] = {
        "summary": ev.get("titre", "Sans titre"),
        "start": {"dateTime": debut.replace(microsecond=0).isoformat(), "timeZone": settings.timezone},
        "end": {"dateTime": fin.replace(microsecond=0).isoformat(), "timeZone": settings.timezone},
    }
    if ev.get("lieu"):
        body["location"] = ev["lieu"]
    if ev.get("description"):
        body["description"] = ev["description"]
    return body


# ── Appels API ────────────────────────────────────────────────────────────────

def list_events(time_min: dt.datetime, time_max: dt.datetime) -> list[dict[str, Any]]:
    """Liste les événements Google dans la fenêtre (déjà convertis en dicts Evenement)."""
    params = {
        "timeMin": time_min.replace(microsecond=0).isoformat() + "Z",
        "timeMax": time_max.replace(microsecond=0).isoformat() + "Z",
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "250",
    }
    resp = httpx.get(f"{API_BASE}/calendars/{_cal_id()}/events", headers=_headers(), params=params, timeout=20.0)
    resp.raise_for_status()
    return [gcal_to_evenement(item) for item in resp.json().get("items", [])]


def create_event(ev: dict[str, Any]) -> dict[str, Any]:
    resp = httpx.post(
        f"{API_BASE}/calendars/{_cal_id()}/events",
        headers=_headers(), json=evenement_to_gcal(ev), timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def update_event(gcal_id: str, ev: dict[str, Any]) -> dict[str, Any]:
    resp = httpx.patch(
        f"{API_BASE}/calendars/{_cal_id()}/events/{gcal_id}",
        headers=_headers(), json=evenement_to_gcal(ev), timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


def delete_event(gcal_id: str) -> None:
    resp = httpx.delete(
        f"{API_BASE}/calendars/{_cal_id()}/events/{gcal_id}",
        headers=_headers(), timeout=20.0,
    )
    if resp.status_code not in (200, 204, 404, 410):
        resp.raise_for_status()
