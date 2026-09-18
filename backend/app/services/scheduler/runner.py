import datetime as dt
import time

from sqlalchemy.exc import OperationalError
from app.core.timeutil import utcnow
from sqlmodel import Session
from app.models.scheduler import JobRun, Notification


def _commit_with_sqlite_retry(session: Session, restore=None) -> None:
    """Committe un job même si une écriture SQLite concurrente est en cours."""
    for attempt in range(6):
        try:
            session.commit()
            return
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt == 5:
                raise
            session.rollback()
            if restore is not None:
                restore()
            time.sleep(0.25 * (2 ** attempt))

def run_job(job_id: str, func):
    from app.core.db import engine
    with Session(engine) as session:
        run = JobRun(job_id=job_id, started_at=utcnow())
        def restore_start() -> None:
            session.add(run)

        restore_start()
        _commit_with_sqlite_retry(session, restore=restore_start)
        session.refresh(run)
        notification = None
        try:
            result = func(session)
            run.status = "success"
            run.log = str(result if result is not None else "OK")
            # Convention (audit §3.E) : un job qui renvoie None n'a rien
            # d'actionnable à signaler -> aucune notification. La traçabilité de
            # TOUS les runs reste assurée par JobRun et la page /jobs. Sans ça,
            # agenda_reminders (96 passages/jour) noyait le centre sous 1 141
            # « 0 rappel(s) créé(s) », rendant les vraies erreurs invisibles.
            if result is not None:
                notification = Notification(
                    source=job_id, titre=f"Job {job_id} terminé",
                    message=run.log, level="info",
                )
                session.add(notification)
        except Exception as e:
            run.status = "error"
            run.log = str(e)
            notification = Notification(source=job_id, titre=f"Erreur job {job_id}",
                                        message=str(e), level="error")
            session.add(notification)
        finally:
            run.finished_at = utcnow()
            final_status = run.status
            final_log = run.log
            final_finished_at = run.finished_at

            def restore_final() -> None:
                run.status = final_status
                run.log = final_log
                run.finished_at = final_finished_at
                session.add(run)
                if notification is not None:
                    session.add(notification)

            restore_final()
            _commit_with_sqlite_retry(session, restore=restore_final)
