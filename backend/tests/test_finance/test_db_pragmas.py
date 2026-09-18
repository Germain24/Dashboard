"""Le WAL SQLite doit checkpointer automatiquement plus souvent que le defaut
(~1000 pages) pour eviter le ralentissement progressif observe sur un run
Buffett de plusieurs heures (voir orchestration/a-faire/2026-07-08-buffett-de-
perf-seeds-infinis-design.md)."""

import sqlite3

from app.core.db import _sqlite_pragmas


def test_wal_autocheckpoint_is_lowered(tmp_path):
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    try:
        _sqlite_pragmas(con, None)
        value = con.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
        assert int(value) == 200
    finally:
        con.close()
