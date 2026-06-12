from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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
    from app.services.scheduler.jobs import (
        agenda_reminders,
        automatisations,
        backup_db,
        habit_reminders,
        ical_sync,
        nutrition_plan,
        portfolio_snapshot,
        snapshot,
        weather_refresh,
    )
    from app.services.scheduler.runner import run_job
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
    scheduler.add_job(run_job, "cron", minute="*/15",
                      args=["agenda_reminders", agenda_reminders.run],
                      id="agenda_reminders", replace_existing=True, misfire_grace_time=600)
    scheduler.add_job(run_job, "cron", hour=20, minute=0,
                      args=["habit_reminders", habit_reminders.run],
                      id="habit_reminders", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour="*/6", minute=10,
                      args=["ical_sync", ical_sync.run],
                      id="ical_sync", replace_existing=True, misfire_grace_time=3600)
    from app.services.scheduler import purge
    scheduler.add_job(run_job, "cron", hour=4, minute=0,
                      args=["purge_old", purge.run],
                      id="purge_old", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour=7, minute=0,
                      args=["briefing_matin", automatisations.run_briefing_matin],
                      id="briefing_matin", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour=21, minute=0,
                      args=["recap_soir", automatisations.run_recap_soir],
                      id="recap_soir", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(run_job, "cron", hour=23, minute=55,
                      args=["daily_snapshot", snapshot.run],
                      id="daily_snapshot", replace_existing=True, misfire_grace_time=3600)
