"""Persistance des résultats Buffett en DB (BuffettRun + BuffettRunResult)."""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
from typing import Any

from sqlmodel import Session, select

from app.models.finance import BuffettRun, BuffettRunResult


def delete_run(session: Session, run_id: int) -> bool:
    """Supprime un run Buffett et tous ses résultats. False si introuvable.

    Sert à retirer une analyse bloquée/interrompue (#) depuis l'UI."""
    run = session.get(BuffettRun, run_id)
    if run is None:
        return False
    for r in session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
    ).all():
        session.delete(r)
    session.delete(run)
    session.commit()
    return True


def create_run(session: Session, n_total: int, params: dict) -> BuffettRun:
    """Crée un run en statut 'running'."""
    run = BuffettRun(
        run_date=dt.date.today(),
        statut="en_cours",
        n_tickers_total=n_total,
        n_tickers_analyzed=0,
        progress_pct=0.0,
        params_json=params,
        updated_at=utcnow(),
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
        run.updated_at = utcnow()
        if run.statut != "termine":
            run.statut = "en_cours"  # un run qui progresse est bien actif (annule un "interrompu")
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
        run.progress_pct = 100.0 if statut == "termine" else run.progress_pct
        run.erreur = erreur
        run.updated_at = utcnow()
        session.add(run)
        session.commit()


def get_done_tickers(session: Session, run_id: int) -> set[str]:
    """Tickers deja persistes pour ce run (reprise apres fermeture du programme)."""
    rows = session.exec(
        select(BuffettRunResult.ticker).where(BuffettRunResult.run_id == run_id)
    ).all()
    return {t for t in rows}


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
        "updated_at": utcnow(),
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


def update_allocations(
    session: Session, run_id: int, alloc: list[dict], reset: bool = True
) -> None:
    """Persiste l'allocation cible (multi-broker) sur les BuffettRunResult.

    ``alloc`` : liste de dicts produits par ``allocation.discretize_allocation`` :
      {Ticker, Broker, shares (int|None), eur, prix, type ('pie'|'shares'),
       'Poids total (%)'}

    Agrège par ticker : ``allocation_pct`` = somme des poids (%), ``broker_cible`` =
    broker(s), et stocke le détail par broker (nombre d'actions entières, montant €,
    prix, type) dans ``secteurs_extra['allocations']`` — sans migration de schéma.
    """
    by_ticker: dict[str, list[dict]] = {}
    for a in alloc:
        by_ticker.setdefault(a["Ticker"], []).append(a)

    if reset and run_id is not None:
        rows = session.exec(
            select(BuffettRunResult).where(BuffettRunResult.run_id == run_id)
        ).all()
        for r in rows:
            r.allocation_pct = None
            r.broker_cible = None
            extra = dict(r.secteurs_extra or {})
            if "allocations" in extra:
                extra.pop("allocations", None)
                r.secteurs_extra = extra or None
                session.add(r)

    for ticker, items in by_ticker.items():
        row = session.exec(
            select(BuffettRunResult).where(BuffettRunResult.ticker == ticker)
        ).first()
        if not row:
            continue
        total_pct = sum(float(it.get("Poids total (%)") or 0) for it in items)
        brokers = sorted({str(it.get("Broker")) for it in items})
        details = [{
            "broker": it.get("Broker"),
            "shares": it.get("shares"),
            "eur": it.get("eur"),
            "prix": it.get("prix"),
            "type": it.get("type"),
            "pct": it.get("Poids total (%)"),
        } for it in items]
        row.allocation_pct = round(total_pct, 4)
        row.broker_cible = ", ".join(brokers)
        extra = dict(row.secteurs_extra or {})
        extra["allocations"] = details
        row.secteurs_extra = extra
        session.add(row)
    session.commit()
