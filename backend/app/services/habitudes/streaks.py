import datetime as dt
from sqlmodel import Session, select
from app.models.habitudes import Habit, HabitEntry


def compute_streak_pure(entry_dates: list[dt.date], today: dt.date) -> int:
    if not entry_dates:
        return 0
    date_set = set(entry_dates)
    if today not in date_set:
        return 0
    streak = 0
    current = today
    while current in date_set:
        streak += 1
        current -= dt.timedelta(days=1)
    return streak


def compute_best_streak_pure(entry_dates: list[dt.date]) -> int:
    """Pur : retourne la plus longue série consécutive dans entry_dates."""
    if not entry_dates:
        return 0
    sorted_dates = sorted(set(entry_dates))
    best = 1
    current = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] - sorted_dates[i - 1] == dt.timedelta(days=1):
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def get_streaks(session: Session) -> list[dict]:
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    today = dt.date.today()
    result = []
    for h in habits:
        entries = session.exec(select(HabitEntry.date).where(HabitEntry.habit_id == h.id)).all()
        dates = list(entries)
        streak = compute_streak_pure(dates, today)
        best = compute_best_streak_pure(dates)
        result.append({"habit_id": h.id, "nom": h.nom, "streak": streak, "best_streak": best})
    return result
