"""Connexion DB SQLite + helpers de session SQLModel."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings

_IS_SQLITE = settings.database_url.startswith("sqlite")

# `check_same_thread=False` est nécessaire pour SQLite avec FastAPI/threads.
connect_args = {"check_same_thread": False} if _IS_SQLITE else {}

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
)


if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _conn_record) -> None:
        """WAL + busy_timeout : réduit les "database is locked" quand les jobs
        APScheduler écrivent en même temps que les requêtes HTTP."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")  # attend jusqu'à 5 s un verrou
        cur.execute("PRAGMA synchronous=NORMAL")  # bon compromis durabilité/perf en WAL
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def get_session() -> Iterator[Session]:
    """Dependency FastAPI : `session: Session = Depends(get_session)`."""
    with Session(engine) as session:
        yield session
