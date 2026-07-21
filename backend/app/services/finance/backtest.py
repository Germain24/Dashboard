"""Backtest simple d'une allocation cible (buy-and-hold) sur des séries de prix.

Cœur pur (sans réseau) : à partir de séries de prix alignées et de poids cibles,
calcule la courbe d'équité normalisée à 100 et le rendement total. La
récupération des prix (yfinance) est faite par l'appelant / l'endpoint.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np


def simulate_allocation(
    prices: dict[str, list[float]],
    weights: dict[str, float],
) -> dict:
    """Courbe d'équité d'un portefeuille buy-and-hold.

    ``prices`` : ticker -> série de prix (même longueur, alignée dans le temps).
    ``weights`` : ticker -> poids (en %). Seuls les tickers présents dans les deux
    sont utilisés ; les poids sont renormalisés à 100 %.

    Retourne ``{"equity": [...], "rendement_pct": x, "n_points": n}`` où ``equity``
    démarre à 100. Buy-and-hold : chaque titre évolue selon ``prix_t / prix_0``.
    """
    common = [t for t in weights if t in prices and prices[t]]
    common = [t for t in common if (weights[t] or 0) > 0 and prices[t][0] > 0]
    if not common:
        return {"equity": [], "rendement_pct": 0.0, "n_points": 0}

    n = min(len(prices[t]) for t in common)
    total_w = sum(weights[t] for t in common)
    norm = {t: weights[t] / total_w for t in common}

    equity: list[float] = []
    for i in range(n):
        val = sum(norm[t] * (prices[t][i] / prices[t][0]) for t in common)
        equity.append(round(val * 100, 4))

    rendement = round(equity[-1] - 100, 2) if equity else 0.0
    return {"equity": equity, "rendement_pct": rendement, "n_points": n}


def simulate_walk_forward(
    dates: list[str],
    prices: dict[str, list[float]],
    allocations: list[dict],
    rebalance_days: int = 80,
    cost_bps: float = 10.0,
) -> dict:
    """Backtest sans fuite temporelle à partir d'allocations historiquement persistées.

    Chaque cible n'est utilisable qu'à compter de sa date de run. Deux rééquilibrages
    sont espacés d'au moins ``rebalance_days`` (en jours calendaires), ce qui reproduit
    une cadence approximativement trimestrielle. Les poids dérivent entre deux dates.
    """
    if not dates or not prices or not allocations:
        return {
            "dates": [], "equity": [], "rendement_pct": 0.0, "n_points": 0,
            "n_rebalances": 0, "turnover": 0.0, "costs_pct": 0.0,
            "max_drawdown_pct": 0.0, "cvar_5_pct": 0.0, "cagr_pct": 0.0,
        }

    parsed_dates = [dt.date.fromisoformat(value) for value in dates]
    snapshots = sorted(
        (
            dt.date.fromisoformat(str(item["date"])),
            {str(t): max(float(w), 0.0) for t, w in (item.get("weights") or {}).items()},
        )
        for item in allocations
        if item.get("date") and item.get("weights")
    )
    if not snapshots:
        return simulate_walk_forward([], {}, [])

    arrays = {
        ticker: np.asarray(values[:len(parsed_dates)], dtype=float)
        for ticker, values in prices.items()
        if len(values) >= 2
    }
    n = min([len(parsed_dates), *(len(values) for values in arrays.values())]) if arrays else 0
    if n < 2:
        return simulate_walk_forward([], {}, [])
    parsed_dates = parsed_dates[:n]
    arrays = {ticker: values[:n] for ticker, values in arrays.items()}

    returns = {}
    for ticker, values in arrays.items():
        previous = values[:-1]
        current = values[1:]
        valid = np.isfinite(previous) & np.isfinite(current) & (previous > 0)
        result = np.zeros(n - 1, dtype=float)
        result[valid] = current[valid] / previous[valid] - 1.0
        returns[ticker] = result

    eligible_snapshots: list[tuple[dt.date, dict[str, float]]] = []
    last_rebalance: dt.date | None = None
    for run_date, target in snapshots:
        if last_rebalance is None or (run_date - last_rebalance).days >= rebalance_days:
            eligible_snapshots.append((run_date, target))
            last_rebalance = run_date

    holdings: dict[str, float] = {}
    equity_value = 100.0
    equity: list[float] = []
    output_dates: list[str] = []
    daily_returns: list[float] = []
    snapshot_index = 0
    total_turnover = 0.0
    total_cost_fraction = 0.0
    n_rebalances = 0
    cost_rate = max(float(cost_bps), 0.0) / 10_000.0

    for i, date in enumerate(parsed_dates):
        while (
            snapshot_index < len(eligible_snapshots)
            and eligible_snapshots[snapshot_index][0] <= date
        ):
            target_raw = eligible_snapshots[snapshot_index][1]
            tradable = {
                ticker: weight for ticker, weight in target_raw.items()
                if ticker in arrays and np.isfinite(arrays[ticker][i]) and arrays[ticker][i] > 0
            }
            total = sum(tradable.values())
            if total > 0:
                target = {ticker: weight / total for ticker, weight in tradable.items()}
                universe = set(holdings) | set(target)
                turnover = 0.5 * sum(
                    abs(target.get(ticker, 0.0) - holdings.get(ticker, 0.0))
                    for ticker in universe
                )
                # Le premier investissement n'est pas considéré comme du turnover.
                charged_turnover = turnover if holdings else 0.0
                cost = charged_turnover * cost_rate
                equity_value *= 1.0 - cost
                total_turnover += charged_turnover
                total_cost_fraction += cost
                holdings = target
                n_rebalances += 1
            snapshot_index += 1

        if not holdings:
            continue
        if i > 0:
            portfolio_return = sum(
                weight * returns[ticker][i - 1]
                for ticker, weight in holdings.items()
                if ticker in returns
            )
            equity_value *= 1.0 + portfolio_return
            daily_returns.append(float(portfolio_return))
            grown = {
                ticker: weight * (1.0 + returns.get(ticker, np.zeros(n - 1))[i - 1])
                for ticker, weight in holdings.items()
            }
            grown_total = sum(grown.values())
            if grown_total > 0:
                holdings = {ticker: value / grown_total for ticker, value in grown.items()}
        output_dates.append(date.isoformat())
        equity.append(round(equity_value, 4))

    if not equity:
        return simulate_walk_forward([], {}, [])
    peak = -math.inf
    max_drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    daily = np.asarray(daily_returns, dtype=float)
    if daily.size:
        cutoff = np.percentile(daily, 5)
        tail = daily[daily <= cutoff]
        cvar = float(tail.mean()) if tail.size else 0.0
    else:
        cvar = 0.0
    years = max((dt.date.fromisoformat(output_dates[-1]) - dt.date.fromisoformat(output_dates[0])).days / 365.25, 0.0)
    cagr = (equity[-1] / equity[0]) ** (1.0 / years) - 1.0 if years > 0 and equity[0] > 0 else 0.0
    return {
        "dates": output_dates,
        "equity": equity,
        "rendement_pct": round(equity[-1] - equity[0], 2),
        "n_points": len(equity),
        "n_rebalances": n_rebalances,
        "turnover": round(total_turnover, 4),
        "costs_pct": round(total_cost_fraction * 100.0, 4),
        "max_drawdown_pct": round(max_drawdown * 100.0, 2),
        "cvar_5_pct": round(cvar * 100.0, 3),
        "cagr_pct": round(cagr * 100.0, 2),
    }
