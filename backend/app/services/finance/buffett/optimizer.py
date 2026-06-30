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
    base_cols = {ticker_col,"Nom","Pays","Prix","EPS","PER","Croissance","PEG","Volume","Achat","Chance MOAT","Secteur","Poids","ISIN"}
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


# ---------------------------------------------------------------------------
# Differential Evolution optimizer (remplace STARR SLSQP pour le portefeuille)
# ---------------------------------------------------------------------------

def per_broker_cardinality_penalty(w, access, max_per_broker: int, beta: float,
                                   threshold: float) -> float:
    """Malus exponentiel quand un broker dépasse ``max_per_broker`` lignes.

    Pour chaque broker (colonne de ``access``), compte les titres disponibles ET
    pondérés (``w >= threshold``) — c.-à-d. les lignes qu'il portera après la
    répartition — et pénalise l'excès : ``Σ_broker exp(β·excès)−1``. Cap PAR broker
    (ex. 20 dans Trading212 ET 20 dans BoursDirect), pas un total global.
    """
    if beta <= 0:
        return 0.0
    w = np.asarray(w, dtype=float)
    acc = np.asarray(access, dtype=bool)
    weighted = w >= threshold
    pen = 0.0
    for j in range(acc.shape[1]):
        n = int((weighted & acc[:, j]).sum())
        excess = n - max_per_broker
        if excess > 0:
            pen += float(np.exp(beta * excess) - 1.0)
    return pen


def cardinality_penalty(w, max_lines: int, beta: float, threshold: float) -> float:
    """Malus exponentiel additif au-delà de ``max_lines`` positions ``>= threshold``.

    penalty = exp(β·(n_lignes − max_lines)) − 1 si dépassement, sinon 0. Pousse
    l'optimiseur à regrouper les ETF redondants et limiter les micro-lignes.
    """
    if beta <= 0:
        return 0.0
    n = int((np.asarray(w, dtype=float) >= threshold).sum())
    excess = n - max_lines
    return float(np.exp(beta * excess) - 1.0) if excess > 0 else 0.0


def constraint_penalty(w, d_vec, C_mat, min_def: float, max_country: float, k: float) -> float:
    """Pénalité quadratique des contraintes look-through (0 si respectées) :
    - défensif : ``k·max(0, min_def − Σ wᵢ·défensifᵢ)²`` (seulement si des actifs
      défensifs sont disponibles, sinon contrainte infaisable -> ignorée) ;
    - pays : ``k·Σ_X max(0, Σ wᵢ·paysᵢ,X − max_country)²``.
    """
    w = np.asarray(w, dtype=float)
    pen = 0.0
    if d_vec is not None and len(d_vec) and float(np.max(d_vec)) > 0:
        short = max(0.0, min_def - float(w @ d_vec))
        pen += k * short * short
    if C_mat is not None and getattr(C_mat, "size", 0):
        over = np.maximum((w @ C_mat) - max_country, 0.0)
        pen += k * float(np.sum(over * over))
    return pen


def cap_stock_weights(w, is_etf, cap: float) -> np.ndarray:
    """Plafonne le poids de chaque ACTION à ``cap`` (ETF exemptés), par water-filling.

    L'excédent au-dessus du plafond est redistribué au prorata sur les titres qui ont
    de la place (ETF — non plafonnés — et actions sous le plafond). La somme est
    préservée. ``is_etf`` : masque booléen [n] ; ``cap`` en fraction (0.15 = 15 %).
    """
    w = np.array(w, dtype=float)
    is_etf = np.asarray(is_etf, dtype=bool)
    if cap <= 0 or cap >= 1:
        return w
    for _ in range(1000):
        over = (~is_etf) & (w > cap + 1e-12)
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        room = (w > 0) & (is_etf | (~is_etf & (w < cap)))
        denom = float(w[room].sum())
        if not room.any() or denom <= 0:
            break
        w[room] += excess * w[room] / denom
    return w


