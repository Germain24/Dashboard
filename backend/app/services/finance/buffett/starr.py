"""STARR : objectif d'optimisation centré sur les GROSSES CHUTES (CVaR).

STARR = rendement annualisé / CVaR(α). Le CVaR (Expected Shortfall) = perte
moyenne dans les pires α % des cas → pénalise directement les krachs, contrairement
au Sharpe (écart-type symétrique).

Scénarios par **Monte-Carlo + copule de Vine** (dépendance de queue entre titres) :
marginales Student-t → transformation en uniformes (PIT) → copule de Vine ajustée →
simulation → retour aux rendements par quantile inverse Student-t. Repli bootstrap
historique si l'ajustement échoue.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .vine_copula import DVineCopula


def portfolio_cvar(port_returns: np.ndarray, alpha: float = 0.05) -> float:
    """CVaR(α) d'une série de rendements de portefeuille (perte moyenne, >0).

    = moyenne des rendements ≤ quantile α, en valeur de perte (signe inversé).
    """
    p = np.asarray(port_returns, dtype=float)
    if p.size == 0:
        return 0.0
    q = np.percentile(p, alpha * 100.0)
    tail = p[p <= q]
    if tail.size == 0:
        return float(-q)
    return float(-tail.mean())


def downside_deviation(port_returns: np.ndarray, target: float = 0.0) -> float:
    """Semi-déviation baissière : écart-type des rendements SOUS ``target`` (>0).

    Ne pénalise que la baisse (les hausses sont ignorées) → « minimiser la variance
    vers le bas, une grosse montée est ok ». ``target`` = seuil acceptable (0 = perte).
    """
    p = np.asarray(port_returns, dtype=float)
    if p.size == 0:
        return 0.0
    downside = np.minimum(p - target, 0.0)
    return float(np.sqrt(np.mean(downside ** 2)))


def simulate_scenarios(returns, n_sim: int = 50_000, seed: int = 42) -> np.ndarray:
    """Simule ``n_sim`` scénarios de rendements [n_sim × n_actifs].

    Monte-Carlo via copule de Vine + marginales Student-t. Repli sur un bootstrap
    historique (rééchantillonnage des lignes réelles) si l'ajustement échoue ou si
    l'échantillon est trop petit.
    """
    R = np.asarray(returns, dtype=float)
    if R.ndim == 1:
        R = R.reshape(-1, 1)
    n_obs, n = R.shape
    rng = np.random.default_rng(seed)

    def _bootstrap() -> np.ndarray:
        idx = rng.integers(0, n_obs, size=n_sim)
        return R[idx]

    if n < 2 or n_obs < 50:
        return _bootstrap()

    try:
        params: list = []
        U = np.zeros((n_obs, n))
        for i in range(n):
            try:
                p = stats.t.fit(R[:, i])
                U[:, i] = stats.t.cdf(R[:, i], *p)
            except Exception:
                p = None
                U[:, i] = stats.rankdata(R[:, i]) / (n_obs + 1)
            params.append(p)
        U = np.clip(U, 1e-6, 1 - 1e-6)

        np.random.seed(seed)  # DVineCopula.simulate utilise np.random
        vine = DVineCopula(family="t").fit(U)
        U_sim = np.clip(vine.simulate(n_obs=n_sim), 1e-6, 1 - 1e-6)

        sim = np.zeros((n_sim, n))
        for i in range(n):
            if params[i] is not None:
                sim[:, i] = stats.t.ppf(U_sim[:, i], *params[i])
            else:
                sim[:, i] = np.quantile(R[:, i], U_sim[:, i])
        sim = np.nan_to_num(sim, nan=0.0, posinf=0.0, neginf=0.0)
        # garde-fou : si la simulation a dégénéré, repli bootstrap
        if not np.isfinite(sim).all() or sim.std() < 1e-12:
            return _bootstrap()
        return sim
    except Exception:
        return _bootstrap()


def neg_starr(raw_weights: np.ndarray, sim_rets: np.ndarray, mean_daily: np.ndarray,
              alpha: float = 0.05, downside_weight: float = 1.0,
              target: float = 0.0) -> float:
    """-(ratio) pour la minimisation. ``raw_weights`` normalisé sur le simplexe.

    ratio = rendement annualisé / (CVaR annualisé + λ · downside-deviation annualisée).
    Le dénominateur combine le risque de **krach** (CVaR, queue α) ET la **variance
    baissière** (semi-déviation sous ``target``) ; ``downside_weight`` (λ) règle le
    poids de la variance baissière. La volatilité haussière n'est pas pénalisée.
    """
    s = float(np.sum(raw_weights))
    if s <= 1e-12:
        return 1e6
    w = raw_weights / s
    ann_ret = float(mean_daily @ w) * 252.0
    port = sim_rets @ w
    cvar = portfolio_cvar(port, alpha)
    dd = downside_deviation(port, target)
    risk = (cvar + downside_weight * dd) * np.sqrt(252.0)
    risk = max(risk, 0.005)
    ratio = ann_ret / risk
    if not np.isfinite(ratio):
        return 1e6
    return -ratio
