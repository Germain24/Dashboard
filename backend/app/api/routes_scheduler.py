import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.scheduler import JobRun
from app.services.scheduler.scheduler import get_scheduler

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

JOB_IDS = ["portfolio_snapshot", "nutrition_plan", "backup_db", "weather_refresh"]

@router.get("/list")
def list_jobs(session: Session = Depends(get_session)):
    scheduler = get_scheduler()
    result = []
    for job_id in JOB_IDS:
        job = scheduler.get_job(job_id)
        last_run = session.exec(
            select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc())
        ).first()
        result.append({
            "job_id": job_id,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "paused": job is None or job.next_run_time is None,
            "last_run": last_run,
        })
    return result

@router.get("/runs")
def job_runs(job_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc()).limit(20)
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
