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


def shrink_correlation(corr: np.ndarray, intensity: float = 0.15) -> np.ndarray:
    """Régularise une matrice vers une cible à corrélation constante.

    La transformation conserve la diagonale à 1 et réduit les corrélations
    extrêmes dues au bruit d'échantillonnage. ``intensity=0`` laisse la matrice
    inchangée ; ``1`` utilise uniquement la corrélation hors diagonale moyenne.
    """
    C = np.asarray(corr, dtype=float)
    if C.ndim != 2 or C.shape[0] != C.shape[1] or C.shape[0] < 2:
        return C.copy()
    lam = min(max(float(intensity), 0.0), 1.0)
    tri = C[np.triu_indices(C.shape[0], 1)]
    finite = tri[np.isfinite(tri)]
    rho = float(np.mean(finite)) if finite.size else 0.0
    rho = float(np.clip(rho, -1.0 / max(C.shape[0] - 1, 1) + 1e-6, 0.999))
    target = np.full_like(C, rho)
    np.fill_diagonal(target, 1.0)
    out = (1.0 - lam) * np.nan_to_num(C, nan=rho) + lam * target
    out = np.clip((out + out.T) / 2.0, -0.999, 0.999)
    np.fill_diagonal(out, 1.0)
    return out


def resolve_regime_windows(
    n_obs: int,
    windows: list[dict] | None = None,
    min_coverage: float | None = None,
) -> list[dict]:
    """Résout les fenêtres 1/3/5 ans réellement utilisables.

    Les poids des fenêtres indisponibles sont redistribués entre les fenêtres
    restantes. Le seuil de couverture tolère les petites différences de calendrier
    boursier (un téléchargement Yahoo de 5 ans contient rarement exactement 1260
    séances). Pour un petit échantillon de test, on conserve une fenêtre unique.
    """
    from .config import Config

    specs = windows if windows is not None else Config.STARR_REGIME_WINDOWS
    coverage = float(
        Config.STARR_REGIME_MIN_COVERAGE if min_coverage is None else min_coverage
    )
    coverage = min(max(coverage, 0.0), 1.0)
    usable: list[dict] = []
    for raw in specs:
        try:
            label = str(raw["label"])
            days = int(raw["days"])
            weight = float(raw["weight"])
        except (KeyError, TypeError, ValueError):
            continue
        if days <= 0 or weight <= 0:
            continue
        required = max(50, int(np.ceil(days * coverage)))
        if n_obs >= required:
            usable.append({
                "label": label,
                "target_days": days,
                "observations": min(days, n_obs),
                "raw_weight": weight,
            })

    if not usable:
        return [{
            "label": "available",
            "target_days": int(n_obs),
            "observations": int(n_obs),
            "raw_weight": 1.0,
            "weight": 1.0,
        }]

    total = sum(item["raw_weight"] for item in usable)
    for item in usable:
        item["weight"] = item["raw_weight"] / total
    return usable


