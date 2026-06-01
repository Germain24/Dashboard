from pathlib import Path
from app.api.routes_scheduler import JOB_IDS


def test_backup_path_construction():
    db_url = "sqlite:///data/mission-control.db"
    db_path_str = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    backup_dir = Path(db_path_str).parent / "backups"
    assert backup_dir == Path("data/backups")


def test_job_ids_complete():
    assert "portfolio_snapshot" in JOB_IDS
    assert "backup_db" in JOB_IDS
    assert "weather_refresh" in JOB_IDS
    assert "nutrition_plan" in JOB_IDS
    assert len(JOB_IDS) == 4
