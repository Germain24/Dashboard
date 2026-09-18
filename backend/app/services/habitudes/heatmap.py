import datetime as dt
from sqlmodel import Session, select
from app.models.habitudes import HabitEntry

def get_heatmap(session: Session, habit_id: int, year: int) -> list[dict]:
    start = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)
    entries = session.exec(
        select(HabitEntry).where(
            HabitEntry.habit_id == habit_id,
            HabitEntry.date >= start,
            HabitEntry.date <= end
        )
    ).all()
    entry_map = {e.date: e.valeur for e in entries}
    result = []
    current = start
    while current <= end:
        result.append({"date": current.isoformat(), "valeur": entry_map.get(current, 0)})
        current += dt.timedelta(days=1)
    return result
