"""APScheduler stubs for Finance module.
- Daily snapshot at 22:00
- Monthly Buffett run on the 1st at 03:00
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# Verrou in-process : empeche deux analyses simultanees dans le meme process.
# A la reouverture du programme le verrou est neuf -> la reprise est possible.
_ANALYSIS_LOCK = threading.Lock()


def is_analysis_running() -> bool:
    """True si une analyse Buffett tourne actuellement dans ce process."""
    return _ANALYSIS_LOCK.locked()


# Seuil (%) de baisse quotidienne déclenchant une notification.
SNAPSHOT_DROP_ALERT_PCT = 5.0


def _notify(session, titre: str, message: str, level: str) -> None:
    """Crée une notification (best-effort)."""
    try:
        from app.models.scheduler import Notification
        session.add(Notification(source="finance_snapshot", titre=titre, message=message, level=level))
        session.commit()
    except Exception as exc:
        logger.warning("Notification snapshot: %s", exc)


def job_daily_snapshot() -> None:
    """Snapshot portefeuille quotidien (22h).

    Crée une notification si le snapshot échoue (error) ou si la valeur chute de
    plus de SNAPSHOT_DROP_ALERT_PCT vs le snapshot précédent (warning).
    """
    from app.core.db import engine
    from sqlmodel import Session
    from app.services.finance.snapshots import (
        take_snapshot_now, get_latest_snapshot, drop_alert_pct,
    )

    try:
        with Session(engine) as session:
            prev = get_latest_snapshot(session)
            prev_val = prev.valeur if prev else None

            snap = take_snapshot_now(session)
            if not snap:
                logger.warning("Snapshot ignore: aucune position active")
                return

            logger.info("Snapshot portefeuille: %.2f EUR (%s)", snap.valeur, snap.date)

            # Alerte de chute (on ignore le cas où prev == le snapshot du jour ré-écrit)
            if prev and prev.date != snap.date:
                drop = drop_alert_pct(prev_val, snap.valeur, SNAPSHOT_DROP_ALERT_PCT)
                if drop is not None:
                    _notify(
                        session,
                        titre=f"Chute du portefeuille : -{drop:.1f} %",
                        message=f"Valeur passée de {prev_val:.0f} à {snap.valeur:.0f} EUR depuis le {prev.date}.",
                        level="warning",
                    )
    except Exception as exc:
        logger.error("Erreur snapshot quotidien: %s", exc, exc_info=True)
        try:
            with Session(engine) as session:
                _notify(session, titre="Échec du snapshot quotidien",
                        message=str(exc), level="error")
        except Exception:
            pass


def job_monthly_buffett(csv_path: str | None = None) -> None:
    """Run Buffett (manuel ou 1er du mois 3h). BackgroundTask FastAPI.

    - Verrou in-process : ignore l'appel si une analyse tourne deja ici.
    - **Reprise** : reprend le dernier run interrompu (statut en_cours/interrompu)
      au lieu d'en creer un nouveau ; le runner saute alors les tickers deja faits.
    """
    if not _ANALYSIS_LOCK.acquire(blocking=False):
        logger.info("Analyse Buffett deja en cours dans ce process -> appel ignore")
        return

    run_id: int | None = None
    start_time = datetime.now()

    try:
        from app.core.db import engine
        from sqlmodel import Session, select
        from app.services.finance.buffett import run_buffett_analysis
        from app.services.finance.buffett.config import Config
        from app.services.finance.buffett.runner import load_tickers
        from app.services.finance.buffett.reporting import (
            create_run, update_run_progress, finalize_run,
        )
        from app.models.finance import BuffettRun

        Config.load_params()
        tickers_csv = csv_path or str(Config.TICKERS_CSV)
        tickers = load_tickers(tickers_csv)
        n_total = len(tickers)

        params = {"csv_path": tickers_csv, "n_tickers": n_total, "max_workers": 10}

        # Reprendre le dernier run non termine, sinon en creer un nouveau
        with Session(engine) as session:
            existing = session.exec(
                select(BuffettRun)
                .where(BuffettRun.statut.in_(["en_cours", "interrompu"]))  # type: ignore[attr-defined]
                .order_by(BuffettRun.run_date.desc(), BuffettRun.id.desc())  # type: ignore[attr-defined]
            ).first()
            if existing:
                existing.statut = "en_cours"
                existing.updated_at = datetime.utcnow()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                run_id = existing.id
                logger.info("Reprise du run Buffett interrompu #%d", run_id)
            else:
                run = create_run(session, n_total, params)
                run_id = run.id
                logger.info("Nouveau run Buffett #%d — %d tickers", run_id, n_total)

        def on_progress(done: int, total: int) -> None:
            with Session(engine) as s:
                update_run_progress(s, run_id, done, total)

        result = run_buffett_analysis(
            session_factory=lambda: Session(engine),
            csv_path=tickers_csv,
            max_workers=10,
            on_progress=on_progress,
            run_id=run_id,
        )

        duree = (datetime.now() - start_time).total_seconds()
        erreur = result.get("error") or result.get("erreur")

        with Session(engine) as session:
            finalize_run(
                session, run_id,
                statut="erreur" if erreur else "termine",
                duree_sec=duree,
                erreur=str(erreur) if erreur else None,
            )

        logger.info(
            "Analyse Buffett terminee — run_id=%s, n_analyses=%d, duree=%.0fs",
            run_id, result.get("n_analyzed", 0), duree,
        )

    except Exception as exc:
        logger.error("Erreur analyse Buffett: %s", exc, exc_info=True)
        # On marque "interrompu" (et non "erreur") pour permettre une reprise.
        if run_id is not None:
            try:
                from app.core.db import engine
                from sqlmodel import Session
                from app.models.finance import BuffettRun
                with Session(engine) as s:
                    run = s.get(BuffettRun, run_id)
                    if run and run.statut == "en_cours":
                        run.statut = "interrompu"
                        run.erreur = str(exc)
                        run.updated_at = datetime.utcnow()
                        s.add(run)
                        s.commit()
            except Exception:
                pass
    finally:
        _ANALYSIS_LOCK.release()


def register_finance_jobs(scheduler) -> None:
    scheduler.add_job(
        job_daily_snapshot, trigger="cron", hour=22, minute=0,
        id="finance_daily_snapshot",
        name="Finance snapshot portefeuille 22h",
        replace_existing=True, misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_monthly_buffett, trigger="cron", day=1, hour=3, minute=0,
        id="finance_monthly_buffett",
        name="Finance analyse Buffett mensuelle 3h",
        replace_existing=True, misfire_grace_time=7200,
    )
    logger.info("Finance jobs enregistres: snapshot@22h, buffett@1er-du-mois-3h")
