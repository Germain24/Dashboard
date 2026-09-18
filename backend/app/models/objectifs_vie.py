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
    # JSON : liste de sous-objectifs {label, metric, baseline, cible, date?}
    # metric = clé résolue dans un autre module (poids, epargne, habitudes_pct…).
    # `date` (optionnel) = jalon daté ; les objectifs stockés avant §5.4 n'en ont
    # pas et restent lisibles.
    # NB : un champ `unite` a longtemps été documenté ici sans jamais exister —
    # ni dans le schéma d'écriture (`SousObjectif`), ni dans le service, ni dans
    # l'UI. Toute valeur envoyée était silencieusement perdue. Retiré de la
    # description plutôt qu'ajouté au schéma : rien ne l'affiche.
    objectifs: str = "[]"
    created_at: dt.datetime = Field(default_factory=utcnow)
