"""Schémas du module Notifications (extraits de routes_notifications.py, #515)."""
from __future__ import annotations

from pydantic import BaseModel


class PrefUpdate(BaseModel):
    source: str
    enabled: bool