def simulate_regime_scenarios(
    returns,
    n_sim: int = 50_000,
    seed: int = 42,
    windows: list[dict] | None = None,
    min_coverage: float | None = None,
    stress_weight: float | None = None,
    stress_vol_multiplier: float | None = None,
    stress_correlation: float | None = None,
) -> tuple[np.ndarray, dict]:
    """Simule un mélange pondé des régimes 1/3/5 ans.

    Le nombre total de scénarios reste exactement ``n_sim`` : le coût mémoire et
    celui des évaluations STARR ne croissent donc pas avec le nombre de fenêtres.
    """
    R = np.asarray(returns, dtype=float)
    if R.ndim == 1:
        R = R.reshape(-1, 1)
    from .config import Config

    regimes = resolve_regime_windows(R.shape[0], windows, min_coverage)
    stress_w = float(Config.STARR_STRESS_WEIGHT if stress_weight is None else stress_weight)
    stress_w = min(max(stress_w, 0.0), 0.50)
    vol_mult = float(
        Config.STARR_STRESS_VOL_MULTIPLIER
        if stress_vol_multiplier is None else stress_vol_multiplier
    )
    target_corr = float(
        Config.STARR_STRESS_EQUITY_CORRELATION
        if stress_correlation is None else stress_correlation
    )

    mixture = [
        {**regime, "mixture_weight": regime["weight"] * (1.0 - stress_w)}
        for regime in regimes
    ]
    if stress_w > 0:
        mixture.append({
            "label": "stress",
            "target_days": min(252, R.shape[0]),
            "observations": min(252, R.shape[0]),
            "raw_weight": stress_w,
            "weight": stress_w,
            "mixture_weight": stress_w,
            "stress": True,
        })

    raw_counts = np.array([r["mixture_weight"] * n_sim for r in mixture], dtype=float)
    counts = np.floor(raw_counts).astype(int)
    remainder = int(n_sim - counts.sum())
    if remainder > 0:
        order = np.argsort(-(raw_counts - counts), kind="stable")
        counts[order[:remainder]] += 1

    blocks: list[np.ndarray] = []
    used: list[dict] = []
    for idx, (regime, count) in enumerate(zip(mixture, counts, strict=True)):
        if count <= 0:
            continue
        observations = int(regime["observations"])
        if regime.get("stress"):
            block = simulate_stress_scenarios(
                R[-observations:],
                n_sim=int(count),
                seed=int(seed + idx * 1009),
                vol_multiplier=vol_mult,
                target_correlation=target_corr,
            )
        else:
            block = simulate_scenarios(
                R[-observations:], n_sim=int(count), seed=int(seed + idx * 1009)
            )
        blocks.append(block)
        used.append({
            "label": regime["label"],
            "target_days": int(regime["target_days"]),
            "observations": observations,
            "weight": float(regime["mixture_weight"]),
            "n_sim": int(count),
        })

    simulated = np.concatenate(blocks, axis=0)
    diagnostics = {
        "method": "weighted_1y_3y_5y_plus_stress_scenario_mixture",
        "n_observations_available": int(R.shape[0]),
        "windows": used,
    }
    return simulated, diagnostics


def simulate_stress_scenarios(
    returns,
    n_sim: int,
    seed: int = 42,
    vol_multiplier: float = 2.0,
    target_correlation: float = 0.85,
) -> np.ndarray:
    """Construit des scénarios de crise à partir des pires journées observées.

    Les actifs procycliques (corrélation positive avec la moyenne de l'univers)
    reçoivent un facteur commun afin que leur corrélation augmente en crise. Les
    actifs historiquement défensifs conservent leurs observations empiriques.
    Les pertes sont ensuite amplifiées par ``vol_multiplier``.
    """
    R = np.asarray(returns, dtype=float)
    if R.ndim == 1:
        R = R.reshape(-1, 1)
    if not len(R) or n_sim <= 0:
        return np.empty((0, R.shape[1]), dtype=float)
    rng = np.random.default_rng(seed)
    market = np.nanmean(R, axis=1)
    cutoff = np.nanpercentile(market, 20)
    tail_idx = np.flatnonzero(market <= cutoff)
    if not len(tail_idx):
        tail_idx = np.arange(len(R))
    idx = rng.choice(tail_idx, size=n_sim, replace=True)
    block = np.nan_to_num(R[idx], nan=0.0)

    if R.shape[1] >= 2:
        market_std = float(np.nanstd(market))
        asset_std = np.nanstd(R, axis=0)
        cov = np.nanmean((R - np.nanmean(R, axis=0)) * (market - np.nanmean(market))[:, None], axis=0)
        denom = np.maximum(asset_std * max(market_std, 1e-12), 1e-12)
        procyclical = (cov / denom) > 0.20
        if int(procyclical.sum()) >= 2:
            Z = block[:, procyclical] / np.maximum(asset_std[procyclical], 1e-12)
            common = np.mean(Z, axis=1)
            common = (common - common.mean()) / max(float(common.std()), 1e-12)
            rho = min(max(float(target_correlation), 0.0), 0.99)
            Z = np.sqrt(rho) * common[:, None] + np.sqrt(1.0 - rho) * Z
            block[:, procyclical] = Z * asset_std[procyclical]

    multiplier = max(float(vol_multiplier), 1.0)
    return np.where(block < 0.0, block * multiplier, block)


