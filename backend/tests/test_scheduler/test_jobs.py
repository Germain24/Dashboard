from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def test_backup_path_construction():
    db_url = "sqlite:///data/mission-control.db"
    db_path_str = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    backup_dir = Path(db_path_str).parent / "backups"
    assert backup_dir == Path("data/backups")


def test_register_all_jobs_includes_expected():
    """register_all_jobs enregistre tous les jobs attendus (source de vérité dynamique)."""
    from app.services.scheduler.scheduler import register_all_jobs

    scheduler = AsyncIOScheduler(timezone="America/Montreal")  # jobstore mémoire
    register_all_jobs(scheduler)
    ids = {j.id for j in scheduler.get_jobs()}
    for expected in (
        "portfolio_snapshot", "nutrition_plan", "backup_db", "weather_refresh",
        "agenda_reminders", "habit_reminders", "purge_old",
    ):
        assert expected in ids, f"job manquant : {expected}"
