"""APScheduler stubs for Finance module.
- Daily snapshot at 22:00
- Monthly Buffett run on the 1st at 03:00
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from app.core.config import settings as _settings
from app.core.timeutil import utcnow

logger = logging.getLogger(__name__)

# Verrou in-process : empeche deux analyses simultanees dans le meme process.
# A la reouverture du programme le verrou est neuf -> la reprise est possible.
_ANALYSIS_LOCK = threading.Lock()


def is_analysis_running() -> bool:
    """True si une analyse Buffett tourne actuellement dans ce process."""
    return _ANALYSIS_LOCK.locked()


# Seuil (%) de baisse quotidienne déclenchant une notification.
# Pilotable par .env (FINANCE_SNAPSHOT_DROP_ALERT_PCT).
SNAPSHOT_DROP_ALERT_PCT = _settings.finance_snapshot_drop_alert_pct


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
    from sqlmodel import Session

    from app.core.db import engine
    from app.services.finance.snapshots import (
        drop_alert_pct,
        get_latest_snapshot,
        take_snapshot_now,
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
        from sqlmodel import Session, select

        from app.core.db import engine
        from app.models.finance import BuffettRun, BuffettRunStatus
        from app.services.finance.buffett import run_buffett_analysis
        from app.services.finance.buffett.config import Config
        from app.services.finance.buffett.reporting import (
            archive_legacy_run,
            create_run,
            finalize_run,
            update_run_progress,
        )
        from app.services.finance.buffett.ticker_universe import read_ticker_catalog

        Config.load_params()
        # NB : le warm-up FX (taux devise->EUR de la colonne Volume) est fait
        # dans run_buffett_analysis, APRES la creation du run -- ici il
        # retardait toute trace visible (verrou tenu, aucun run cree) quand
        # Yahoo throttlait (#bug POST /buffett/run "ne fait rien").
        requested_csv = csv_path or str(Config.TICKERS_CSV)
        tickers_csv = requested_csv
        n_total = 0
        params = {"csv_path": requested_csv, "n_tickers": 0, "max_workers": 1}

        # Reprendre le dernier run non termine, sinon en creer un nouveau
        with Session(engine) as session:
            legacy = session.get(BuffettRun, 52)
            if legacy and legacy.statut == BuffettRunStatus.TERMINE.value:
                archive_legacy_run(session, 52)
            existing = session.exec(
                select(BuffettRun)
                .where(BuffettRun.statut.in_([
                    BuffettRunStatus.EN_COURS.value,
                    BuffettRunStatus.INTERROMPU.value,
                ]))  # type: ignore[attr-defined]
                .order_by(BuffettRun.run_date.desc(), BuffettRun.id.desc())  # type: ignore[attr-defined]
            ).first()
            if existing:
                existing.statut = BuffettRunStatus.EN_COURS.value
                existing.updated_at = utcnow()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                run_id = existing.id
                from app.services.finance.buffett.universe_snapshot import (
                    create_universe_snapshot,
                    snapshot_path,
                )
                universe = (existing.params_json or {}).get("universe_snapshot")
                if not isinstance(universe, dict):
                    # Répare un run créé avant l'écriture de son snapshot (par
                    # exemple collision avec un ID SQLite réutilisé). Aucun
                    # scoring supplémentaire ne part sans univers figé.
                    from app.services.finance.catalog.builder import load_registry

                    universe = create_universe_snapshot(
                        Path(requested_csv),
                        run_id=existing.id,
                        destination_dir=Path(Config.DATA_DIR) / "buffett_universes",
                        catalog_version=load_registry().get("version"),
                    )
                    existing.params_json = {
                        **(existing.params_json or {}),
                        "universe_snapshot": universe,
                    }
                    session.add(existing)
                    session.commit()
                    session.refresh(existing)
                    logger.warning(
                        "Run Buffett #%d sans snapshot: univers canonique créé avant reprise",
                        existing.id,
                    )
                tickers_csv = snapshot_path(existing.params_json, requested_csv)
                snapshot_catalog = read_ticker_catalog(
                    tickers_csv, require_canonical=True
                )
                n_total = len(snapshot_catalog.tickers)
                logger.info("Reprise du run Buffett interrompu #%d", run_id)
                if existing.id == 52:
                    logger.warning(
                        "Reprise du run %s : les tickers deja analyses avant le passage "
                        "de la colonne Volume en euros gardent un volume en nb d'actions "
                        "(unites melangees sur CE run uniquement, pas de migration).",
                        existing.id,
                    )
            else:
                # Le catalogue doit être entièrement valide AVANT de créer une
                # ligne de run. Une erreur de lecture ne doit plus produire un
                # faux run terminé/échoué avec zéro ticker.
                source_catalog = read_ticker_catalog(
                    requested_csv, require_canonical=True
                )
                n_total = len(source_catalog.tickers)
                params["n_tickers"] = n_total
                run = create_run(session, n_total, params)
                run_id = run.id
                from app.services.finance.buffett.universe_snapshot import create_universe_snapshot
                from app.services.finance.catalog.builder import load_registry
                universe = create_universe_snapshot(
                    Path(requested_csv),
                    run_id=run_id,
                    destination_dir=Path(Config.DATA_DIR) / "buffett_universes",
                    catalog_version=load_registry().get("version"),
                )
                run.params_json = {**params, "universe_snapshot": universe}
                session.add(run)
                session.commit()
                tickers_csv = universe["snapshot_path"]
                logger.info("Nouveau run Buffett #%d — %d tickers", run_id, n_total)

        def on_progress(done: int, total: int) -> None:
            with Session(engine) as s:
                update_run_progress(s, run_id, done, total)

        result = run_buffett_analysis(
            session_factory=lambda: Session(engine),
            csv_path=tickers_csv,
            max_workers=1,
            on_progress=on_progress,
            run_id=run_id,
            initial_total=n_total,
        )

        duree = (datetime.now() - start_time).total_seconds()
        erreur = result.get("error") or result.get("erreur")

        with Session(engine) as session:
            finalize_run(
                session, run_id,
                statut=BuffettRunStatus.ERREUR.value if erreur else BuffettRunStatus.TERMINE.value,
                duree_sec=duree,
                erreur=str(erreur) if erreur else None,
            )

        logger.info(
            "Analyse Buffett terminee — run_id=%s, n_analyses=%d, duree=%.0fs",
            run_id, result.get("n_analyzed", 0), duree,
        )

    except Exception as exc:
        logger.error("Erreur analyse Buffett: %s", exc, exc_info=True)
        # La traceback complète est persistée, pas seulement `str(exc)` : un run
        # planté la nuit ne laissait qu'une phrase, rendant chaque incident
        # indiagnosticable après coup (cf. audit §3.C). On borne la taille pour
        # ne pas gonfler la ligne indéfiniment.
        import traceback

        trace = traceback.format_exc()
        detail = f"{exc}\n\n{trace}"[-6000:]
        # On marque "interrompu" (et non "erreur") pour permettre une reprise.
        if run_id is not None:
            try:
                from sqlmodel import Session

                from app.core.db import engine
                from app.models.finance import BuffettRun, BuffettRunStatus
                with Session(engine) as s:
                    run = s.get(BuffettRun, run_id)
                    if run and run.statut == BuffettRunStatus.EN_COURS.value:
                        run.statut = BuffettRunStatus.INTERROMPU.value
                        run.erreur = detail
                        run.updated_at = utcnow()
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
