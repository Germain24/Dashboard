"""Modèle LifeGoal (#226) — objectifs de vie inter-modules."""

from __future__ import annotations

import datetime as dt

from app.core.timeutil import utcnow
from sqlmodel import SQLModel, Field


class LifeGoal(SQLModel, table=True):
    __tablename__ = "life_goal"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    echeance: dt.date | None = None
    # JSON : liste de sous-objectifs {label, metric, baseline, cible, unite}
    # metric = clé résolue dans un autre module (poids, epargne, habitudes_pct…).
    objectifs: str = "[]"
    created_at: dt.datetime = Field(default_factory=utcnow)