def correlation_stability_diagnostics(
    returns,
    tickers: list[str] | None = None,
    windows: list[dict] | None = None,
    min_coverage: float | None = None,
    top_n: int = 20,
) -> dict:
    """Résume les divergences de corrélation de Spearman entre les régimes."""
    R = np.asarray(returns, dtype=float)
    if R.ndim == 1:
        R = R.reshape(-1, 1)
    n_assets = R.shape[1]
    names = list(tickers or [str(i) for i in range(n_assets)])
    regimes = resolve_regime_windows(R.shape[0], windows, min_coverage)
    matrices: list[np.ndarray] = []
    labels: list[str] = []
    observations: dict[str, int] = {}
    for regime in regimes:
        n = int(regime["observations"])
        ranks = np.apply_along_axis(stats.rankdata, 0, R[-n:])
        corr = np.atleast_2d(np.corrcoef(ranks, rowvar=False))
        matrices.append(corr)
        labels.append(str(regime["label"]))
        observations[str(regime["label"])] = n

    base = {
        "method": "spearman",
        "windows": observations,
        "thresholds": {"unstable": 0.25, "major_shift": 0.40},
        "available": len(matrices) >= 2 and n_assets >= 2,
    }
    if not base["available"]:
        return {**base, "reason": "at_least_two_windows_and_assets_required"}

    tri_i, tri_j = np.triu_indices(n_assets, 1)
    pair_values = np.stack([m[tri_i, tri_j] for m in matrices], axis=0)
    deltas = np.nanmax(pair_values, axis=0) - np.nanmin(pair_values, axis=0)
    valid = np.isfinite(deltas)
    if not valid.any():
        return {**base, "available": False, "reason": "no_finite_pair"}

    valid_idx = np.flatnonzero(valid)
    ranked = valid_idx[np.argsort(-deltas[valid_idx], kind="stable")[:max(0, top_n)]]
    top_pairs = []
    for k in ranked:
        top_pairs.append({
            "ticker_a": names[int(tri_i[k])],
            "ticker_b": names[int(tri_j[k])],
            "max_delta": float(deltas[k]),
            "correlations": {
                label: float(pair_values[pos, k])
                for pos, label in enumerate(labels)
                if np.isfinite(pair_values[pos, k])
            },
        })

    finite = deltas[valid]
    return {
        **base,
        "n_pairs": int(finite.size),
        "mean_delta": float(np.mean(finite)),
        "median_delta": float(np.median(finite)),
        "p90_delta": float(np.percentile(finite, 90)),
        "max_delta": float(np.max(finite)),
        "unstable_pairs": int(np.sum(finite >= 0.25)),
        "major_shift_pairs": int(np.sum(finite >= 0.40)),
        "top_pairs": top_pairs,
    }


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
    from .config import Config
    rho = shrink_correlation(rho, float(Config.STARR_CORRELATION_SHRINKAGE))
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
              target: float = 0.0, annual_cost: float = 0.0) -> float:
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
    ann_ret = float(mean_daily @ w) * 252.0 - max(float(annual_cost), 0.0)
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
                    target: float = 0.0, annual_costs=0.0) -> np.ndarray:
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
    cost_array = np.broadcast_to(
        np.asarray(annual_costs, dtype=float), (X.shape[1],)
    )[ok]
    ann_ret = (mean_daily @ W) * 252.0 - np.maximum(cost_array, 0.0)
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
