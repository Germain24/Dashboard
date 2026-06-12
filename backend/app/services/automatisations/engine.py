"""Moteur de routines (#201) — exécution et CRUD."""

from __future__ import annotations

import datetime as dt
import json

from sqlmodel import Session, select

from app.models.routines import Routine
from app.models.scheduler import Notification


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def get_routines(session: Session) -> list[Routine]:
    return list(session.exec(select(Routine).order_by(Routine.created_at)).all())


def get_routine(session: Session, routine_id: int) -> Routine | None:
    return session.get(Routine, routine_id)


def create_routine(
    session: Session,
    name: str,
    trigger_type: str = "cron",
    trigger_value: str = "",
    actions: list[dict] | None = None,
    description: str = "",
    enabled: bool = True,
) -> Routine:
    routine = Routine(
        name=name,
        description=description,
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        actions=json.dumps(actions or []),
        enabled=enabled,
    )
    session.add(routine)
    session.commit()
    session.refresh(routine)
    return routine


def update_routine(session: Session, routine_id: int, patch: dict) -> Routine | None:
    routine = session.get(Routine, routine_id)
    if not routine:
        return None
    if "actions" in patch and isinstance(patch["actions"], list):
        patch["actions"] = json.dumps(patch["actions"])
    for k, v in patch.items():
        setattr(routine, k, v)
    session.add(routine)
    session.commit()
    session.refresh(routine)
    return routine


def delete_routine(session: Session, routine_id: int) -> bool:
    routine = session.get(Routine, routine_id)
    if not routine:
        return False
    session.delete(routine)
    session.commit()
    return True


# ─── EXÉCUTION ────────────────────────────────────────────────────────────────

def execute_routine(session: Session, routine_id: int) -> str:
    """Exécute les actions d'une routine et met à jour last_run_at."""
    routine = session.get(Routine, routine_id)
    if not routine:
        raise ValueError(f"Routine {routine_id} introuvable")

    actions = json.loads(routine.actions)
    results: list[str] = []

    for action in actions:
        t = action.get("type")
        if t == "notify":
            session.add(Notification(
                source=f"routine_{routine_id}",
                level=action.get("level", "info"),
                titre=action.get("titre", "Routine"),
                message=action.get("message", ""),
            ))
            results.append("notif créée")
        elif t == "job":
            job_id = action.get("job_id", "")
            _trigger_job_now(job_id)
            results.append(f"job {job_id!r} déclenché")
        else:
            results.append(f"action inconnue: {t!r}")

    routine.last_run_at = dt.datetime.utcnow()
    session.add(routine)
    session.commit()
    return "; ".join(results) or "ok"


def _trigger_job_now(job_id: str) -> None:
    """Déclenche un job APScheduler immédiatement (best-effort)."""
    try:
        from app.services.scheduler.scheduler import get_scheduler
        scheduler = get_scheduler()
        job = scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=dt.datetime.now())
    except Exception:
        pass
