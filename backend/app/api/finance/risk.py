"""Sous-routeur Finance : benchmarks, risque, treemap."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.core.cache import TTLCache
from app.api.schemas_finance import (
    BenchmarkOut, BenchmarkSeriePoint, RiskMetricsOut, TreemapNodeOut,
)
from app.services.finance.snapshots import get_history
from app.services.finance.portfolio import get_positions
from app.services.finance.benchmarks import get_portfolio_vs_benchmarks
from app.services.finance.risk import get_risk_metrics, get_treemap_data, get_sector_diversification

router = APIRouter()


@router.get("/diversification")
def diversification(session: Session = Depends(get_session)):
    """Diversification sectorielle + détection de surpondération (> seuil)."""
    return get_sector_diversification(session)


@router.get("/benchmarks", response_model=list[BenchmarkOut])
def benchmarks(session: Session = Depends(get_session)):
    from app.services.finance.benchmarks import BENCHMARKS
    rows = get_history(session, limit=10000)  # tout l'historique pour la simulation CW8
    snapshots = [{"date": str(r.date), "valeur": r.valeur, "investit": r.investit} for r in rows]
    data = get_portfolio_vs_benchmarks(snapshots)
    bench = data.get("benchmarks", {})
    result = []
    for nom, info in bench.items():
        if not info:
            continue
        serie = [BenchmarkSeriePoint(date=p["date"], valeur=p["valeur"])
                 for p in info.get("serie", [])]
        result.append(BenchmarkOut(
            nom=nom,
            ticker=BENCHMARKS.get(nom, ""),
            perf_1a_pct=info.get("perf_1y_pct"),
            perf_6m_pct=info.get("perf_6m_pct"),
            perf_mtd_pct=info.get("perf_mtd_pct"),
            serie=serie,
        ))
    return result


_risk_cache = TTLCache(ttl_seconds=300.0)


@router.get("/risk", response_model=RiskMetricsOut)
def risk(session: Session = Depends(get_session)):
    rows = get_history(session, limit=365)
    snapshots = [{"date": str(r.date), "valeur": r.valeur} for r in rows]
    positions = get_positions(session)
    # Cache 5 min : la signature (nb points + dernière date + nb positions) suffit
    # à invalider dès qu'un snapshot ou une position change.
    key = (len(snapshots), snapshots[-1]["date"] if snapshots else None, len(positions))
    m = _risk_cache.get_or_set(key, lambda: get_risk_metrics(snapshots, positions))
    return RiskMetricsOut(**m)


@router.get("/treemap", response_model=list[TreemapNodeOut])
def treemap(group_by: str = "secteur", session: Session = Depends(get_session)):
    positions = get_positions(session)
    nodes = get_treemap_data(positions)
    return [TreemapNodeOut(**n) for n in nodes]
