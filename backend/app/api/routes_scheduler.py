import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.scheduler import JobRun
from app.services.scheduler.scheduler import get_scheduler

router = APIRouter(prefix="", tags=["jobs"])

@router.get("/list")
def list_jobs(session: Session = Depends(get_session)):
    """Liste TOUS les jobs enregistrés dans le scheduler (#166), avec prochaine
    exécution, état (pause), dernier run et indicateur d'échec (#173)."""
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs()
    result = []
    for job in jobs:
        last_run = session.exec(
            select(JobRun).where(JobRun.job_id == job.id).order_by(JobRun.started_at.desc())
        ).first()
        result.append({
            "job_id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "paused": job.next_run_time is None,
            "last_run": last_run,
            "last_failed": bool(last_run and last_run.status not in ("success", "running")),
        })
    result.sort(key=lambda r: r["job_id"])
    return result

@router.get("/runs")
def job_runs(job_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc()).limit(20)
    ).all()

@router.get("/{job_id}/runs")
def job_runs_by_path(job_id: str, limit: int = 20, session: Session = Depends(get_session)):
    """Historique des exécutions (JobRun) d'un job, du plus récent au plus ancien."""
    return session.exec(
        select(JobRun)
        .where(JobRun.job_id == job_id)
        .order_by(JobRun.started_at.desc())
        .limit(max(1, min(limit, 200)))
    ).all()

@router.post("/{job_id}/run")
def force_run(job_id: str):
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    scheduler.modify_job(job_id, next_run_time=datetime.datetime.now())
    return {"status": "triggered", "job_id": job_id}

@router.post("/{job_id}/pause")
def pause_job(job_id: str):
    get_scheduler().pause_job(job_id)
    return {"status": "paused"}

@router.post("/{job_id}/resume")
def resume_job(job_id: str):
    get_scheduler().resume_job(job_id)
    return {"status": "resumed"}
