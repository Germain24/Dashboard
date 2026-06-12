"""Routes Paramètres (#543-544)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings as env_settings
from app.core.secrets import mask_secret
from app.services.settings import get_preferences, set_preferences

router = APIRouter(tags=["settings"])


def _integration_status() -> dict:
    """Présence des secrets (jamais leur valeur) pour la page Paramètres."""
    return {
        "tmdb":              bool(env_settings.tmdb_api_key),
        "anthropic":         bool(env_settings.anthropic_api_key),
        "google_calendar":   bool(env_settings.google_refresh_token),
        "openweather":       bool(env_settings.openweather_api_key),
    }


@router.get("/settings")
def read_settings():
    return {
        "preferences": get_preferences(),
        "integrations": _integration_status(),
    }


@router.post("/settings")
def write_settings(patch: dict):
    updated = set_preferences(patch)
    return {"preferences": updated, "integrations": _integration_status()}
