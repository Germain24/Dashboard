"""Invalide une tranche de résultats Buffett afin de la recalculer.

Le catalogue et les données financières locales ne sont jamais supprimés. Les
lignes retirées sont copiées dans une petite base SQLite de sauvegarde avant la
transaction destructive.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--above", type=float, required=True)
    parser.add_argument("--database", type=Path, default=Path("data/mission-control.db"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    database = args.database.resolve()
    connection = sqlite3.connect(database, timeout=30)
    connection.execute("PRAGMA busy_timeout=30000")
    where = "run_id = ? AND chance_moat > ?"
    parameters = (args.run_id, args.above)
    affected = connection.execute(
        f"SELECT COUNT(*) FROM buffett_run_result WHERE {where}", parameters
    ).fetchone()[0]
    if not args.apply:
        print({"run_id": args.run_id, "above": args.above, "affected": affected})
        return
    if affected <= 0:
        print({"run_id": args.run_id, "deleted": 0, "reason": "no_matching_rows"})
        return

    backup_root = str(settings.backup_dir or "").strip()
    if not backup_root:
        raise RuntimeError("BACKUP_DIR n'est pas configuré : sauvegarde NAS impossible.")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = Path(backup_root) / "files" / "maintenance" / "retest-buffett-scores" / (
        f"run{args.run_id}-score-gt-{args.above:g}-before-v3-{stamp}.db"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    connection.execute("ATTACH DATABASE ? AS score_backup", (str(backup),))
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            f"CREATE TABLE score_backup.buffett_run_result AS "
            f"SELECT * FROM main.buffett_run_result WHERE {where}",
            parameters,
        )
        saved = connection.execute(
            "SELECT COUNT(*) FROM score_backup.buffett_run_result"
        ).fetchone()[0]
        if saved != affected:
            raise RuntimeError(f"sauvegarde incomplète: {saved}/{affected}")
        integrity = connection.execute("PRAGMA score_backup.integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"intégrité incorrecte pour la sauvegarde NAS: {integrity}")
        connection.execute(
            f"DELETE FROM main.buffett_run_result WHERE {where}", parameters
        )
        remaining = connection.execute(
            "SELECT COUNT(*) FROM main.buffett_run_result WHERE run_id = ?",
            (args.run_id,),
        ).fetchone()[0]
        total = connection.execute(
            "SELECT n_tickers_total FROM main.buffett_run WHERE id = ?",
            (args.run_id,),
        ).fetchone()[0]
        # Une tâche fondamentale peut produire plusieurs cotations secondaires.
        # Le nombre de lignes restantes peut donc dépasser le total de tâches;
        # l'estimation de reprise doit rester bornée. Le runner la corrigera avec
        # le nombre exact de symboles primaires dès son démarrage.
        progress_done = max(0, int(total) - int(affected))
        connection.execute(
            """
            UPDATE main.buffett_run
            SET statut = 'interrompu', n_tickers_analyzed = ?, progress_pct = ?,
                duree_sec = NULL, erreur = 'Recalcul ciblé Score V3 en attente'
            WHERE id = ?
            """,
            (
                progress_done,
                round(progress_done / max(total, 1) * 100.0, 2),
                args.run_id,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        backup.unlink(missing_ok=True)
        raise
    finally:
        connection.close()

    print(
        {
            "run_id": args.run_id,
            "backup": str(backup),
            "saved": saved,
            "deleted": affected,
            "remaining": remaining,
            "run_total": total,
        }
    )


if __name__ == "__main__":
    main()
