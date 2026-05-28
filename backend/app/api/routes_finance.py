"""Finance API routes — portfolio, snapshots, benchmarks, risk,
buffett runs, rebalancing, transactions.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlmodel import Session, select

from app.core.db import get_session
from app.api.schemas_finance import (
    SnapshotOut, HistoryPointOut, PositionOut, PerfMetricsOut,
    BenchmarkOut, BenchmarkSeriePoint, RiskMetricsOut, TreemapNodeOut,
    TransactionCreate, TransactionOut, ImportResultOut,
    BuffettRunOut, BuffettResultOut, BuffettRunDetailOut, BuffettProgressOut,
    RebalancingDiffOut, RebalancingLineOut,
)
from app.services.finance.snapshots import get_latest_snapshot, get_history, take_snapshot_now
from app.services.finance.portfolio import get_positions, get_perf_metrics
from app.services.finance.benchmarks import get_portfolio_vs_benchmarks
from app.services.finance.risk import get_risk_metrics, get_treemap_data
from app.services.finance.transactions import (
    list_transactions, create_transaction, delete_transaction, import_csv,
)
from app.services.finance.rebalancing import compute_rebalancing_diff
from app.models.finance import BuffettRun, BuffettRunResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["finance"])


@router.get("/ping")
def ping():
    return {"module": "finance", "ready": True}


# --- Portfolio & snapshots ---

@router.get("/portfolio", response_model=list[PositionOut])
def portfolio(session: Session = Depends(get_session)):
    return get_positions(session)


@router.get("/portfolio/perf", response_model=PerfMetricsOut)
def portfolio_perf(session: Session = Depends(get_session)):
    m = get_perf_metrics(session)
    return PerfMetricsOut(**m) if m else PerfMetricsOut()


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


# --- Benchmarks & risk ---

@router.get("/benchmarks", response_model=list[BenchmarkOut])
def benchmarks(session: Session = Depends(get_session)):
    rows = get_history(session, limit=365)
    snapshots = [{"date": str(r.date), "valeur": r.valeur} for r in rows]
    data = get_portfolio_vs_benchmarks(snapshots)
    result = []
    for nom, info in data.items():
        serie = [BenchmarkSeriePoint(date=p["date"], valeur=p["valeur"])
                 for p in info.get("serie", [])]
        result.append(BenchmarkOut(
            nom=nom,
            ticker=info.get("ticker", ""),
            perf_1a_pct=info.get("perf_1a_pct"),
            perf_6m_pct=info.get("perf_6m_pct"),
            perf_mtd_pct=info.get("perf_mtd_pct"),
            serie=serie,
        ))
    return result


@router.get("/risk", response_model=RiskMetricsOut)
def risk(session: Session = Depends(get_session)):
    rows = get_history(session, limit=365)
    snapshots = [{"date": str(r.date), "valeur": r.valeur} for r in rows]
    positions = get_positions(session)
    m = get_risk_metrics(snapshots, positions)
    return RiskMetricsOut(**m)


@router.get("/treemap", response_model=list[TreemapNodeOut])
def treemap(group_by: str = "secteur", session: Session = Depends(get_session)):
    positions = get_positions(session)
    nodes = get_treemap_data(positions)
    return [TreemapNodeOut(**n) for n in nodes]


# --- Transactions ---

@router.get("/transactions", response_model=list[TransactionOut])
def transactions_list(
    ticker: Optional[str] = None,
    broker: Optional[str] = None,
    limit: int = 200,
    session: Session = Depends(get_session),
):
    return list_transactions(session, ticker=ticker, broker=broker, limit=limit)


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def transactions_create(body: TransactionCreate,
                        session: Session = Depends(get_session)):
    data = {
        "ticker": body.ticker.upper(),
        "type": body.type_transaction,
        "date": dt.datetime.combine(body.date_transaction, dt.time.min),
        "quantite": body.quantite,
        "prix_unitaire": body.prix_unitaire,
        "frais": body.frais,
        "devise": body.devise,
        "broker": body.broker,
        "note": body.note,
    }
    return create_transaction(session, data)


@router.delete("/transactions/{tx_id}", status_code=204)
def transactions_delete(tx_id: int, session: Session = Depends(get_session)):
    deleted = delete_transaction(session, tx_id)
    if not deleted:
        raise HTTPException(404, f"Transaction {tx_id} introuvable")


@router.post("/transactions/import", response_model=ImportResultOut)
async def transactions_import(
    file: UploadFile = File(...),
    broker: str = "auto",
    session: Session = Depends(get_session),
):
    content = await file.read()
    result = import_csv(session, content.decode("utf-8", errors="replace"),
                        broker_hint=broker)
    return ImportResultOut(**result)


# --- Buffett runs ---

@router.get("/buffett/runs", response_model=list[BuffettRunOut])
def buffett_runs(limit: int = 12, session: Session = Depends(get_session)):
    stmt = (select(BuffettRun)
            .order_by(BuffettRun.run_date.desc())  # type: ignore[attr-defined]
            .limit(limit))
    return list(session.exec(stmt).all())


@router.get("/buffett/latest", response_model=Optional[BuffettRunOut])
def buffett_latest(session: Session = Depends(get_session)):
    stmt = (select(BuffettRun)
            .where(BuffettRun.statut == "termine")
            .order_by(BuffettRun.run_date.desc()))  # type: ignore[attr-defined]
    return session.exec(stmt).first()


@router.get("/buffett/progress", response_model=BuffettProgressOut)
def buffett_progress(session: Session = Depends(get_session)):
    stmt = (select(BuffettRun)
            .where(BuffettRun.statut == "en_cours")
            .order_by(BuffettRun.created_at.desc()))  # type: ignore[attr-defined]
    run = session.exec(stmt).first()
    if run:
        return BuffettProgressOut(run_id=run.id, statut="en_cours",
                                   progress_pct=run.progress_pct or 0.0,
                                   n_done=run.n_tickers_analyzed,
                                   n_total=run.n_tickers_total)
    return BuffettProgressOut(run_id=None, statut="idle", progress_pct=0.0)


@router.get("/buffett/runs/{run_id}", response_model=BuffettRunDetailOut)
def buffett_run_detail(run_id: int, session: Session = Depends(get_session)):
    run = session.get(BuffettRun, run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} introuvable")
    top = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .order_by(BuffettRunResult.chance_moat.desc())  # type: ignore[attr-defined]
        .limit(50)
    ).all())
    alloc = list(session.exec(
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .where(BuffettRunResult.allocation_pct.isnot(None))  # type: ignore[attr-defined]
        .order_by(BuffettRunResult.allocation_pct.desc())  # type: ignore[attr-defined]
    ).all())
    return BuffettRunDetailOut(run=run, top_results=top, allocation_cible=alloc)


@router.post("/buffett/run", status_code=202)
def buffett_run_start(
    background_tasks: BackgroundTasks,
    csv_path: Optional[str] = None,
    session: Session = Depends(get_session),
):
    from app.services.finance.scheduler_stub import job_monthly_buffett
    stmt = select(BuffettRun).where(BuffettRun.statut == "en_cours")
    if session.exec(stmt).first():
        raise HTTPException(409, "Analyse Buffett deja en cours")
    background_tasks.add_task(job_monthly_buffett, csv_path)
    return {"message": "Analyse demarree en arriere-plan", "status": "accepted"}


# --- Rebalancing ---

@router.get("/rebalancing/diff", response_model=Optional[RebalancingDiffOut])
def rebalancing_diff(session: Session = Depends(get_session)):
    diff = compute_rebalancing_diff(session)
    if diff is None:
        return None
    return RebalancingDiffOut(
        run_id=diff.run_id,
        run_date=diff.run_date,
        valeur_totale_eur=diff.valeur_totale_eur,
        lignes=[RebalancingLineOut(**l.__dict__) for l in diff.lignes],
        n_acheter=diff.n_acheter,
        n_vendre=diff.n_vendre,
        n_conserver=diff.n_conserver,
    )
