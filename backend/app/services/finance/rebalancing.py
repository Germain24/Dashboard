"""
Rebalancing service — compare real positions vs last Buffett run target.
Produces buy/sell diff in EUR. No trade execution (PLAN absolute rule).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import yfinance as yf
from sqlmodel import Session, select

from app.models.finance import Position, BuffettRun, BuffettRunResult


@dataclass
class RebalancingLine:
    ticker: str
    nom: str
    allocation_actuelle_pct: float
    allocation_cible_pct: float
    valeur_actuelle_eur: float
    valeur_cible_eur: float
    delta_eur: float          # positive = acheter, negative = vendre
    action: str               # "ACHETER" | "VENDRE" | "CONSERVER"


@dataclass
class RebalancingDiff:
    run_id: int
    run_date: str
    valeur_totale_eur: float
    lignes: list[RebalancingLine]
    n_acheter: int
    n_vendre: int
    n_conserver: int


def _get_last_run(session: Session) -> Optional[BuffettRun]:
    stmt = (
        select(BuffettRun)
        .where(BuffettRun.statut == "termine")
        .order_by(BuffettRun.run_date.desc())  # type: ignore[attr-defined]
    )
    return session.exec(stmt).first()


def _get_run_results(session: Session, run_id: int) -> list[BuffettRunResult]:
    stmt = (
        select(BuffettRunResult)
        .where(BuffettRunResult.run_id == run_id)
        .where(BuffettRunResult.allocation_pct.isnot(None))  # type: ignore[attr-defined]
        .order_by(BuffettRunResult.allocation_pct.desc())  # type: ignore[attr-defined]
    )
    return list(session.exec(stmt).all())


def _get_positions(session: Session) -> list[Position]:
    return list(session.exec(select(Position)).all())


def _fetch_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch current prices for a list of tickers. Returns {ticker: price}."""
    prices: dict[str, float] = {}
    if not tickers:
        return prices
    try:
        data = yf.download(
            tickers,
            period="2d",
            auto_adjust=True,
            progress=False,
        )
        close = data["Close"] if "Close" in data.columns else data
        for t in tickers:
            try:
                if t in close.columns:
                    prices[t] = float(close[t].dropna().iloc[-1])
            except Exception:
                pass
    except Exception:
        pass
    return prices


def compute_rebalancing_diff(session: Session) -> Optional[RebalancingDiff]:
    """
    Compare Position table vs last finished BuffettRun allocation.
    Returns None if no terminated run exists.
    """
    run = _get_last_run(session)
    if run is None:
        return None

    run_results = _get_run_results(session, run.id)
    positions = _get_positions(session)

    pos_tickers = [p.ticker for p in positions]
    prices = _fetch_prices(pos_tickers)

    pos_valeur: dict[str, float] = {}
    for p in positions:
        price = prices.get(p.ticker, p.prix_moyen or 0.0)
        pos_valeur[p.ticker] = price * (p.quantite or 0)

    valeur_totale = sum(pos_valeur.values())
    if valeur_totale <= 0:
        valeur_totale = 1.0

    alloc_actuelle: dict[str, float] = {
        t: (v / valeur_totale * 100) for t, v in pos_valeur.items()
    }

    cible_map: dict[str, tuple[float, str]] = {
        r.ticker: (r.allocation_pct or 0.0, r.nom or r.ticker)
        for r in run_results
        if r.allocation_pct and r.allocation_pct > 0
    }

    all_tickers = set(alloc_actuelle) | set(cible_map)
    lignes: list[RebalancingLine] = []

    for ticker in sorted(all_tickers):
        pct_actuel = alloc_actuelle.get(ticker, 0.0)
        pct_cible, nom = cible_map.get(ticker, (0.0, ticker))
        val_actuelle = (pct_actuel / 100) * valeur_totale
        val_cible = (pct_cible / 100) * valeur_totale
        delta = val_cible - val_actuelle

        if abs(delta) < 1:
            action = "CONSERVER"
        elif delta > 0:
            action = "ACHETER"
        else:
            action = "VENDRE"

        lignes.append(RebalancingLine(
            ticker=ticker,
            nom=nom,
            allocation_actuelle_pct=round(pct_actuel, 2),
            allocation_cible_pct=round(pct_cible, 2),
            valeur_actuelle_eur=round(val_actuelle, 2),
            valeur_cible_eur=round(val_cible, 2),
            delta_eur=round(delta, 2),
            action=action,
        ))

    lignes.sort(key=lambda l: abs(l.delta_eur), reverse=True)

    return RebalancingDiff(
        run_id=run.id,
        run_date=str(run.run_date),
        valeur_totale_eur=round(valeur_totale, 2),
        lignes=lignes,
        n_acheter=sum(1 for l in lignes if l.action == "ACHETER"),
        n_vendre=sum(1 for l in lignes if l.action == "VENDRE"),
        n_conserver=sum(1 for l in lignes if l.action == "CONSERVER"),
    )
