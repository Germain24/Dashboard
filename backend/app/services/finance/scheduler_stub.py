"""
APScheduler stubs for Finance module.
- Daily snapshot at 22:00 (every day)
- Monthly Buffett run on the 1st at 03:00

This module is imported by CONV 13 (scheduler global) and activated there.
Exposed here as standalone functions so they can be called manually too.
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job functions (called by APScheduler or manually)
# ---------------------------------------------------------------------------

def job_daily_snapshot() -> None:
    """Take a portfolio snapshot and store it in DB. Runs daily at 22:00."""
    try:
        from app.core.db import engine
        from sqlmodel import Session
        from app.services.finance.snapshots import take_snapshot_now

        with Session(engine) as session:
            snap = take_snapshot_now(session)
            if snap:
                logger.info(
                    "Snapshot portefeuille: %.2f EUR (%s)",
                    snap.valeur_totale,
                    snap.date,
                )
            else:
                logger.warning("Snapshot ignore: aucune position active")
    except Exception as exc:
        logger.error("Erreur snapshot quotidien: %s", exc, exc_info=True)


def job_monthly_buffett(csv_path: str | None = None) -> None:
    """
    Run the monthly Buffett analysis. Runs on the 1st of each month at 03:00.
    Uses tickers.csv by default (path from Config).
    Long-running — designed to be called in a background thread.
    """
    run_id: int | None = None
    try:
        from app.core.db import engine
        from sqlmodel import Session
        from app.services.finance.buffett import run_buffett_analysis
        from app.services.finance.buffett.config import Config
        from app.services.finance.buffett.reporting import (
            create_run, update_run_progress, finalize_run,
        )

        cfg = Config()
        tickers_csv = csv_path or str(cfg.TICKERS_CSV)

        logger.info(
            "Demarrage analyse Buffett mensuelle (%s)",
            datetime.now().isoformat(),
        )

        with Session(engine) as session:
            run = create_run(session, tickers_csv)
            run_id = run.id

        def on_progress(done: int, total: int, _ticker: str) -> None:
            pct = round(done / max(total, 1) * 100, 1)
            with Session(engine) as s:
                update_run_progress(s, run_id, pct, done, total)

        result = run_buffett_analysis(
            session_factory=lambda: Session(engine),
            csv_path=tickers_csv,
            max_workers=cfg.MAX_WORKERS,
            n_sim=cfg.N_SIM,
            on_progress=on_progress,
        )

        with Session(engine) as session:
            finalize_run(session, run_id, result)

        logger.info(
            "Analyse Buffett terminee — run_id=%d, n_analysed=%d, duree=%.0fs",
            run_id,
            result.get("n_analyzed", 0),
            result.get("duree_sec", 0),
        )
    except Exception as exc:
        logger.error("Erreur analyse Buffett mensuelle: %s", exc, exc_info=True)
        if run_id is not None:
            try:
                from app.core.db import engine
                from sqlmodel import Session
                from app.services.finance.buffett.reporting import finalize_run
                with Session(engine) as s:
                    finalize_run(s, run_id, {"erreur": str(exc)})
            except Exception:
                pass


# ---------------------------------------------------------------------------
# APScheduler registration (called by CONV 13 scheduler setup)
# ---------------------------------------------------------------------------

def register_finance_jobs(scheduler) -> None:  # type: ignore[type-arg]
    """
    Register finance jobs on the provided APScheduler instance.
    Called from the global scheduler setup (CONV 13).
    """
    scheduler.add_job(
        job_daily_snapshot,
        trigger="cron",
        hour=22,
        minute=0,
        id="finance_daily_snapshot",
        name="Finance — snapshot portefeuille 22h",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_monthly_buffett,
        trigger="cron",
        day=1,
        hour=3,
        minute=0,
        id="finance_monthly_buffett",
        name="Finance — analyse Buffett mensuelle 3h",
        replace_existing=True,
        misfire_grace_time=7200,
    )
    logger.info("Finance jobs enregistres: snapshot@22h, buffett@1er-du-mois-3h")