def split_budget_to_brokers(w, access, b_ratios, min_position: float = 0.0) -> np.ndarray:
    """Répartit le budget de chaque broker sur SES titres disponibles, au prorata du
    poids optimiseur ``w`` (somme 1). Retourne W [n_tickers × n_brokers, fraction du
    capital total].

    - Pas de sous-investissement mécanique : chaque broker déploie son budget parmi
      ses titres disponibles (la dispo inégale ne laisse pas de budget oisif).
    - ``min_position`` : les titres dont le poids < seuil ne sont PAS achetés (évite
      les micro-lignes), mais leur part est **redéployée sur les titres gardés** du
      même broker (l'argent reste investi : on réduit le NOMBRE de lignes, pas le
      montant investi). ``min_position=0`` -> tous les titres gardés.
    """
    w = np.asarray(w, dtype=float)
    num_t = len(w)
    num_b = len(b_ratios)
    W = np.zeros((num_t, num_b))
    for j in range(num_b):
        if b_ratios[j] <= 0:
            continue
        kept = [i for i in range(num_t) if access[i][j] and w[i] >= min_position]
        tot = sum(w[i] for i in kept)
        if tot <= 0:
            # aucun titre au-dessus du seuil : repli sur tous les dispos (équipondéré)
            avail = [i for i in range(num_t) if access[i][j]]
            if avail:
                share = b_ratios[j] / len(avail)
                for i in avail:
                    W[i, j] = share
            continue
        for i in kept:
            W[i, j] = b_ratios[j] * w[i] / tot   # budget redéployé sur les gardés
    return W


