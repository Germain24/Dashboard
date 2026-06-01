import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.habitudes import Habit, HabitEntry
from app.services.habitudes import entries as entries_svc
from app.services.habitudes import streaks as streaks_svc
from app.services.habitudes import heatmap as heatmap_svc
from pydantic import BaseModel

router = APIRouter(prefix="", tags=["habitudes"])

class HabitCreate(BaseModel):
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"

class EntryCreate(BaseModel):
    habit_id: int
    date: dt.date
    valeur: float = 1.0

@router.get("/habits")
def list_habits(session: Session = Depends(get_session)):
    return session.exec(select(Habit).where(Habit.actif == True).order_by(Habit.ordre)).all()

@router.post("/habits", status_code=201)
def create_habit(body: HabitCreate, session: Session = Depends(get_session)):
    h = Habit(**body.model_dump())
    session.add(h)
    session.commit()
    session.refresh(h)
    return h

@router.patch("/habits/{id}")
def update_habit(id: int, body: dict, session: Session = Depends(get_session)):
    h = session.get(Habit, id)
    if not h:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(h, k, v)
    session.add(h)
    session.commit()
    session.refresh(h)
    return h

@router.delete("/habits/{id}", status_code=204)
def delete_habit(id: int, session: Session = Depends(get_session)):
    h = session.get(Habit, id)
    if not h:
        raise HTTPException(404)
    h.actif = False
    session.add(h)
    session.commit()

@router.get("/today")
def today_checklist(session: Session = Depends(get_session)):
    return entries_svc.get_today_checklist(session)

@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)):
    return entries_svc.upsert_entry(session, body.habit_id, body.date, body.valeur)

@router.delete("/entries/{id}", status_code=204)
def delete_entry(id: int, session: Session = Depends(get_session)):
    e = session.get(HabitEntry, id)
    if not e:
        raise HTTPException(404)
    session.delete(e)
    session.commit()

@router.get("/streaks")
def streaks(session: Session = Depends(get_session)):
    return streaks_svc.get_streaks(session)

@router.get("/heatmap")
def heatmap(habit_id: int, year: int = dt.date.today().year,
            session: Session = Depends(get_session)):
    return heatmap_svc.get_heatmap(session, habit_id, year)

@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    today = dt.date.today()
    start_30 = today - dt.timedelta(days=30)
    result = []
    for h in habits:
        entries = session.exec(
            select(HabitEntry).where(HabitEntry.habit_id == h.id, HabitEntry.date >= start_30)
        ).all()
        result.append({"habit_id": h.id, "nom": h.nom,
                       "completions_30j": len(entries),
                       "taux_30j": round(len(entries) / 30 * 100, 1)})
    return result
