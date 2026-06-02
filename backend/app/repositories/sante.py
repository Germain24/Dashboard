"""Repositories du module Sante."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.sante import Aliment, MesureSante, NutritionGoal, PlanNutrition


class MesureSanteRepository(Repository[MesureSante]):
    model = MesureSante


class PlanNutritionRepository(Repository[PlanNutrition]):
    model = PlanNutrition


class AlimentRepository(Repository[Aliment]):
    model = Aliment


class NutritionGoalRepository(Repository[NutritionGoal]):
    model = NutritionGoal
