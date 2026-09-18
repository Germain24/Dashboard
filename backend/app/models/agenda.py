"""Modèles Agenda — CONV 5.

Tables :
  - `regle_recurrence` : règle de répétition hebdomadaire simple
  - `evenement`        : événement ponctuel (étendu) ou lié à une règle
  - `tache`            : tâche avec deadline et priorité
"""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# RegleRecurrence
# ---------------------------------------------------------------------------

class RegleRecurrence(SQLModel, table=True):
    """Règle de répétition hebdomadaire : cours, shifts, activités récurrentes.

    Format simple : { weekdays: [0,2,4], start_time: '09:00', end_time: '12:00' }
    Avantage vs RRULE : lisible, éditable depuis l'UI sans parser RFC 5545.
    """

    __tablename__ = "regle_recurrence"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    # JSON list[int] 0=Lun…6=Dim (ISO weekday - 1 → Python weekday())
    weekdays: Any = Field(default_factory=list, sa_column=Column(JSON))
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"
    lieu: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None   # cours / travail / sport / rdv / autre
    couleur: Optional[str] = None     # "#3B82F6"
    until: Optional[dt.date] = None   # fin de la règle (None = indéfini)
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: Optional[dt.datetime] = None


# ---------------------------------------------------------------------------
# Evenement (extension de CONV 1)
# ---------------------------------------------------------------------------

class Evenement(SQLModel, table=True):
    """Événement ponctuel ou occurrence matérialisée d'une RecurrenceRule."""

    __tablename__ = "evenement"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    debut: dt.datetime = Field(index=True)
    fin: Optional[dt.datetime] = None
    lieu: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None      # "manuel" / "ical" / "garmin" / ...
    source_id: Optional[str] = None   # UID iCal pour déduplication
    # Extensions CONV 5
    categorie: Optional[str] = None   # cours / travail / sport / rdv / autre
    couleur: Optional[str] = None     # "#3B82F6"
    recurrence_id: Optional[int] = Field(
        default=None, foreign_key="regle_recurrence.id"
    )


# ---------------------------------------------------------------------------
# Tache
# ---------------------------------------------------------------------------

class Tache(SQLModel, table=True):
    """Tâche avec deadline et priorité.

    Modèle séparé d'Evenement (décision CONV 5) pour isoler les reqs
    de CONV 6 (Études) qui branchera ses devoirs ici.
    """

    __tablename__ = "tache"

    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    deadline: Optional[dt.date] = Field(default=None, index=True)
    priorite: int = Field(default=3)          # 1=très haute … 5=basse
    statut: str = Field(default="todo")       # "todo" / "done"
    duree_estimee_min: Optional[int] = None
    note: Optional[str] = None
    categorie: Optional[str] = None           # etudes / courses / perso / ...
    source: Optional[str] = None              # "manuel" / "etudes" / ...
    source_id: Optional[int] = None           # id dans la table source
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: Optional[dt.datetime] = None
