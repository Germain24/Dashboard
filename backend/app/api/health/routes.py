"""Healthcheck — endpoint sans dépendance utilisé par le frontend pour s'assurer
que le backend répond."""

from __future__ import annotations

import functools
import os
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import text
from sqlmodel import Session

from app import __version__
from app.api.health.schemas import HealthResponse
from app.core.config import settings
from app.core.db import engine

router = APIRouter()


def _db_ok() -> bool:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_status = "ok" if _db_ok() else "error"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
        timezone=settings.timezone,
        db=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/health/live")
def health_live() -> dict:
    """Liveness : le process répond. N'effectue aucune vérification de dépendance."""
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(response: Response) -> dict:
    """Readiness : prêt à servir (DB joignable). Renvoie 503 sinon."""
    ok = _db_ok()
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "not_ready", "db": "ok" if ok else "error"}


@functools.lru_cache(maxsize=1)
def _git_sha() -> str:
    # Priorité à la variable d'env (utile en conteneur où le .git est absent).
    env_sha = os.environ.get("GIT_SHA") or os.environ.get("SOURCE_COMMIT")
    if env_sha:
        return env_sha.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(settings.repo_root),
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


@router.get("/version")
def version() -> dict:
    """Version applicative + sha git + date de build."""
    build_date = os.environ.get("BUILD_DATE") or datetime.now(timezone.utc).isoformat()
    return {
        "version": __version__,
        "git_sha": _git_sha(),
        "build_date": build_date,
        "env": settings.app_env,
    }
