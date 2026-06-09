"""Backup quotidien de la base SQLite avec rotation, rétention et contrôle
d'intégrité (#176/#177)."""

import datetime as dt
import sqlite3
from pathlib import Path


def integrity_ok(db_file: Path) -> bool:
    """PRAGMA integrity_check sur un fichier SQLite (#177)."""
    try:
        conn = sqlite3.connect(str(db_file))
        try:
            res = conn.execute("PRAGMA integrity_check").fetchone()
            return bool(res and res[0] == "ok")
        finally:
            conn.close()
    except Exception:
        return False


def prune_backups(backup_dir: Path, keep: int) -> int:
    """Garde les `keep` backups les plus récents (*.db). Retourne le nombre supprimé."""
    backups = sorted(backup_dir.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old in backups[max(0, keep):]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def run(session):
    from app.core.config import settings
    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        # Backup fichier spécifique à SQLite. Sur Postgres (#180), utiliser
        # l'export JSON (/data/export) ou pg_dump côté serveur.
        return "Backup ignoré : base non-SQLite (utiliser /data/export ou pg_dump)."
    db_path_str = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    db_path = Path(db_path_str)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"{dt.date.today()}.db"

    conn = sqlite3.connect(str(db_path))
    backup_conn = sqlite3.connect(str(dest))
    try:
        conn.backup(backup_conn)
    finally:
        backup_conn.close()
        conn.close()

    if not integrity_ok(dest):
        # Backup corrompu : on le retire pour ne pas garder une copie inutilisable.
        try:
            dest.unlink()
        except OSError:
            pass
        raise RuntimeError(f"Backup {dest.name} a échoué le contrôle d'intégrité")

    keep = getattr(settings, "backup_retention_count", 14)
    removed = prune_backups(backup_dir, keep)
    return f"Backup OK: {dest.name} (intégrité vérifiée ; {removed} ancien(s) supprimé(s))"
