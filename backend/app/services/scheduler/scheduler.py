from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

_scheduler: AsyncIOScheduler | None = None

def get_scheduler(db_url: str | None = None) -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        if db_url is None:
            from app.core.config import settings
            db_url = settings.database_url
        jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
        _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Montreal")
    return _scheduler

def register_all_jobs(scheduler: AsyncIOScheduler) -> None:
    from app.services.scheduler.runner import run_job
    from app.services.scheduler.jobs import portfolio_snapshot, nutrition_plan, backup_db, weather_refresh
    scheduler.add_job(run_job, "cron", hour=22, minute=0,
                      args=["portfolio_snapshot", portfolio_snapshot.run],
                      id="portfolio_snapshot", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour=6, minute=30,
                      args=["nutrition_plan", nutrition_plan.run],
                      id="nutrition_plan", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour=0, minute=0,
                      args=["backup_db", backup_db.run],
                      id="backup_db", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour="6,12,18,0", minute=0,
                      args=["weather_refresh", weather_refresh.run],
                      id="weather_refresh", replace_existing=True)
