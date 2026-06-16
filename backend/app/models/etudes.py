"""Modèles Études — CONV 6.

Remplace le stub CONV 1 (table `etude`).
Trois modèles :
  - Cours        : matière du semestre (code, nom, semestre, crédits optionnels)
  - Evaluation   : évaluation avec date → bridge Agenda (source="etudes")
  - SessionEtude : log de session de travail (Pomodoro / libre)
"""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from typing import Optional

from sqlmodel import Field, SQLModel


class Cours(SQLModel, table=True):
    __tablename__ = "cours"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)                  # ex. "INF1000"
    nom: str                                        # ex. "Introduction à la programmation"
    semestre: str = Field(index=True)               # ex. "A2026" ou "H2026"
    credits: int = Field(default=3)                 # crédits UQAM (défaut 3)
    prof: Optional[str] = None
    local: Optional[str] = None                     # salle de cours
    note_finale: Optional[float] = None             # /100, saisie manuelle
    actif: bool = Field(default=True)               # cours en cours ou terminé
    note: Optional[str] = None                      # commentaire libre
    created_at: dt.datetime = Field(
        default_factory=utcnow
    )
    updated_at: dt.datetime = Field(
        default_factory=utcnow
    )


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluation"

    id: Optional[int] = Field(default=None, primary_key=True)
    cours_id: int = Field(foreign_key="cours.id", index=True)
    titre: str                                      # ex. "Examen final", "TP1"
    type_eval: str = Field(default="autre")         # exam / devoir / quiz / projet / autre
    date_limite: Optional[dt.date] = Field(default=None, index=True)
    note_obtenue: Optional[float] = None            # note reçue (optionnel)
    note_max: Optional[float] = Field(default=100)  # /100 par défaut
    note: Optional[str] = None                      # commentaire
    created_at: dt.datetime = Field(
        default_factory=utcnow
    )
    updated_at: dt.datetime = Field(
        default_factory=utcnow
    )


class SessionEtude(SQLModel, table=True):
    __tablename__ = "session_etude"

    id: Optional[int] = Field(default=None, primary_key=True)
    cours_id: Optional[int] = Field(default=None, foreign_key="cours.id", index=True)
    date: dt.date = Field(default_factory=dt.date.today, index=True)
    duree_min: int                                  # durée en minutes
    sujet: Optional[str] = None                     # ce sur quoi on a travaillé
    note: Optional[str] = None                      # ressenti / bilan
    created_at: dt.datetime = Field(
        default_factory=utcnow
    )
