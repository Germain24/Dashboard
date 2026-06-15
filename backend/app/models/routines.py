"""Modèle Routine (#201) — moteur d'automatisations déclaratives."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
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
    created_at: dt.datetime = Field(default_factory=utcnow)


class RoutineRun(SQLModel, table=True):
    """Journal d'audit d'un déclenchement de routine (#217)."""
    __tablename__ = "routine_run"
    id: int | None = Field(default=None, primary_key=True)
    routine_id: int = Field(foreign_key="routine.id", index=True)
    routine_name: str = ""
    ran_at: dt.datetime = Field(default_factory=utcnow)
    status: str = "ok"          # "ok" | "blocked" | "error"
    detail: str = ""
    # Artefacts réversibles créés par ce run, p.ex. {"notifications":[id], "jobs":["x"]}
    # — sert au rollback (#216). Les notifications sont supprimables ; les jobs non.
    created_ids: str = "{}"
    rolled_back: bool = False
