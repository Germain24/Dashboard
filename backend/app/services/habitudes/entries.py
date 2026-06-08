import datetime as dt
import json
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.habitudes import Habit, HabitEntry

DEFAULT_HABITS = [
    {"nom": "Muscu", "type": "binaire", "source_auto": "entrainement_muscu", "ordre": 0},
    {"nom": "Course", "type": "binaire", "source_auto": "entrainement_cardio", "ordre": 1},
    {"nom": "Lecture", "type": "quantifiable", "unite": "minutes", "cible": 30.0, "source_auto": "livres_lecture", "ordre": 2},
    {"nom": "Sommeil >= 7h", "type": "binaire", "ordre": 3},
    {"nom": "Pas de junk food", "type": "binaire", "ordre": 4},
    {"nom": "Meditation", "type": "binaire", "ordre": 5},
]

def seed_habits(session: Session) -> None:
    existing = session.exec(select(Habit)).all()
    if existing:
        return
    for h in DEFAULT_HABITS:
        habit = Habit(**h)
        session.add(habit)
    session.commit()

def get_today_checklist(session: Session, *, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    habits = session.exec(select(Habit).where(Habit.actif == True).order_by(Habit.ordre)).all()
    entries_today = {e.habit_id: e for e in session.exec(
        select(HabitEntry).where(HabitEntry.date == today)
    ).all()}
    week_start = today - dt.timedelta(days=today.weekday())  # Monday
    result = []
    for h in habits:
        if h.frequence == "weekly":
            entry = entries_today.get(h.id) or session.exec(
                select(HabitEntry).where(
                    HabitEntry.habit_id == h.id,
                    HabitEntry.date >= week_start,
                    HabitEntry.date <= today,
                )
            ).first()
        else:
            entry = entries_today.get(h.id)
        result.append({"habit": h, "entry": entry})
    return result

def upsert_entry(session: Session, habit_id: int, date: dt.date,
                 valeur: float = 1.0, auto: bool = False) -> HabitEntry:
    existing = session.exec(
        select(HabitEntry).where(HabitEntry.habit_id == habit_id, HabitEntry.date == date)
    ).first()
    if existing:
        existing.valeur = valeur
        session.add(existing)
        session.commit()
        session.refresh(existing)
        _propagate_linked(session, habit_id, date)
        return existing
    entry = HabitEntry(habit_id=habit_id, date=date, valeur=valeur, auto=auto)
    try:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        _propagate_linked(session, habit_id, date)
        return entry
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(HabitEntry).where(HabitEntry.habit_id == habit_id, HabitEntry.date == date)
        ).first()


def _propagate_linked(session: Session, habit_id: int, date: dt.date) -> None:
    """Auto-coche les habitudes liées (linked_ids) sans boucle infinie."""
    habit = session.get(Habit, habit_id)
    if not habit:
        return
    try:
        linked_ids: list[int] = json.loads(habit.linked_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        return
    for linked_id in linked_ids:
        if linked_id == habit_id:
            continue
        existing = session.exec(
            select(HabitEntry).where(HabitEntry.habit_id == linked_id, HabitEntry.date == date)
        ).first()
        if not existing:
            session.add(HabitEntry(habit_id=linked_id, date=date, valeur=1.0, auto=True))
    session.commit()

def auto_check_habit(session: Session, source: str, date: dt.date, valeur: float = 1.0) -> bool:
    habit = session.exec(
        select(Habit).where(Habit.source_auto == source, Habit.actif == True)
    ).first()
    if not habit:
        return False
    upsert_entry(session, habit.id, date, valeur=valeur, auto=True)
    return True
