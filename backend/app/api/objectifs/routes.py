from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.objectifs.schemas import CATEGORIES, STATUTS, GoalCreate, GoalUpdate
from app.core.db import get_session
from app.models.objectifs import LongTermGoal

router = APIRouter(prefix="", tags=["objectifs"])


def _validate(data: dict) -> None:
    if "categorie" in data and data["categorie"] not in CATEGORIES:
        raise HTTPException(422, f"categorie doit être parmi {CATEGORIES}")
    if "statut" in data and data["statut"] not in STATUTS:
        raise HTTPException(422, f"statut doit être parmi {STATUTS}")


@router.get("/ping")
def ping():
    return {"module": "objectifs", "ready": True}


@router.get("/goals")
def list_goals(statut: str | None = None, session: Session = Depends(get_session)):
    q = select(LongTermGoal)
    if statut:
        if statut not in STATUTS:
            raise HTTPException(422, f"statut doit être parmi {STATUTS}")
        q = q.where(LongTermGoal.statut == statut)
    return session.exec(q.order_by(LongTermGoal.echeance.is_(None), LongTermGoal.echeance)).all()


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreate, session: Session = Depends(get_session)):
    _validate(body.model_dump())
    goal = LongTermGoal(**body.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdate, session: Session = Depends(get_session)):
    goal = session.get(LongTermGoal, goal_id)
    if not goal:
        raise HTTPException(404, f"Objectif {goal_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    _validate(data)
    for k, v in data.items():
        setattr(goal, k, v)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: Session = Depends(get_session)):
    goal = session.get(LongTermGoal, goal_id)
    if not goal:
        raise HTTPException(404, f"Objectif {goal_id} introuvable")
    session.delete(goal)
    session.commit()
