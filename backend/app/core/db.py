"""Connexion DB SQLite + helpers de session SQLModel."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings
from app.core.realtime import publish

_IS_SQLITE = settings.database_url.startswith("sqlite")

# `check_same_thread=False` est nécessaire pour SQLite avec FastAPI/threads.
# `timeout` concerne aussi les connexions SQLAlchemy utilisées par les threads
# de progression du portefeuille. Cinq secondes étaient trop courtes pendant
# une grosse mise à jour d'allocation ou un checkpoint APScheduler.
connect_args = (
    {"check_same_thread": False, "timeout": 60.0}
    if _IS_SQLITE
    else {}
)

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
        cur.execute("PRAGMA busy_timeout=60000")  # attend jusqu'à 60 s un verrou
        cur.execute("PRAGMA synchronous=NORMAL")  # bon compromis durabilité/perf en WAL
        cur.execute("PRAGMA foreign_keys=ON")
        # Checkpoint automatique tous les 200 pages (~800 Ko) au lieu du défaut
        # ~1000 : sur un run Buffett de plusieurs heures qui écrit en continu
        # (progression DE), un WAL qui grossit sans être purgé dégrade
        # progressivement chaque lecture/écriture SQLite (mesuré : 815 pages/
        # ~3,2 Mo non checkpointées après quelques heures -> ralentissement 7x).
        cur.execute("PRAGMA wal_autocheckpoint=200")
        cur.close()


def get_session() -> Iterator[Session]:
    """Dependency FastAPI : `session: Session = Depends(get_session)`."""
    with Session(engine) as session:
        yield session


def _domain_for_instance(instance: object) -> str | None:
    if instance.__class__.__name__ in {"Notification", "NotificationPreference"}:
        return "notifications"
    if instance.__class__.__name__ in {"JobRun"}:
        return "jobs"
    module = instance.__class__.__module__
    if not module.startswith("app.models."):
        return None
    domain = module.removeprefix("app.models.").split(".", 1)[0]
    aliases = {
        "films_series": "films-series",
        "notification": "notifications",
        "objectifs_vie": "routines",
        "scheduler": "jobs",
    }
    return aliases.get(domain, domain)


@event.listens_for(Session, "after_flush")
def _collect_realtime_domains(session: Session, _flush_context) -> None:
    domains = session.info.setdefault("_realtime_domains", set())
    for instance in session.new.union(session.dirty).union(session.deleted):
        domain = _domain_for_instance(instance)
        if domain:
            domains.add(domain)


@event.listens_for(Session, "after_commit")
def _publish_realtime_domains(session: Session) -> None:
    domains = session.info.pop("_realtime_domains", set())
    for domain in sorted(domains):
        publish(f"{domain}.changed", invalidate=[[domain]])


@event.listens_for(Session, "after_rollback")
def _discard_realtime_domains(session: Session) -> None:
    session.info.pop("_realtime_domains", None)
