"""Schémas du module Health (extraits de routes_health.py, #516)."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    env: str
    timezone: str
    db: str
    timestamp: str
