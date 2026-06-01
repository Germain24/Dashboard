import datetime as dt
from sqlmodel import Session
from app.models.scheduler import JobRun, Notification

def run_job(job_id: str, func):
    from app.core.db import engine
    with Session(engine) as session:
        run = JobRun(job_id=job_id, started_at=dt.datetime.utcnow())
        session.add(run)
        session.commit()
        session.refresh(run)
        try:
            result = func(session)
            run.status = "success"
            run.log = str(result or "OK")
            notif = Notification(source=job_id, titre=f"Job {job_id} terminé",
                                 message=run.log, level="info")
            session.add(notif)
        except Exception as e:
            run.status = "error"
            run.log = str(e)
            notif = Notification(source=job_id, titre=f"Erreur job {job_id}",
                                 message=str(e), level="error")
            session.add(notif)
        finally:
            run.finished_at = dt.datetime.utcnow()
            session.add(run)
            session.commit()
