"""Persistance des résultats Buffett en DB (BuffettRun + BuffettRunResult)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session, select

from app.models.finance import BuffettRun, BuffettRunResult


def create_run(session: Session, n_total: int, params: dict) -> BuffettRun:
    """Crée un run en statut 'running'."""
    run = BuffettRun(
        run_date=dt.date.today(),
        statut="running",
        n_tickers_total=n_total,
        n_tickers_analyzed=0,
        progress_pct=0.0,
        params_json=params,
        updated_at=dt.datetime.utcnow(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_run_progress(session: Session, run_id: int, n_done: int, n_total: int) -> None:
    """Met à jour la progression d'un run en cours."""
    run = session.get(BuffettRun, run_id)
    if run:
        run.n_tickers_analyzed = n_done
        run.progress_pct = round(n_done / n_total * 100, 1) if n_total else 0
        run.updated_at = dt.datetime.utcnow()
        session.add(run)
        session.commit()


def finalize_run(
    session: Session, run_id: int, statut: str, duree_sec: float, erreur: str | None = None
) -> None:
    """Clôture un run (completed ou error)."""
    run = session.get(BuffettRun, run_id)
    if run:
        run.statut = statut
        run.duree_sec = duree_sec
        run.progress_pct = 100.0 if statut == "completed" else run.progress_pct
        run.erreur = erreur
        run.updated_at = dt.datetime.utcnow()
        session.add(run)
        session.commit()


def upsert_result(session: Session, run_id: int, ticker: str, score: float, metrics: dict) -> None:
    """Upsert un BuffettRunResult (1 ticker scoré pour ce run).

    Race condition safe : on attrape IntegrityError (note 13 du PLAN).
    """
    from sqlalchemy.exc import IntegrityError

    existing = session.exec(select(BuffettRunResult).where(BuffettRunResult.ticker == ticker)).first()
    growth = metrics.get("CAGR")
    peg = metrics.get("PEG")
    values: dict[str, Any] = {
        "run_id": run_id,
        "nom": metrics.get("Nom"),
        "pays": metrics.get("Pays"),
        "secteur": metrics.get("Secteur"),
        "prix": float(metrics.get("Prix") or 0),
        "eps": float(metrics.get("EPS") or 0),
        "per": float(metrics.get("PER") or 0),
        "croissance": float(growth * 100) if growth else None,
        "peg": float(peg) if peg is not None else None,
        "volume": float(metrics.get("Volume") or 0),
        "chance_moat": round(score, 2),
        "achat": bool(metrics.get("Achat", False)),
        "updated_at": dt.datetime.utcnow(),
    }
    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        obj = BuffettRunResult(ticker=ticker, **values)
        session.add(obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def update_allocations(session: Session, run_id: int, alloc: list[dict]) -> None:
    """Met à jour allocation_pct + broker_cible depuis le résultat de l'optimiseur."""
    for a in alloc:
        row = session.exec(
            select(BuffettRunResult).where(BuffettRunResult.ticker == a["Ticker"])
        ).first()
        if row:
            row.allocation_pct = a.get("Poids total (%)")
            row.broker_cible = a.get("Broker")
            session.add(row)
    session.commit()
