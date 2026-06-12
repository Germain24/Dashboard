"""Modèle Routine (#201) — moteur d'automatisations déclaratives."""

from __future__ import annotations

import datetime as dt
from sqlmodel import SQLModel, Field


class Routine(SQLModel, table=True):
    __tablename__ = "routine"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    trigger_type: str = "cron"  # "cron" | "event"
    trigger_value: str = ""     # cron expr or event name
    actions: str = "[]"         # JSON list of {type, ...params}
    enabled: bool = True
    last_run_at: dt.datetime | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
