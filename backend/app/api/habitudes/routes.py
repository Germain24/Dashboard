import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select
from app.core.db import get_session
from app.core.pagination import Pagination, paginate
from app.core.query_params import Sorting, apply_sort
from app.models.habitudes import Habit, HabitEntry
from app.repositories.habitudes import HabitRepository, HabitEntryRepository
from app.api.habitudes.schemas import HabitCreate, EntryCreate
from app.services.habitudes import entries as entries_svc
from app.services.habitudes import streaks as streaks_svc
from app.services.habitudes import heatmap as heatmap_svc
from app.services.habitudes import gamification as gamification_svc

router = APIRouter(prefix="", tags=["habitudes"])

@router.get("/habits")
def list_habits(response: Response,
                page: Pagination = Depends(),
                sorting: Sorting = Depends(),
                session: Session = Depends(get_session)):
    stmt = select(Habit).where(Habit.actif == True)
    if sorting.sort:
        stmt = apply_sort(stmt, Habit, sorting, allowed={"nom", "ordre", "frequence"})
    else:
        stmt = stmt.order_by(Habit.ordre)
    return paginate(session, stmt, response, page)

@router.post("/habits", status_code=201)
def create_habit(body: HabitCreate, session: Session = Depends(get_session)):
    return HabitRepository(session).create(body.model_dump())

@router.patch("/habits/{id}")
def update_habit(id: int, body: dict, session: Session = Depends(get_session)):
    repo = HabitRepository(session)
    h = repo.get(id)
    if not h:
        raise HTTPException(404)
    return repo.update(h, body)

@router.delete("/habits/{id}", status_code=204)
def delete_habit(id: int, session: Session = Depends(get_session)):
    repo = HabitRepository(session)
    h = repo.get(id)
    if not h:
        raise HTTPException(404)
    repo.update(h, {"actif": False})  # soft-delete

@router.get("/today")
def today_checklist(session: Session = Depends(get_session)):
    return entries_svc.get_today_checklist(session)

@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)):
    return entries_svc.upsert_entry(session, body.habit_id, body.date, body.valeur)

@router.delete("/entries/{id}", status_code=204)
def delete_entry(id: int, session: Session = Depends(get_session)):
    if not HabitEntryRepository(session).delete_by_id(id):
        raise HTTPException(404)

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


@router.get("/weekly-completion")
def weekly_completion(session: Session = Depends(get_session)):
    """Taux de complétion de la semaine en cours (lundi–aujourd'hui) pour la home (#138)."""
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    if not habits:
        return {"total": 0, "done": 0, "taux": 0}
    days_elapsed = (today - week_start).days + 1
    expected = sum(
        1 if h.frequence == "weekly" else days_elapsed
        for h in habits
    )
    done = 0
    for h in habits:
        if h.frequence == "weekly":
            done += 1 if session.exec(
                select(HabitEntry).where(
                    HabitEntry.habit_id == h.id,
                    HabitEntry.date >= week_start,
                    HabitEntry.date <= today,
                )
            ).first() else 0
        else:
            done += session.exec(
                select(HabitEntry).where(
                    HabitEntry.habit_id == h.id,
                    HabitEntry.date >= week_start,
                    HabitEntry.date <= today,
                )
            ).all().__len__()
    taux = round(done / expected * 100, 1) if expected else 0
    return {"total": expected, "done": done, "taux": min(taux, 100)}


@router.get("/gamification")
def gamification(session: Session = Depends(get_session)):
    """XP / niveau par habitude (#142)."""
    return gamification_svc.get_gamification(session)
