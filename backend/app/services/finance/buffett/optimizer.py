"""Optimiseur de portefeuille STARR via Monte Carlo + copule de Vine."""

from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.optimize import minimize

from .config import Config


def _get_active_brokers() -> list[str]:
    return [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]


def _is_true(val) -> bool:
    import pandas as pd
    if pd.isna(val) or str(val).strip() == "": return True
    if isinstance(val, (bool, np.bool_)): return bool(val)
    try:
        return float(val) != 0
    except (ValueError, TypeError):
        pass
    return str(val).strip().upper() in ["VRAI", "TRUE", "OUI", "1", "1.0"]


def _get_broker_col(b_name: str, columns: list) -> str | None:
    import re
    def clean(v): return "".join(filter(str.isalnum, str(v).upper()))
    cb = clean(b_name)
    for c in columns:
        if cb == clean(c): return c
    bn = re.search(r"(\d+)$", b_name)
    for c in columns:
        cc = clean(c)
        if cb in cc or cc in cb:
            cn = re.search(r"(\d+)$", c)
            if (bn.group(1) if bn else None) == (cn.group(1) if cn else None): return c
    return None


def prepare_optimization(tickers: list[str], df) -> tuple[list, list]:
    """Retourne (matrix_access, active_brokers)."""
    import pandas as pd
    ticker_col = "Ticker Yahoo Finance"
    base_cols = {ticker_col,"Nom","Pays","Prix","EPS","PER","Croissance","PEG","Volume","Achat","Chance MOAT","Secteur","Poids"}
    broker_cols = [c for c in df.columns if c not in base_cols]
    active = _get_active_brokers()
    forced_up = [t.upper() for t in Config.FORCED_BUY_TICKERS]
    matrix = []
    for t in tickers:
        rows = df[df[ticker_col] == t]
        row_acc = []
        for b in active:
            col = _get_broker_col(b, broker_cols)
            access = True
            if col and not rows.empty:
                v = rows.iloc[0][col]
                if not pd.isna(v): access = _is_true(v)
            row_acc.append(access)
        matrix.append(row_acc)
    return matrix, active


def optimize_portfolio(
    tickers: list[str],
    returns,   # pd.DataFrame
    cov_mat: np.ndarray,
    matrix_access: list,
    active_brokers: list[str],
    vine,
    n_sim: int = 500_000,
) -> tuple[np.ndarray, float]:
    """Optimise le portefeuille (STARR via Monte Carlo + copule).

    Retourne (units_matrix [n_tickers × n_brokers, entiers 0-100], final_starr).
    """
    num_t = len(tickers); num_b = len(active_brokers)
    total_cap = sum(Config.BUDGET_BROKERS.values())
    b_ratios = [Config.BUDGET_BROKERS[b] / total_cap for b in active_brokers]
    n_vars = num_t * num_b

    bounds = []
    for i in range(num_t):
        for j in range(num_b):
            bounds.append((0.0, b_ratios[j]) if matrix_access[i][j] else (0.0, 0.0))

    constraints = [
        {"type": "eq", "fun": lambda w, bj=j: np.sum(w.reshape(num_t, num_b)[:, bj]) - b_ratios[bj]}
        for j in range(num_b)
    ]

    mean_rets = returns.mean().values * 252
    print(f"    * Simulation Monte Carlo ({n_sim} scénarios)...")
    U_sim = vine.simulate(n_obs=n_sim)
    sim_rets = np.zeros((n_sim, num_t))
    for i in range(num_t):
        p = stats.t.fit(returns.iloc[:, i])
        sim_rets[:, i] = stats.t.ppf(U_sim[:, i], *p)

    def starr(w_flat, alpha=0.05):
        wg = np.sum(w_flat.reshape(num_t, num_b), axis=1)
        port = sim_rets @ wg
        mr = wg @ mean_rets
        var_t = np.percentile(port, alpha * 100)
        tail = port[port <= var_t]
        cvar = max(-np.mean(tail) * np.sqrt(252) if len(tail) else 1e-4, 0.005)
        s = mr / cvar
        return mr, cvar, (s if mr >= 0 else mr * cvar)

    # Phase 1 : Max STARR multi-start
    best_w, best_val = None, -np.inf
    fallback_w0 = None
    print(f"    * Optimisation STARR multi-start ({Config.N_MULTISTART} départs)...")
    for start in range(Config.N_MULTISTART):
        w0 = np.zeros(n_vars)
        for j in range(num_b):
            avail = [i for i in range(num_t) if matrix_access[i][j]]
            if avail:
                val = b_ratios[j] / len(avail)
                for i in avail: w0[i * num_b + j] = val
        lb, ub = [b[0] for b in bounds], [b[1] for b in bounds]
        w0 = np.clip(w0, lb, ub)
        if fallback_w0 is None: fallback_w0 = w0.copy()
        if start > 0: w0 = np.clip(w0 + np.random.normal(0, 0.01, n_vars), lb, ub)
        res = minimize(lambda w: -starr(w)[2], w0, method="SLSQP",
                       bounds=bounds, constraints=constraints,
                       options={"ftol":1e-6,"maxiter":500,"eps":1e-3})
        if res.success and -res.fun > best_val:
            best_val, best_w = -res.fun, res.x

    if best_w is None: best_w = fallback_w0; best_val = starr(best_w)[2]

    # Phase 2 : Min CVaR dans zone STARR >= 90% du max
    target = 0.9 * best_val if best_val >= 0 else 1.1 * best_val
    res2 = minimize(lambda w: starr(w)[1], best_w, method="SLSQP",
                    bounds=bounds, constraints=constraints + [{"type":"ineq","fun":lambda w: starr(w)[2]-target}],
                    options={"ftol":1e-6,"maxiter":500,"eps":1e-3})
    final_w = res2.x if (res2.success and res2.x is not None) else best_w
    _, _, final_starr = starr(final_w)

    # Phase 3 : Discrétisation Hare-Niemeyer (1% incréments)
    wm = final_w.reshape(num_t, num_b)
    units = np.zeros((num_t, num_b), dtype=int)
    for j in range(num_b):
        if b_ratios[j] <= 0: continue
        pcts = wm[:, j] / b_ratios[j] * 100
        floors = np.floor(np.maximum(pcts, 0)).astype(int)
        rests = pcts - floors
        diff = 100 - floors.sum()
        if diff > 0:
            for idx in np.argsort(rests)[-diff:]: floors[idx] += 1
        units[:, j] = floors

    print(f"    * STARR final : {final_starr:.3f}")
    return units, final_starr
