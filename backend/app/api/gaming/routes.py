from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.gaming.schemas import GOAL_TYPES, STATUTS, GameCreate, GameUpdate, GoalCreate, GoalUpdate
from app.core.db import get_session
from app.models.gaming import Game, GameGoal

router = APIRouter(prefix="", tags=["gaming"])


@router.get("/ping")
def ping():
    return {"module": "gaming", "ready": True}


@router.get("/games")
def list_games(statut: str | None = None, session: Session = Depends(get_session)):
    q = select(Game)
    if statut:
        if statut not in STATUTS:
            raise HTTPException(422, f"statut doit être parmi {STATUTS}")
        q = q.where(Game.statut == statut)
    games = session.exec(q.order_by(Game.titre)).all()
    counts = {
        g_id: n
        for g_id, n in session.exec(
            select(GameGoal.game_id, func.count()).group_by(GameGoal.game_id)
        ).all()
    }
    return [{**g.model_dump(), "nb_goals": counts.get(g.id, 0)} for g in games]


@router.post("/games", status_code=201)
def create_game(body: GameCreate, session: Session = Depends(get_session)):
    if body.statut not in STATUTS:
        raise HTTPException(422, f"statut doit être parmi {STATUTS}")
    game = Game(**body.model_dump())
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@router.patch("/games/{game_id}")
def update_game(game_id: int, body: GameUpdate, session: Session = Depends(get_session)):
    game = session.get(Game, game_id)
    if not game:
        raise HTTPException(404, f"Jeu {game_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    if "statut" in data and data["statut"] not in STATUTS:
        raise HTTPException(422, f"statut doit être parmi {STATUTS}")
    for k, v in data.items():
        setattr(game, k, v)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


@router.delete("/games/{game_id}", status_code=204)
def delete_game(game_id: int, session: Session = Depends(get_session)):
    game = session.get(Game, game_id)
    if not game:
        raise HTTPException(404, f"Jeu {game_id} introuvable")
    for goal in session.exec(select(GameGoal).where(GameGoal.game_id == game_id)).all():
        session.delete(goal)
    session.delete(game)
    session.commit()


@router.get("/games/{game_id}/goals")
def list_goals(game_id: int, session: Session = Depends(get_session)):
    if not session.get(Game, game_id):
        raise HTTPException(404, f"Jeu {game_id} introuvable")
    return session.exec(
        select(GameGoal).where(GameGoal.game_id == game_id).order_by(GameGoal.fait, GameGoal.id)
    ).all()


@router.post("/games/{game_id}/goals", status_code=201)
def create_goal(game_id: int, body: GoalCreate, session: Session = Depends(get_session)):
    if not session.get(Game, game_id):
        raise HTTPException(404, f"Jeu {game_id} introuvable")
    if body.type not in GOAL_TYPES:
        raise HTTPException(422, f"type doit être parmi {GOAL_TYPES}")
    goal = GameGoal(game_id=game_id, **body.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdate, session: Session = Depends(get_session)):
    goal = session.get(GameGoal, goal_id)
    if not goal:
        raise HTTPException(404, f"Objectif {goal_id} introuvable")
    data = body.model_dump(exclude_unset=True)
    if "type" in data and data["type"] not in GOAL_TYPES:
        raise HTTPException(422, f"type doit être parmi {GOAL_TYPES}")
    for k, v in data.items():
        setattr(goal, k, v)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: Session = Depends(get_session)):
    goal = session.get(GameGoal, goal_id)
    if not goal:
        raise HTTPException(404, f"Objectif {goal_id} introuvable")
    session.delete(goal)
    session.commit()
