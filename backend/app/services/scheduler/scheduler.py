import datetime as dt

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler: AsyncIOScheduler | None = None


def get_scheduler(db_url: str | None = None) -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        if db_url is None:
            # Réutiliser le moteur applicatif est important sur SQLite : il
            # porte le WAL et le busy_timeout. Un SQLAlchemyJobStore construit
            # uniquement avec `url` créait une seconde connexion SQLite avec
            # le délai par défaut de 5 s, exactement celle qui échouait pendant
            # les grosses écritures de Buffett.
            from app.core.db import engine

            jobstores = {"default": SQLAlchemyJobStore(engine=engine)}
        else:
            jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
        _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Montreal")
    return _scheduler


def register_all_jobs(scheduler: AsyncIOScheduler) -> None:
    from app.core.realtime import publish
    from app.services.scheduler.jobs import (
        agenda_reminders,
        auto_plan,
        automatisations,
        backup_db,
        course_revisions,
        credit_reminders,
        habit_reminders,
        housekeeping,
        ical_sync,
        nutrition_plan,
        portfolio_snapshot,
        snapshot,
        weather_refresh,
        weekly_trash,
    )
    from app.services.scheduler.runner import run_job

    scheduler.add_job(
        publish,
        "cron",
        hour=0,
        minute=0,
        kwargs={
            "topic": "system.day_changed",
            "invalidate": [["finance"], ["agenda"], ["habitudes"], ["sante"]],
        },
        id="system_day_changed",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=22,
        minute=0,
        args=["portfolio_snapshot", portfolio_snapshot.run],
        id="portfolio_snapshot",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=6,
        minute=30,
        args=["nutrition_plan", nutrition_plan.run],
        id="nutrition_plan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=0,
        minute=0,
        args=["backup_db", backup_db.run],
        id="backup_db",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour="6,12,18,0",
        minute=0,
        args=["weather_refresh", weather_refresh.run],
        id="weather_refresh",
        replace_existing=True,
    )
    scheduler.add_job(
        run_job,
        "cron",
        minute="*/15",
        args=["agenda_reminders", agenda_reminders.run],
        id="agenda_reminders",
        replace_existing=True,
        misfire_grace_time=600,
    )
    # CHAQUE matin, et non le seul dimanche : `ensure_weekly_trash_reminder`
    # vise le dimanche courant ou suivant et est idempotent (source_id unique par
    # dimanche). Cadencé au dimanche, le rappel n'apparaissait dans l'agenda que
    # le jour même — invisible le reste de la semaine.
    scheduler.add_job(
        run_job,
        "cron",
        hour=6,
        minute=5,
        args=["weekly_trash", weekly_trash.run],
        id="weekly_trash",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=6,
        minute=20,
        args=["housekeeping", housekeeping.run],
        id="housekeeping",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=20,
        minute=0,
        args=["habit_reminders", habit_reminders.run],
        id="habit_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "interval",
        hours=1,
        args=["ical_sync", ical_sync.run],
        id="ical_sync",
        replace_existing=True,
        misfire_grace_time=3600,
        next_run_time=dt.datetime.now(scheduler.timezone),
    )
    scheduler.add_job(
        run_job,
        "cron",
        day=5,
        hour=8,
        minute=0,
        args=["credit_reminders", credit_reminders.run],
        id="credit_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    from app.services.scheduler import purge

    scheduler.add_job(
        run_job,
        "cron",
        hour=4,
        minute=0,
        args=["purge_old", purge.run],
        id="purge_old",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=7,
        minute=0,
        args=["briefing_matin", automatisations.run_briefing_matin],
        id="briefing_matin",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=21,
        minute=0,
        args=["recap_soir", automatisations.run_recap_soir],
        id="recap_soir",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=23,
        minute=55,
        args=["daily_snapshot", snapshot.run],
        id="daily_snapshot",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=8,
        minute=0,
        args=["courses_check", automatisations.run_courses_check],
        id="courses_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=8,
        minute=10,
        args=["skincare_reorder", automatisations.run_skincare_reorder],
        id="skincare_reorder",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        day=1,
        hour=7,
        minute=30,
        args=["budget_rebalancing", automatisations.run_budget_rebalancing],
        id="budget_rebalancing",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_job,
        "cron",
        hour=7,
        minute=15,
        args=["anomaly_detection", automatisations.run_anomaly_detection],
        id="anomaly_detection",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Replanifie le cycle (sport, études, repas, batch cooking) chaque jour de
    # cuisine, désormais LUNDI & MERCREDI (rabais étudiant Super C lun→mer, cf.
    # agenda.planner.COOKING_WEEKDAYS). Lundi couvre (mar, mer) et mercredi
    # couvre (jeu → lundi suivant) : les deux cycles pavent la semaine entière.
    scheduler.add_job(
        run_job,
        "cron",
        day_of_week="mon,wed",
        hour=6,
        minute=0,
        args=["auto_plan", auto_plan.run],
        id="auto_plan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Prépare les révisions de la semaine dimanche matin, avant l'ouverture
    # Shopify de 12 h. Les shifts et les cours sont déjà des obstacles fixes.
    scheduler.add_job(
        run_job,
        "cron",
        day_of_week="sun",
        hour=6,
        minute=30,
        args=["course_revisions", course_revisions.run],
        id="course_revisions",
        replace_existing=True,
        misfire_grace_time=3600,
    )
