"""FastAPI app entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app import __version__
from app.api import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging


async def _refresh_external_accounts_after_startup() -> None:
    """Rafraîchit les comptes externes sans retarder la readiness HTTP.

    Les fournisseurs blockchain peuvent prendre plusieurs secondes (ou être
    indisponibles). Cette synchronisation est utile au dashboard, mais elle ne
    doit pas empêcher Uvicorn de commencer à servir ``/health``.
    """
    log = logging.getLogger(__name__)

    def refresh() -> dict:
        from sqlmodel import Session

        from app.core.db import engine
        from app.services.finance.external_accounts import refresh_external_accounts

        with Session(engine) as session:
            return refresh_external_accounts(session, force=True)

    try:
        result = await asyncio.to_thread(refresh)
        log.info(
            "Synchronisation des comptes externes terminée (%s)",
            result.get("status", "ok"),
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        # Une intégration externe ne doit jamais faire tomber le serveur.
        log.warning("Synchronisation des comptes externes: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie de l'application (remplace les on_event startup/shutdown dépréciés)."""
    log = logging.getLogger(__name__)
    from sqlmodel import Session

    from app.core.db import engine
    external_refresh_task: asyncio.Task[None] | None = None

    # État des intégrations (présence des secrets, jamais leur valeur — #192).
    from app.core.secrets import integration_status
    log.info("Intégrations configurées: %s", integration_status(settings))

    with Session(engine) as session:
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
        # Purge des playlists musicales aux noms obsolètes (#musique)
        try:
            from app.services.musique.playlists import purge_unknown_ambiances
            n = purge_unknown_ambiances(session)
            if n:
                log.info("Musique : %d appartenances obsolètes purgées", n)
        except Exception as exc:
            log.warning("Purge playlists musique: %s", exc)

    # Démarrer APScheduler
    try:
        from app.services.finance import register_finance_jobs
        from app.services.scheduler.scheduler import get_scheduler, register_all_jobs
        scheduler = get_scheduler()
        register_all_jobs(scheduler)
        register_finance_jobs(scheduler)
        scheduler.start()
        log.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
    except Exception as exc:
        log.warning("APScheduler startup: %s", exc)

    # Les comptes externes sont rafraîchis après la readiness de l'application.
    # Avant ce déplacement, les appels réseau MetaMask/RealT bloquaient le
    # lifespan et le frontend recevait plusieurs ECONNREFUSED au démarrage.
    if "PYTEST_CURRENT_TEST" not in os.environ:
        external_refresh_task = asyncio.create_task(
            _refresh_external_accounts_after_startup(),
            name="refresh-external-accounts",
        )

    yield

    if external_refresh_task is not None and not external_refresh_task.done():
        external_refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await external_refresh_task

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
            "API du dashboard personnel Mission Control : finance, budget, "
            "santé, agenda, entraînement et les autres modules de vie."
        ),
        lifespan=lifespan,
    )
    # Injecte un X-Request-ID sur chaque réponse pour le traçage.
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        # Autorise localhost sur n'importe quel port en dev (port Next variable).
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=settings.cors_methods_list,
        allow_headers=settings.cors_headers_list,
        expose_headers=["X-Total-Count", "Content-Range", "X-Request-ID"],
    )
    # Routes principales versionnées sous /api/v1 (documentées dans l'OpenAPI).
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    # Montage racine conservé pour rétro-compatibilité (non documenté).
    app.include_router(api_router, include_in_schema=False)
    # Compatibilité avec les anciens clients qui appellent /api/*.
    app.include_router(api_router, prefix="/api", include_in_schema=False)
    register_exception_handlers(app)

    # Photos locales (Santé #69, Garde-robe #75) servies depuis data/*_photos/.
    try:
        from pathlib import Path

        from fastapi.staticfiles import StaticFiles

        from app.services.garderobe.photos import photos_dir as garderobe_photos_dir
        from app.services.sante.photos import photos_dir as sante_photos_dir

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
