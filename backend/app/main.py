"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie de l'application (remplace les on_event startup/shutdown dépréciés)."""
    log = logging.getLogger(__name__)
    from app.core.db import engine
    from sqlmodel import Session

    # État des intégrations (présence des secrets, jamais leur valeur — #192).
    from app.core.secrets import integration_status
    log.info("Intégrations configurées: %s", integration_status(settings))

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
        # Seed produits skincare par défaut
        try:
            from app.services.skincare.products import seed_skincare
            seed_skincare(session)
        except Exception as exc:
            log.warning("Seed skincare: %s", exc)

    # Démarrer Ollama si besoin (module Musique) — en arrière-plan, ne bloque pas le boot.
    if settings.musique_ollama_autostart:
        import threading

        def _start_ollama() -> None:
            try:
                from app.services.musique.ollama_client import ensure_running
                ok = ensure_running()
                log.info("Ollama: %s", "prêt" if ok else "non démarré (classement musique indispo)")
            except Exception as exc:  # pragma: no cover — défensif
                log.warning("Ollama autostart: %s", exc)

        threading.Thread(target=_start_ollama, daemon=True).start()

    # Démarrer APScheduler
    try:
        from app.services.scheduler.scheduler import get_scheduler, register_all_jobs
        from app.services.finance import register_finance_jobs
        scheduler = get_scheduler()
        register_all_jobs(scheduler)
        register_finance_jobs(scheduler)
        scheduler.start()
        log.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
    except Exception as exc:
        log.warning("APScheduler startup: %s", exc)

    yield

    # Arrêt propre du scheduler
    try:
        from app.services.scheduler.scheduler import get_scheduler
        get_scheduler().shutdown(wait=False)
    except Exception:
        pass


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(
        title="Mission Control API",
        version=__version__,
        description=(
            "API du dashboard personnel Mission Control. "
            "En CONV 1, seuls /health et les /ping de chaque module sont actifs."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        # Autorise localhost sur n'importe quel port en dev (port Next variable).
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=settings.cors_methods_list,
        allow_headers=settings.cors_headers_list,
        expose_headers=["X-Total-Count", "Content-Range"],
    )
    # Routes principales versionnées sous /api/v1 (documentées dans l'OpenAPI).
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    # Montage racine conservé pour rétro-compatibilité (non documenté).
    app.include_router(api_router, include_in_schema=False)
    register_exception_handlers(app)

    # Photos locales (Santé #69, Garde-robe #75) servies depuis data/*_photos/.
    try:
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles
        from app.services.sante.photos import photos_dir as sante_photos_dir
        from app.services.garderobe.photos import photos_dir as garderobe_photos_dir

        for url, directory in (
            ("/media/sante", sante_photos_dir()),
            ("/media/garderobe", garderobe_photos_dir()),
        ):
            directory.mkdir(parents=True, exist_ok=True)
            app.mount(url, StaticFiles(directory=str(directory)), name=url.strip("/").replace("/", "-"))

        music_path = Path(settings.music_dir)
        if music_path.exists():
            app.mount("/media/music", StaticFiles(directory=str(music_path)), name="media-music")
    except Exception:  # pragma: no cover — défensif (ne bloque pas le démarrage)
        logging.getLogger(__name__).warning("Montage /media indisponible", exc_info=True)

    return app


app = create_app()
