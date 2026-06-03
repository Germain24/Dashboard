"""Sous-routeur Finance : portefeuille, snapshots, positions, historique."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_session
from app.api.schemas_finance import (
    SnapshotOut, HistoryPointOut, PositionOut, PerfMetricsOut,
    PositionCreate, PositionIdOut,
)
from app.services.finance.snapshots import get_latest_snapshot, get_history, take_snapshot_now
from app.services.finance.portfolio import get_positions, get_perf_metrics, get_title_detail

router = APIRouter()


@router.get("/ping")
def ping():
    return {"module": "finance", "ready": True}


@router.get("/portfolio", response_model=list[PositionOut])
def portfolio(session: Session = Depends(get_session)):
    return get_positions(session)


@router.get("/portfolio/perf", response_model=PerfMetricsOut)
def portfolio_perf(session: Session = Depends(get_session)):
    m = get_perf_metrics(session)
    return PerfMetricsOut(**m) if m else PerfMetricsOut()


@router.get("/titre/{ticker}")
def titre_detail(ticker: str, session: Session = Depends(get_session)):
    """Vue détaillée d'un titre : cours, P/E, score Buffett, poids, performance."""
    return get_title_detail(session, ticker)


@router.get("/projection")
def projection(
    initial: float = 0,
    mensuel: float = 0,
    taux: float = 5.0,
    mois: int = 120,
    objectif: float = 0,
):
    """Projection d'épargne à intérêts composés (+ mois pour atteindre un objectif)."""
    from app.services.finance.projection import project_savings, mois_pour_objectif
    res = project_savings(initial, mensuel, taux, mois)
    if objectif and objectif > 0:
        res["objectif"] = objectif
        res["mois_pour_objectif"] = mois_pour_objectif(initial, mensuel, taux, objectif)
    return res


@router.get("/fx")
def fx_rates(base: str = "EUR", quotes: str = "USD,CAD"):
    """Taux de change du jour : 1 base = X quote, pour chaque devise demandée."""
    from app.services.finance.fx import get_rate
    wanted = [q.strip().upper() for q in quotes.split(",") if q.strip()]
    return {
        "base": base.upper(),
        "rates": {q: get_rate(base, q) for q in wanted},
    }


@router.get("/snapshot/latest", response_model=Optional[SnapshotOut])
def snapshot_latest(session: Session = Depends(get_session)):
    return get_latest_snapshot(session)


@router.post("/snapshot", response_model=Optional[SnapshotOut], status_code=201)
def snapshot_create(session: Session = Depends(get_session)):
    snap = take_snapshot_now(session)
    if snap is None:
        raise HTTPException(422, "Aucune position active pour creer un snapshot")
    return snap


@router.get("/history", response_model=list[HistoryPointOut])
def history(days: int = 365, session: Session = Depends(get_session)):
    rows = get_history(session, limit=days)
    return [HistoryPointOut(date=r.date, valeur=r.valeur, investit=r.investit)
            for r in rows]


@router.post("/history/sync-excel")
def history_sync_excel(session: Session = Depends(get_session)):
    """Recharge l'historique depuis Historique_portefeuille.xlsx (source editable).

    Tu edites le fichier (Date JJ/MM/AAAA, Valeur, Investit), tu cliques -> la courbe
    du Suivi est mise a jour sans redemarrer.
    """
    from app.services.finance.history_excel import sync_excel_to_db, find_history_file
    n = sync_excel_to_db(session)
    return {"synced": n, "file": find_history_file() or "introuvable"}


# --- Positions manuelles ---

@router.get("/positions/list", response_model=list[PositionIdOut])
def positions_list(session: Session = Depends(get_session)):
    """Liste toutes les positions avec leur id (pour edition/suppression)."""
    from app.models.finance import Position
    from sqlmodel import select as sel
    return list(session.exec(sel(Position)).all())


@router.post("/positions", response_model=PositionIdOut, status_code=201)
def positions_create(body: PositionCreate, session: Session = Depends(get_session)):
    """Cree ou met a jour une position (upsert par ticker+broker)."""
    import datetime as _dt
    from app.models.finance import Position
    from sqlmodel import select as sel
    broker = body.broker or "default"
    existing = session.exec(
        sel(Position)
        .where(Position.ticker == body.ticker.upper())
        .where(Position.broker == broker)
    ).first()
    if existing:
        existing.quantite = body.quantite
        existing.pmu = body.pmu
        existing.devise = body.devise
        existing.updated_at = _dt.datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    pos = Position(
        ticker=body.ticker.upper(),
        broker=broker,
        quantite=body.quantite,
        pmu=body.pmu,
        devise=body.devise,
        updated_at=_dt.datetime.utcnow(),
    )
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


@router.put("/positions/{pos_id}", response_model=PositionIdOut)
def positions_update(pos_id: int, body: PositionCreate, session: Session = Depends(get_session)):
    """Met a jour une position par son id."""
    import datetime as _dt
    from app.models.finance import Position
    pos = session.get(Position, pos_id)
    if not pos:
        raise HTTPException(404, f"Position {pos_id} introuvable")
    pos.ticker = body.ticker.upper()
    pos.quantite = body.quantite
    pos.pmu = body.pmu
    pos.devise = body.devise
    pos.broker = body.broker or pos.broker
    pos.updated_at = _dt.datetime.utcnow()
    session.add(pos)
    session.commit()
    session.refresh(pos)
    return pos


@router.delete("/positions/{pos_id}", status_code=204)
def positions_delete(pos_id: int, session: Session = Depends(get_session)):
    """Supprime une position."""
    from app.models.finance import Position
    pos = session.get(Position, pos_id)
    if not pos:
        raise HTTPException(404, f"Position {pos_id} introuvable")
    session.delete(pos)
    session.commit()


@router.post("/snapshot/auto", status_code=200)
def snapshot_auto(session: Session = Depends(get_session)):
    """Auto-snapshot silencieux : prend un snapshot si des positions existent.
    Retourne le snapshot du jour (nouveau ou existant). Jamais d'erreur 422.
    """
    import datetime as _dt
    from app.models.finance import SnapshotPortefeuille
    from sqlmodel import select as sel
    today = _dt.date.today()
    existing = session.exec(sel(SnapshotPortefeuille).where(SnapshotPortefeuille.date == today)).first()
    if existing:
        return {"status": "already_exists", "date": str(today), "valeur": existing.valeur}
    snap = take_snapshot_now(session)
    if snap:
        return {"status": "created", "date": str(snap.date), "valeur": snap.valeur}
    return {"status": "no_positions"}
