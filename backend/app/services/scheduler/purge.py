"""Purge des vieux JobRun et notifications lues (#172).

Rétention configurable (settings.jobrun_retention_days / notification_retention_days).
La logique de seuil est pure (testable) ; `purge_old` applique sur la DB.
"""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow

from sqlmodel import Session, select

from app.core.config import settings
from app.models.scheduler import JobRun, Notification


def cutoff(now: dt.datetime, days: int) -> dt.datetime:
    """Pur : date limite — tout ce qui est antérieur est purgeable."""
    return now - dt.timedelta(days=max(0, days))


def purge_old(
    session: Session,
    *,
    now: dt.datetime | None = None,
    jobrun_days: int | None = None,
    notif_days: int | None = None,
) -> dict[str, int]:
    """Supprime les JobRun anciens et les notifications LUES anciennes.

    Les notifications non lues sont conservées (l'utilisateur ne les a pas vues).
    Retourne le nombre d'éléments supprimés par table.
    """
    now = now or utcnow()
    jr_days = settings.jobrun_retention_days if jobrun_days is None else jobrun_days
    nt_days = settings.notification_retention_days if notif_days is None else notif_days

    jr_cut = cutoff(now, jr_days)
    nt_cut = cutoff(now, nt_days)

    jruns = session.exec(
        select(JobRun).where(JobRun.started_at < jr_cut)
    ).all()
    notifs = session.exec(
        select(Notification).where(
            Notification.lu == True, Notification.created_at < nt_cut  # noqa: E712
        )
    ).all()
    n_jr, n_nt = len(jruns), len(notifs)
    for r in jruns:
        session.delete(r)
    for n in notifs:
        session.delete(n)
    session.commit()
    return {"job_runs": n_jr, "notifications": n_nt}


def run(session: Session) -> str:
    """Point d'entrée job scheduler."""
    res = purge_old(session)
    return f"Purge : {res['job_runs']} JobRun, {res['notifications']} notifications lues supprimés."
