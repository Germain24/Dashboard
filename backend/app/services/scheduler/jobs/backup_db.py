import datetime as dt
import sqlite3
from pathlib import Path

def run(session):
    from app.core.config import settings
    db_url = settings.database_url
    db_path_str = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    db_path = Path(db_path_str)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"{dt.date.today()}.db"
    conn = sqlite3.connect(str(db_path))
    backup_conn = sqlite3.connect(str(dest))
    try:
        conn.backup(backup_conn)
        return f"Backup créé: {dest.name}"
    finally:
        backup_conn.close()
        conn.close()
