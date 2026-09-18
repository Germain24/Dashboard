"""Repositories du module Habitudes."""
from __future__ import annotations

from app.core.repository import Repository
from app.models.habitudes import Habit, HabitEntry


class HabitRepository(Repository[Habit]):
    model = Habit


class HabitEntryRepository(Repository[HabitEntry]):
    model = HabitEntry