def optimize_portfolio_de(
    tickers: list[str],
    returns,          # pd.DataFrame de rendements journaliers
    matrix_access: list,
    active_brokers: list[str],
    seed: int = 42,
    progress_cb=None,   # callable(iteration:int, convergence:float) | None
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
) -> tuple[np.ndarray, float]:
    """Optimise le portefeuille via Differential Evolution sur l'objectif **STARR**.

    STARR = rendement annualisé / CVaR(α) : pénalise les **grosses chutes** (queues
    de distribution), contrairement au Sharpe (écart-type symétrique). Les scénarios
    sont simulés une fois par **Monte-Carlo + copule de Vine** (cf. ``starr``) — la
    simulation ne dépend pas des poids, donc chaque évaluation DE n'est qu'un produit
    ``sim @ w`` + percentile.

    Optimisation au niveau TICKER (simplexe sum=1, normalisation interne), puis
    répartition par broker (chaque broker déploie 100 % de son budget). Les titres
    dégénérés (variance nulle) sont écartés ; le filtre de liquidité est appliqué en
    amont (éligibilité). Retourne (W [n_tickers × n_brokers, fraction du capital
    total], STARR_final).
    """
    from scipy.optimize import differential_evolution

    from .starr import neg_starr, simulate_scenarios

    n_sim = int(Config.STARR_N_SIM if n_sim is None else n_sim)
    alpha = float(Config.STARR_ALPHA if alpha is None else alpha)
    downside_weight = float(
        Config.STARR_DOWNSIDE_WEIGHT if downside_weight is None else downside_weight
    )
    min_position = float(
        Config.MIN_ALLOCATION_THRESHOLD if min_position is None else min_position
    )
    card_beta = float(Config.STARR_CARD_BETA)
    max_position = float(Config.MAX_POSITION_PCT)

    # ETF (depuis ToutBroker) -> exemptés du plafond de poids par titre.
    from .broker_availability import load_etf_tickers
    etf_set = load_etf_tickers()
    is_etf_full = np.array([str(t).upper() in etf_set for t in tickers], dtype=bool)

    num_t = len(tickers)
    num_b = len(active_brokers)
    # Plafond de lignes PAR broker (ex. 20 dans T212 ET 20 dans BoursDirect).
    max_per_broker = int(Config.STARR_MAX_LINES_PER_BROKER)
    total_cap = sum(Config.BUDGET_BROKERS.values()) or 1.0
    b_ratios = np.array([Config.BUDGET_BROKERS[b] / total_cap for b in active_brokers])

    R = np.asarray(returns, dtype=float)
    mean_daily_all = R.mean(axis=0)
    std = R.std(axis=0)

    access = np.array(
        [[bool(matrix_access[i][j]) for j in range(num_b)] for i in range(num_t)],
        dtype=bool,
    )
    # Titre investissable : au moins un broker ET variance non nulle (les séries de
    # prix dégénérées faussent le CVaR / la simulation).
    investable = access.any(axis=1) & (std > 1e-9) & np.isfinite(mean_daily_all)
    inv_idx = [i for i in range(num_t) if investable[i]]

    if not inv_idx:
        print("    * Aucun titre investissable -> poids nuls.")
        return np.zeros((num_t, num_b)), 0.0

    R_inv = R[:, inv_idx]
    mean_daily = mean_daily_all[inv_idx]
    access_inv = access[inv_idx]   # dispo broker restreinte aux titres investissables
    print(f"    * STARR/DE : {len(inv_idx)} titres, {n_sim} scénarios "
          f"(Monte-Carlo + copule de Vine, CVaR {int(alpha*100)} %)...")
    sim_rets = simulate_scenarios(R_inv, n_sim=n_sim, seed=seed)

    # ── Contraintes look-through (défensif min, pays max) ────────────────────
    from .lookthrough import load_lookthrough
    min_def = float(Config.MIN_DEFENSIVE_PCT)
    max_country = float(Config.MAX_COUNTRY_PCT)
    pen_k = float(Config.CONSTRAINT_PENALTY)
    inv_tickers = [str(tickers[i]).upper() for i in inv_idx]
    try:
        defmap, paysmap = load_lookthrough()
    except Exception:
        defmap, paysmap = {}, {}
    d_vec = np.array([defmap.get(t, 0.0) for t in inv_tickers], dtype=float)
    all_countries = sorted({c for t in inv_tickers for c in (paysmap.get(t) or {})})
    cidx = {c: j for j, c in enumerate(all_countries)}
    C_mat = np.zeros((len(inv_tickers), len(all_countries)))
    for i, t in enumerate(inv_tickers):
        for c, v in (paysmap.get(t) or {}).items():
            C_mat[i, cidx[c]] = v
    print(f"    * Contraintes : defensif>={min_def:.0%} (dispo {float(d_vec.max() if len(d_vec) else 0):.0%} max), "
          f"pays<={max_country:.0%} ({len(all_countries)} pays)")

    # ── Optimisation niveau TICKER (simplexe sum=1) sur l'objectif STARR ─────
    bounds = [(0.0, 1.0)] * len(inv_idx)

    def neg_obj(raw: np.ndarray) -> float:
        base = neg_starr(raw, sim_rets, mean_daily, alpha, downside_weight)
        s = float(np.sum(raw))
        if s > 0:
            w_ = raw / s
            # Malus cardinalité PAR broker (≤ max_per_broker lignes chez chacun).
            base += per_broker_cardinality_penalty(w_, access_inv, max_per_broker, card_beta, min_position)
            # Contraintes look-through (défensif / pays).
            base += constraint_penalty(w_, d_vec, C_mat, min_def, max_country, pen_k)
        return base

    _iter = {"n": 0}

    def _de_callback(xk, convergence=0.0):
        _iter["n"] += 1
        if progress_cb is not None:
            try:
                progress_cb(_iter["n"], float(convergence))
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation
        return False

    result = differential_evolution(
        neg_obj,
        bounds=bounds,
        seed=seed,
        maxiter=200,          # objectif STARR coûteux (MC) -> moins d'itérations
        tol=1e-6,
        mutation=(0.5, 1.5),
        recombination=0.9,
        popsize=12,
        polish=False,         # CVaR non lisse -> pas de polish gradient
        workers=1,
        updating="deferred",
        callback=_de_callback if progress_cb is not None else None,
    )

    raw = np.maximum(result.x, 0.0)
    s = raw.sum()
    w_inv = raw / s if s > 0 else raw
    # STARR PUR (sans le malus de cardinalité, qui ne sert qu'à orienter l'optimiseur).
    starr = -neg_starr(w_inv, sim_rets, mean_daily, alpha, downside_weight)
    if not np.isfinite(starr):
        starr = 0.0
    print(f"    * STARR final : {starr:.3f}")

    # Remappage vers la liste complète des tickers (non-investissables = 0).
    w = np.zeros(num_t)
    for k, i in enumerate(inv_idx):
        w[i] = w_inv[k]

    # Plafond de poids par ACTION (ETF exemptés) : filet anti-concentration.
    w = cap_stock_weights(w, is_etf_full, max_position)

    # Répartition par broker (cf. split_budget_to_brokers) : déploiement du budget
    # parmi les titres disponibles ; les positions < min_position restent en cash
    # (on ne force pas le 100 %).
    W = split_budget_to_brokers(w, access, b_ratios, min_position)
    return W, starr
