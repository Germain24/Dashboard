"""FastAPI app entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title="Mission Control API",
        version=__version__,
        description=(
            "API du dashboard personnel Mission Control. "
            "En CONV 1, seuls /health et les /ping de chaque module sont actifs."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.on_event("startup")
    def _on_startup() -> None:
        import logging
        log = logging.getLogger(__name__)
        from app.core.db import engine
        from sqlmodel import Session
        with Session(engine) as session:
            # Sync historique Excel Finance
            try:
                from app.services.finance.history_excel import sync_excel_to_db
                sync_excel_to_db(session)
            except Exception as exc:
                log.warning("Sync Excel: %s", exc)
            # Seed catégories Budget
            try:
                from app.services.budget.categories import seed_categories
                seed_categories(session)
            except Exception as exc:
                log.warning("Seed budget categories: %s", exc)
            # Seed habitudes par défaut
            try:
                from app.services.habitudes.entries import seed_habits
                seed_habits(session)
            except Exception as exc:
                log.warning("Seed habitudes: %s", exc)
        # Démarrer APScheduler
        try:
            from app.services.scheduler.scheduler import get_scheduler, register_all_jobs
            scheduler = get_scheduler()
            register_all_jobs(scheduler)
            scheduler.start()
            log.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
        except Exception as exc:
            log.warning("APScheduler startup: %s", exc)

    @app.on_event("shutdown")
    def _on_shutdown() -> None:
        try:
            from app.services.scheduler.scheduler import get_scheduler
            get_scheduler().shutdown(wait=False)
        except Exception:
            pass

    return app


app = create_app()
