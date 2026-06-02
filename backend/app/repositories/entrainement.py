"""Repositories du module Entrainement."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.entrainement import (
    CourseCardio, Exercice, Programme, ProgrammeJour, Seance, SetSerie,
)


class ExerciceRepository(Repository[Exercice]):
    model = Exercice


class ProgrammeRepository(Repository[Programme]):
    model = Programme


class ProgrammeJourRepository(Repository[ProgrammeJour]):
    model = ProgrammeJour


class SeanceRepository(Repository[Seance]):
    model = Seance


class SetSerieRepository(Repository[SetSerie]):
    model = SetSerie


class CourseCardioRepository(Repository[CourseCardio]):
    model = CourseCardio
