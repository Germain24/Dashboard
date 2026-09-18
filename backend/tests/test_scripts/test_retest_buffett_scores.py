import runpy
import sqlite3
import sys
from pathlib import Path

from app.core.config import settings


def test_retest_saves_deleted_rows_to_nas_before_mutating(tmp_path, monkeypatch):
    database = tmp_path / "mission-control.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE buffett_run_result (
                id INTEGER PRIMARY KEY, run_id INTEGER, ticker TEXT,
                chance_moat REAL, volume REAL, prix REAL
            );
            CREATE TABLE buffett_run (
                id INTEGER PRIMARY KEY, n_tickers_total INTEGER,
                statut TEXT, n_tickers_analyzed INTEGER, progress_pct REAL,
                duree_sec REAL, erreur TEXT
            );
            INSERT INTO buffett_run_result VALUES (1, 42, 'DROP', 0.9, 10, 2);
            INSERT INTO buffett_run_result VALUES (2, 42, 'KEEP', 0.5, 5, 3);
            INSERT INTO buffett_run VALUES (42, 2, 'termine', 2, 100, 1, NULL);
            """
        )

    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "retest_buffett_scores.py"
    nas = tmp_path / "nas"
    monkeypatch.setattr(settings, "backup_dir", str(nas))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--run-id",
            "42",
            "--above",
            "0.7",
            "--database",
            str(database),
            "--apply",
        ],
    )

    namespace = runpy.run_path(str(script))
    namespace["main"]()

    backups = list((nas / "files" / "maintenance" / "retest-buffett-scores").glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as saved:
        assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert saved.execute("SELECT ticker FROM buffett_run_result").fetchone()[0] == "DROP"
    with sqlite3.connect(database) as result:
        tickers = [row[0] for row in result.execute(
            "SELECT ticker FROM buffett_run_result WHERE run_id=42"
        )]
    assert tickers == ["KEEP"]
    assert not (tmp_path / "backups").exists()
