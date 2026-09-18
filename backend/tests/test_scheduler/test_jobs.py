import datetime as dt
from pathlib import Path

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.scheduler.jobs.backup_db import get_backup_directory, integrity_ok


def test_backup_path_uses_configured_nas_directory():
    db_path = Path("data/mission-control.db")
    assert get_backup_directory("Z:/BackUp/mission-control", db_path) == Path(
        "Z:/BackUp/mission-control"
    )
    with pytest.raises(RuntimeError, match="BACKUP_DIR n'est pas configuré"):
        get_backup_directory(None, db_path)


def test_backup_job_writes_verified_copy_to_configured_directory(tmp_path, monkeypatch):
    import sqlite3

    from app.core.config import settings
    from app.services.scheduler.jobs import backup_db

    source = tmp_path / "mission-control.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")
        conn.execute("INSERT INTO sample VALUES ('preserved')")

    nas_directory = tmp_path / "nas" / "mission-control"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source.as_posix()}")
    monkeypatch.setattr(settings, "backup_dir", str(nas_directory))
    monkeypatch.setattr(settings, "backup_retention_count", 0)

    result = backup_db.run(None)

    destination = nas_directory / f"{dt.date.today()}.db"
    assert destination.is_file()
    assert integrity_ok(destination)
    assert "Backup OK" in result
    assert not (tmp_path / "backups").exists()


def test_backup_job_fails_closed_without_nas_directory(tmp_path, monkeypatch):
    import sqlite3

    from app.core.config import settings
    from app.services.scheduler.jobs import backup_db

    source = tmp_path / "mission-control.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE sample (value TEXT)")

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source.as_posix()}")
    monkeypatch.setattr(settings, "backup_dir", "")

    with pytest.raises(RuntimeError, match="BACKUP_DIR n'est pas configuré"):
        backup_db.run(None)
    assert not (tmp_path / "backups").exists()


def test_register_all_jobs_includes_expected():
    """register_all_jobs enregistre tous les jobs attendus (source de vérité dynamique)."""
    from app.services.scheduler.scheduler import register_all_jobs

    scheduler = AsyncIOScheduler(timezone="America/Montreal")  # jobstore mémoire
    register_all_jobs(scheduler)
    ids = {j.id for j in scheduler.get_jobs()}
    for expected in (
        "portfolio_snapshot",
        "nutrition_plan",
        "backup_db",
        "weather_refresh",
        "agenda_reminders",
        "habit_reminders",
        "purge_old",
        "auto_plan",
        "credit_reminders",
        "weekly_trash",
        "course_revisions",
        "ical_sync",
    ):
        assert expected in ids, f"job manquant : {expected}"
    ical_job = scheduler.get_job("ical_sync")
    assert ical_job is not None
    assert ical_job.trigger.interval.total_seconds() == 60 * 60
    assert -60 < (ical_job.next_run_time - dt.datetime.now(scheduler.timezone)).total_seconds() <= 0
