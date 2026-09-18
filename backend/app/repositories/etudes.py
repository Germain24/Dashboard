"""Repositories du module Etudes."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.etudes import Cours, Evaluation, SessionEtude


class CoursRepository(Repository[Cours]):
    model = Cours


class EvaluationRepository(Repository[Evaluation]):
    model = Evaluation


class SessionEtudeRepository(Repository[SessionEtude]):
    model = SessionEtude
