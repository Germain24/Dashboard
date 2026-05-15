"""Connexion DB SQLite + helpers de session SQLModel."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, create_engine

from app.core.config import settings

# `check_same_thread=False` est nécessaire pour SQLite avec FastAPI/threads.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
)


def get_session() -> Iterator[Session]:
    """Dependency FastAPI : `session: Session = Depends(get_session)`."""
    with Session(engine) as session:
        yield session
