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


def _gaussian_copula_uniforms(R: np.ndarray, n_sim: int, rng) -> np.ndarray:
    """Uniformes simulées via copule GAUSSIENNE sur la corrélation de Spearman
    COMPLÈTE (convertie en corrélation de Pearson par 2·sin(π/6·ρs)).

    Voie rapide pour les grands univers : l'ajustement D-vine est O(n²) taus de
    Kendall en boucle Python (~1 h à 1250 titres) alors que sa `simulate()` ne
    retient qu'une matrice de corrélation creuse (chemin D-vine) passée dans
    une gaussienne -- ici la matrice est pleine ET le calcul vectorisé.
    """
    from .vine_copula import is_pos_def, nearest_pos_def

    ranks = np.apply_along_axis(stats.rankdata, 0, R)
    rho_s = np.corrcoef(ranks, rowvar=False)
    rho = 2.0 * np.sin(np.pi / 6.0 * np.clip(rho_s, -1.0, 1.0))
    np.fill_diagonal(rho, 1.0)
    if not is_pos_def(rho):
        rho = nearest_pos_def(rho)
    z = rng.multivariate_normal(np.zeros(R.shape[1]), rho, size=n_sim,
                                method="cholesky")
    return stats.norm.cdf(z)


def simulate_scenarios(returns, n_sim: int = 50_000, seed: int = 42) -> np.ndarray:
    """Simule ``n_sim`` scénarios de rendements [n_sim × n_actifs].

    Monte-Carlo via copule + marginales Student-t : copule de Vine jusqu'à
    ``Config.STARR_VINE_MAX_DIM`` titres, copule gaussienne (corrélation
    Spearman complète) au-delà -- cf. `_gaussian_copula_uniforms`. Repli sur un
    bootstrap historique (rééchantillonnage des lignes réelles) si l'ajustement
    échoue ou si l'échantillon est trop petit.
    """
    from .config import Config

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

        if n > int(Config.STARR_VINE_MAX_DIM):
            print(f"    * Copule gaussienne (corr. Spearman pleine) : {n} titres "
                  f"> STARR_VINE_MAX_DIM={Config.STARR_VINE_MAX_DIM} (vine intraitable)")
            U_sim = np.clip(_gaussian_copula_uniforms(R, n_sim, rng), 1e-6, 1 - 1e-6)
        else:
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


def neg_starr_batch(raw_weights: np.ndarray, sim_rets: np.ndarray, mean_daily: np.ndarray,
                    alpha: float = 0.05, downside_weight: float = 1.0,
                    target: float = 0.0) -> np.ndarray:
    """Version VECTORISÉE de ``neg_starr`` sur une population entière.

    ``raw_weights`` : [n_actifs × S], une colonne par candidat (convention scipy
    ``vectorized=True``). Retourne [S]. Toute la population est évaluée en UN
    produit matriciel BLAS (``sim_rets @ W``) au lieu de S appels scalaires.
    Le CVaR est estimé par la moyenne des ``round(α·n_sim)`` pires scénarios
    (``np.partition``), équivalent au percentile de ``portfolio_cvar`` à ±1
    scénario près. ``sim_rets`` peut être en float32 (recherche DE) : les
    agrégats sont accumulés en float64.
    """
    X = np.asarray(raw_weights, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n_sim = sim_rets.shape[0]
    out = np.full(X.shape[1], 1e6)
    X = np.maximum(X, 0.0)
    s = X.sum(axis=0)
    ok = s > 1e-12
    if not ok.any():
        return out
    W = X[:, ok] / s[ok]
    ann_ret = (mean_daily @ W) * 252.0
    port = sim_rets @ W.astype(sim_rets.dtype)     # (n_sim × S_ok), gros matmul BLAS
    k = max(1, int(round(alpha * n_sim)))
    tail = np.partition(port, k - 1, axis=0)[:k]
    cvar = -tail.mean(axis=0, dtype=np.float64)
    downside = np.minimum(port - target, 0.0).astype(np.float64)
    dd = np.sqrt(np.mean(downside ** 2, axis=0))
    risk = np.maximum((cvar + downside_weight * dd) * np.sqrt(252.0), 0.005)
    ratio = ann_ret / risk
    out[ok] = np.where(np.isfinite(ratio), -ratio, 1e6)
    return out
