"""Modèle DailySnapshot (#212) — journal de vie quotidien unifié."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from sqlmodel import SQLModel, Field


class DailySnapshot(SQLModel, table=True):
    __tablename__ = "daily_snapshot"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(unique=True, index=True)
    data: str = "{}"  # JSON blob — agrégat cross-modules
    created_at: dt.datetime = Field(default_factory=utcnow)
