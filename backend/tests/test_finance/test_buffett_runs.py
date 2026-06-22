"""Suppression d'un run Buffett (analyse bloquée) — run + résultats."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.finance import BuffettRun, BuffettRunResult
from app.services.finance.buffett.reporting import delete_run


def _fk_engine():
    """SQLite avec FK ACTIVÉES (comme en prod) — sinon le test ne reproduit pas
    la contrainte qui faisait échouer delete_run."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    return engine


def test_delete_run_removes_run_and_its_results():
    engine = _fk_engine()
    with Session(engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="interrompu")
        s.add(run)
        s.commit()
        s.refresh(run)
        s.add(BuffettRunResult(run_id=run.id, ticker="AAPL", chance_moat=80.0))
        s.commit()

        assert delete_run(s, run.id) is True
        assert s.get(BuffettRun, run.id) is None
        assert s.exec(select(BuffettRunResult).where(BuffettRunResult.run_id == run.id)).all() == []


def test_delete_run_returns_false_when_absent():
    with Session(_fk_engine()) as s:
        assert delete_run(s, 9999) is False
