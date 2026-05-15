"""Healthcheck — endpoint sans dépendance utilisé par le frontend pour s'assurer
que le backend répond."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app import __version__
from app.core.config import settings
from app.core.db import engine

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    env: str
    timezone: str
    db: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_status = "ok"
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        env=settings.app_env,
        timezone=settings.timezone,
        db=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
