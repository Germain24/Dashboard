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

def get_streaks(session: Session) -> list[dict]:
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    today = dt.date.today()
    result = []
    for h in habits:
        entries = session.exec(select(HabitEntry.date).where(HabitEntry.habit_id == h.id)).all()
        streak = compute_streak_pure(list(entries), today)
        result.append({"habit_id": h.id, "nom": h.nom, "streak": streak})
    return result
