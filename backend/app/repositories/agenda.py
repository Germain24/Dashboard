"""Repositories du module Agenda."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.agenda import Evenement, RegleRecurrence, Tache


class EvenementRepository(Repository[Evenement]):
    model = Evenement


class TacheRepository(Repository[Tache]):
    model = Tache


class RegleRecurrenceRepository(Repository[RegleRecurrence]):
    model = RegleRecurrence
