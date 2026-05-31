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
    def _sync_portfolio_history() -> None:
        """Lit l'Excel d'historique de portefeuille au demarrage (source editable)."""
        import logging
        try:
            from app.core.db import engine
            from sqlmodel import Session
            from app.services.finance.history_excel import sync_excel_to_db
            with Session(engine) as session:
                sync_excel_to_db(session)
        except Exception as exc:  # ne jamais bloquer le demarrage
            logging.getLogger(__name__).warning("Sync historique Excel au demarrage: %s", exc)

    return app


app = create_app()
