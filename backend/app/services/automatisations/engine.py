"""Moteur de routines (#201) — exécution et CRUD."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
import json

from sqlmodel import Session, select

from app.models.routines import Routine, RoutineRun
from app.models.scheduler import Notification
from app.services.settings import get_preferences


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

def _log_run(
    session: Session, routine: Routine, status: str, detail: str,
    created: dict | None = None,
) -> None:
    """Écrit une entrée d'audit pour un déclenchement (#217).

    `created` (#216) = artefacts réversibles produits par le run, sérialisés en
    JSON dans `created_ids` pour permettre le rollback.
    """
    session.add(RoutineRun(
        routine_id=routine.id,
        routine_name=routine.name,
        status=status,
        detail=detail[:1000],
        created_ids=json.dumps(created or {"notifications": [], "jobs": []}),
    ))


def run_action_list(
    session: Session, actions: list[dict], *, source: str,
) -> tuple[str, str, dict]:
    """Exécute une liste d'actions (notify/job). Retourne (status, detail, created).

    Réutilisé par les routines ET les recettes (#215). N'engage pas le commit
    (laissé à l'appelant). `source` préfixe les notifications créées. `created`
    recense les artefacts réversibles (ids de notifications) + jobs déclenchés
    (non réversibles), pour le rollback (#216).
    """
    results: list[str] = []
    status = "ok"
    created: dict = {"notifications": [], "jobs": []}
    try:
        for action in actions:
            t = action.get("type")
            if t == "notify":
                notif = Notification(
                    source=source,
                    level=action.get("level", "info"),
                    titre=action.get("titre", "Routine"),
                    message=action.get("message", ""),
                )
                session.add(notif)
                session.flush()  # pour récupérer l'id (rollback)
                created["notifications"].append(notif.id)
                results.append("notif créée")
            elif t == "job":
                job_id = action.get("job_id", "")
                _trigger_job_now(job_id)
                created["jobs"].append(job_id)
                results.append(f"job {job_id!r} déclenché")
            else:
                results.append(f"action inconnue: {t!r}")
    except Exception as exc:  # une action a échoué -> "error"
        status = "error"
        results.append(f"erreur: {exc}")
    return status, ("; ".join(results) or "ok"), created


def execute_routine(session: Session, routine_id: int) -> str:
    """Exécute les actions d'une routine et met à jour last_run_at.

    Respecte le kill switch global (#217) : s'il est actif, aucune action n'est
    exécutée et la tentative est journalisée en "blocked". Chaque déclenchement
    (ok/blocked/error) crée une entrée d'audit `RoutineRun`.
    """
    routine = session.get(Routine, routine_id)
    if not routine:
        raise ValueError(f"Routine {routine_id} introuvable")

    # Kill switch global : on bloque avant toute action (manuelle ou planifiée).
    if get_preferences().get("automatisations_kill_switch"):
        _log_run(session, routine, "blocked", "Kill switch global actif")
        session.commit()
        return "bloqué (kill switch global actif)"

    actions = json.loads(routine.actions)
    status, detail, created = run_action_list(session, actions, source=f"routine_{routine_id}")

    routine.last_run_at = utcnow()
    session.add(routine)
    _log_run(session, routine, status, detail, created)
    session.commit()
    return detail


def get_routine_runs(
    session: Session, limit: int = 50, routine_id: int | None = None,
) -> list[RoutineRun]:
    """Journal d'audit des déclenchements, du plus récent au plus ancien (#217)."""
    q = select(RoutineRun)
    if routine_id is not None:
        q = q.where(RoutineRun.routine_id == routine_id)
    q = q.order_by(RoutineRun.id.desc()).limit(limit)
    return list(session.exec(q).all())


def rerun_run(session: Session, run_id: int) -> str:
    """Ré-exécute la routine d'un run passé (#216). Crée un nouveau RoutineRun.

    Respecte le kill switch (via execute_routine). Lève ValueError si le run ou
    la routine n'existent plus.
    """
    run = session.get(RoutineRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} introuvable")
    return execute_routine(session, run.routine_id)


def rollback_run(session: Session, run_id: int) -> str:
    """Annule ce qui est RÉVERSIBLE dans un run (#216).

    Seules les notifications créées par le run sont supprimables. Les actions
    `job` ont déjà appliqué leurs effets dans d'autres modules -> non réversibles,
    juste signalées. Idempotent (un run déjà annulé n'est pas rejoué).
    """
    run = session.get(RoutineRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} introuvable")
    if run.rolled_back:
        return "Déjà annulé."

    created = json.loads(run.created_ids or "{}")
    deleted = 0
    for nid in created.get("notifications", []):
        notif = session.get(Notification, nid)
        if notif is not None:
            session.delete(notif)
            deleted += 1

    parts = [f"{deleted} notification(s) supprimée(s)"]
    jobs = created.get("jobs", [])
    if jobs:
        parts.append(f"{len(jobs)} job(s) non réversible(s) (effets déjà appliqués)")

    run.rolled_back = True
    session.add(run)
    session.commit()
    return " ; ".join(parts)


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
