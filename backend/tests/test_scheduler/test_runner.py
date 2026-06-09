"""Tests du runner de jobs (#182 e2e, #183 succès/erreur)."""

from sqlmodel import Session, select

from app.models.scheduler import JobRun, Notification
from app.services.scheduler.runner import run_job


def test_run_job_success_creates_jobrun_and_notification(patched_db_engine):
    run_job("demo_ok", lambda s: "fait")
    with Session(patched_db_engine) as s:
        runs = s.exec(select(JobRun)).all()
        assert len(runs) == 1
        assert runs[0].status == "success"
        assert runs[0].log == "fait"
        assert runs[0].finished_at is not None
        notifs = s.exec(select(Notification)).all()
        assert len(notifs) == 1
        assert notifs[0].level == "info"
        assert notifs[0].source == "demo_ok"


def test_run_job_exception_sets_error_status(patched_db_engine):
    def boom(_session):
        raise ValueError("kaboom")

    run_job("demo_err", boom)  # ne doit PAS propager l'exception
    with Session(patched_db_engine) as s:
        run = s.exec(select(JobRun)).first()
        assert run.status == "error"
        assert "kaboom" in run.log
        assert run.finished_at is not None
        notif = s.exec(select(Notification)).first()
        assert notif.level == "error"
        assert notif.source == "demo_err"


def test_run_job_e2e_real_job(patched_db_engine):
    """#182 : un vrai job (purge) s'exécute -> JobRun + Notification créés."""
    from app.services.scheduler import purge

    run_job("purge_old", purge.run)
    with Session(patched_db_engine) as s:
        run = s.exec(select(JobRun).where(JobRun.job_id == "purge_old")).first()
        assert run is not None and run.status == "success"
        assert s.exec(select(Notification).where(Notification.source == "purge_old")).first() is not None
