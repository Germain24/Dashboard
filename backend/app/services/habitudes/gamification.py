"""Gamification légère : XP et niveau basés sur completions + streaks (#142).

XP :
  - 1 XP par complétion binaire
  - 5 XP bonus quand la série courante est un multiple de 7 (semaine entière)
  - niveau = floor(sqrt(xp / 10))  — progression qui se tasse naturellement
"""

from __future__ import annotations

import datetime as dt
import math

from sqlmodel import Session, select

from app.models.habitudes import Habit, HabitEntry
from app.services.habitudes.streaks import compute_streak_pure


def compute_xp(total_completions: int, current_streak: int) -> int:
    """Pur : calcule le XP d'une habitude."""
    xp = total_completions
    # bonus par semaine complète dans le streak courant
    weekly_bonuses = current_streak // 7
    xp += weekly_bonuses * 5
    return xp


def compute_level(xp: int) -> int:
    """Pur : niveau à partir du XP (commence à 1)."""
    return max(1, math.floor(math.sqrt(xp / 10)) + 1)


def xp_to_next_level(xp: int) -> int:
    """Pur : XP restant pour passer au niveau suivant."""
    current = compute_level(xp)
    next_lvl_xp = ((current) ** 2) * 10
    return max(0, next_lvl_xp - xp)


def get_gamification(session: Session, *, today: dt.date | None = None) -> list[dict]:
    """Assemble XP/niveau par habitude active (#142)."""
    today = today or dt.date.today()
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    result = []
    for h in habits:
        dates = list(session.exec(select(HabitEntry.date).where(HabitEntry.habit_id == h.id)).all())
        total = len(dates)
        streak = compute_streak_pure(dates, today)
        xp = compute_xp(total, streak)
        result.append({
            "habit_id": h.id,
            "nom": h.nom,
            "xp": xp,
            "level": compute_level(xp),
            "xp_to_next": xp_to_next_level(xp),
        })
    return result
