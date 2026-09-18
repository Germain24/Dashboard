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


MIN_DAILY_SIMPLE_RETURN = -0.999
MAX_DAILY_SIMPLE_RETURN = 3.0


def sanitize_simulated_returns(values) -> tuple[np.ndarray, dict[str, int]]:
    """Garantit des scénarios journaliers finis et représentables en float32.

    Une marginale Student mal ajustée peut produire une valeur encore finie en
    float64 mais supérieure à 3e38. Sa conversion en float32 devient alors
    ``inf`` et invalide l'objectif de tous les portefeuilles. Les rendements
    simples sont bornés à -100 % ; le plafond positif de +300 %/jour est un
    garde-fou numérique très au-delà des observations utilisées ici.
    """
    array = np.asarray(values, dtype=np.float64)
    non_finite = int((~np.isfinite(array)).sum())
    extreme = int(
        (
            np.isfinite(array)
            & (
                (array < MIN_DAILY_SIMPLE_RETURN)
                | (array > MAX_DAILY_SIMPLE_RETURN)
            )
        ).sum()
    )
    clean = np.nan_to_num(
        array,
        nan=0.0,
        posinf=MAX_DAILY_SIMPLE_RETURN,
        neginf=MIN_DAILY_SIMPLE_RETURN,
    )
    clean = np.clip(
        clean,
        MIN_DAILY_SIMPLE_RETURN,
        MAX_DAILY_SIMPLE_RETURN,
    )
    return clean, {"non_finite_replaced": non_finite, "extreme_clipped": extreme}


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

    simulated, sanitization = sanitize_simulated_returns(
        np.concatenate(blocks, axis=0)
    )
    diagnostics = {
        "method": "weighted_1y_3y_5y_plus_stress_scenario_mixture",
        "n_observations_available": int(R.shape[0]),
        "windows": used,
        "sanitization": sanitization,
    }
    return simulated, diagnostics


def stratified_scenario_indices(
    diagnostics: dict,
    n_sample: int,
    *,
    seed: int = 42,
) -> tuple[np.ndarray, dict[str, int]]:
    """Sélectionne un sous-échantillon sans déformer le mélange de régimes.

    ``simulate_regime_scenarios`` concatène volontairement les blocs pour rendre
    le diagnostic auditable. Prendre simplement le préfixe favorisait donc le
    premier régime et pouvait supprimer tout le stress de la recherche.
    """
    windows = list(diagnostics.get("windows") or [])
    available = np.asarray(
        [max(0, int(window.get("n_sim") or 0)) for window in windows], dtype=int
    )
    total = int(available.sum())
    wanted = max(0, min(int(n_sample), total))
    if wanted == 0 or total == 0:
        return np.empty(0, dtype=int), {}

    raw = available.astype(float) * (wanted / total)
    counts = np.minimum(np.floor(raw).astype(int), available)
    remainder = wanted - int(counts.sum())
    if remainder:
        order = np.argsort(-(raw - counts), kind="stable")
        # Chaque reste vaut moins d'une observation : lui attribuer plusieurs
        # places surpondérait le premier régime lors des petits échantillons.
        eligible = order[counts[order] < available[order]]
        counts[eligible[:remainder]] += 1

    rng = np.random.default_rng(seed)
    selected: list[np.ndarray] = []
    by_regime: dict[str, int] = {}
    offset = 0
    for window, available_count, count in zip(
        windows, available, counts, strict=True
    ):
        if count:
            local = rng.choice(int(available_count), size=int(count), replace=False)
            selected.append(local + offset)
        label = str(window.get("label") or f"regime_{len(by_regime) + 1}")
        by_regime[label] = int(count)
        offset += int(available_count)
    indices = np.concatenate(selected) if selected else np.empty(0, dtype=int)
    rng.shuffle(indices)
    return indices.astype(int, copy=False), by_regime


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


def _tail_size(n_scenarios: int, alpha: float) -> int:
    """Nombre de scénarios de queue commun aux scoreurs scalaire et vectorisé."""
    if not np.isfinite(alpha) or not 0.0 < alpha <= 1.0:
        raise ValueError("alpha doit être dans ]0, 1]")
    return min(n_scenarios, max(1, int(round(alpha * n_scenarios))))


def portfolio_cvar(port_returns: np.ndarray, alpha: float = 0.05) -> float:
    """CVaR(α) d'une série de rendements de portefeuille (perte moyenne, >0).

    Moyenne des ``round(alpha * n)`` pires rendements, avec au moins un
    scénario. Inclure tous les ex aequo au quantile diluerait les pertes :
    une chute et 99 jours plats doivent retenir cinq jours, pas les cent.
    """
    p = np.asarray(port_returns, dtype=float)
    if p.size == 0:
        return 0.0
    p = p.reshape(-1)
    k = _tail_size(p.size, alpha)
    return float(-np.partition(p, k - 1)[:k].mean(dtype=np.float64))


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
                marginal = stats.t.ppf(U_sim[:, i], *params[i])
                # Un ajustement Student dégénéré peut rester « fini » en
                # float64 tout en dépassant la plage float32. Pour cette seule
                # marginale, conserver la dépendance simulée (U_sim) mais
                # reprendre la distribution empirique, nécessairement bornée.
                if (
                    not np.isfinite(marginal).all()
                    or np.any(marginal < MIN_DAILY_SIMPLE_RETURN)
                    or np.any(marginal > MAX_DAILY_SIMPLE_RETURN)
                ):
                    marginal = np.quantile(R[:, i], U_sim[:, i])
                sim[:, i] = marginal
            else:
                sim[:, i] = np.quantile(R[:, i], U_sim[:, i])
        # garde-fou : si la simulation a dégénéré, repli bootstrap
        if not np.isfinite(sim).all() or sim.std() < 1e-12:
            return _bootstrap()
        return sanitize_simulated_returns(sim)[0]
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
    k = _tail_size(n_sim, alpha)
    tail = np.partition(port, k - 1, axis=0)[:k]
    cvar = -tail.mean(axis=0, dtype=np.float64)
    downside = np.minimum(port - target, 0.0).astype(np.float64)
    dd = np.sqrt(np.mean(downside ** 2, axis=0))
    risk = np.maximum((cvar + downside_weight * dd) * np.sqrt(252.0), 0.005)
    ratio = ann_ret / risk
    out[ok] = np.where(np.isfinite(ratio), -ratio, 1e6)
    return out


SCORE_SCALE = 100.0   # score exprime en POINTS de pourcentage annuels


def benchmark_stats(bench_sim_returns, bench_mean_daily, alpha: float = 0.05,
                    target: float = 0.0) -> dict:
    """Reperes du benchmark, calcules UNE SEULE FOIS avant la boucle DE.

    `bench_sim_returns` doit provenir des MEMES scenarios simules que les
    candidats (colonne dediee de `sim_rets`), sans quoi la comparaison melangerait
    deux tirages differents.
    """
    return {
        "annual_return": float(bench_mean_daily) * 252.0,
        "cvar": float(portfolio_cvar(bench_sim_returns, alpha)) * np.sqrt(252.0),
        "downside_deviation": float(
            downside_deviation(bench_sim_returns, target)
        ) * np.sqrt(252.0),
    }


def risk_reduction_credit() -> float:
    """Crédit courant accordé à un risque INFÉRIEUR au benchmark (cf. Config)."""
    from .config import Config

    return max(float(getattr(Config, "STARR_RISK_REDUCTION_CREDIT", 0.0)), 0.0)


def _risk_excess(measure, benchmark, credit: float):
    """Terme de risque partiellement symétrique, commun aux deux scoreurs.

        max(0, delta) − credit × max(0, −delta)

    ``credit = 0`` redonne exactement la forme unilatérale d'origine. Cette
    fonction est partagée par ``neg_benchmark_relative`` et
    ``benchmark_relative_batch_details`` : les deux DOIVENT rester identiques,
    sinon le polish final noterait autrement que la recherche.
    """
    delta = np.asarray(measure, dtype=float) - float(benchmark)
    return np.maximum(delta, 0.0) - credit * np.maximum(-delta, 0.0)


def neg_benchmark_relative(raw_weights: np.ndarray, sim_rets: np.ndarray,
                           mean_daily: np.ndarray, bench: dict,
                           alpha: float = 0.05, downside_weight: float = 1.0,
                           target: float = 0.0, annual_cost: float = 0.0,
                           credit: float | None = None,
                           normalize_weights: bool = True) -> float:
    """-(score) pour la minimisation. `raw_weights` normalise sur le simplexe.

    score = (rendement - rendement_benchmark)
          - risque(CVaR, CVaR_benchmark)
          - lambda * risque(semi-deviation, semi-deviation_benchmark)

    Trois proprietes voulues :
    - un portefeuille identique au benchmark vaut exactement 0 ;
    - PLUS de division, donc plus de score infini quand le CVaR tend vers 0 : c'est
      ce qui permettait a un ETF monetaire de rafler 96 % de l'allocation ;
    - le terme de risque est ASYMETRIQUE : depasser le risque du benchmark coute
      plein tarif, descendre en dessous ne rapporte que `credit` fois l'ecart
      (cf. Config.STARR_RISK_REDUCTION_CREDIT). A `credit = 0` on retrouve la
      forme strictement unilaterale d'origine ; monter vers 1.0 recree le biais
      monetaire que la forme soustractive avait corrige.

    La semi-deviation ne compte que les journees NEGATIVES : la volatilite a la
    hausse n'est jamais penalisee.

    ``normalize_weights=False`` conserve les fractions du capital effectivement
    investies. Le cash restant a un rendement nul ; renormaliser ces poids
    attribuerait à tort un rendement d'investissement au cash non déployé.
    """
    weights = np.maximum(np.asarray(raw_weights, dtype=float), 0.0)
    s = float(np.sum(weights))
    if not np.isfinite(s) or (normalize_weights and s <= 1e-12):
        return 1e6
    k_credit = risk_reduction_credit() if credit is None else max(float(credit), 0.0)
    w = weights / s if normalize_weights else weights
    ann_ret = float(mean_daily @ w) * 252.0 - max(float(annual_cost), 0.0)
    port = sim_rets @ w
    cvar = portfolio_cvar(port, alpha) * np.sqrt(252.0)
    dd = downside_deviation(port, target) * np.sqrt(252.0)
    score = (
        (ann_ret - bench["annual_return"])
        - float(_risk_excess(cvar, bench["cvar"], k_credit))
        - downside_weight
        * float(_risk_excess(dd, bench["downside_deviation"], k_credit))
    )
    if not np.isfinite(score):
        return 1e6
    return -score * SCORE_SCALE


def benchmark_relative_batch_details(
    raw_weights: np.ndarray,
    sim_rets: np.ndarray,
    mean_daily: np.ndarray,
    bench: dict,
    alpha: float = 0.05,
    downside_weight: float = 1.0,
    target: float = 0.0,
    annual_costs=0.0,
    credit: float | None = None,
    normalize_weights: bool = True,
) -> tuple[np.ndarray, dict]:
    """Score vectorisé et contexte de risque réutilisable par les contraintes.

    `raw_weights` : [n_actifs x S], une colonne par candidat (convention scipy
    `vectorized=True`). Meme estimation du CVaR par `np.partition` que
    `neg_starr_batch` : moyenne des `round(alpha * n_sim)` pires scenarios. Le
    contexte évite de recalculer les rendements de portefeuille pour attribuer
    ensuite le risque baissier aux secteurs.

    Le terme de risque partage STRICTEMENT ``_risk_excess`` avec
    ``neg_benchmark_relative`` : la recherche vectorisee et le polish final
    doivent noter de la meme facon.
    """
    X = np.asarray(raw_weights, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n_sim = sim_rets.shape[0]
    out = np.full(X.shape[1], 1e6)
    X = np.maximum(X, 0.0)
    s = X.sum(axis=0)
    ok = np.isfinite(s) & ((s > 1e-12) if normalize_weights else True)
    if not ok.any():
        return out, {
            "valid": ok,
            "weights": np.empty((X.shape[0], 0), dtype=float),
            "portfolio_returns": np.empty((n_sim, 0), dtype=float),
            "tail_indices": np.empty((0, 0), dtype=int),
            "downside": np.empty((n_sim, 0), dtype=float),
            "downside_deviation_daily": np.empty(0, dtype=float),
            "cvar_daily": np.empty(0, dtype=float),
        }
    W = X[:, ok] / s[ok] if normalize_weights else X[:, ok]
    cost_array = np.broadcast_to(
        np.asarray(annual_costs, dtype=float), (X.shape[1],)
    )[ok]
    ann_ret = (mean_daily @ W) * 252.0 - np.maximum(cost_array, 0.0)
    port = sim_rets @ W.astype(sim_rets.dtype)
    k = _tail_size(n_sim, alpha)
    tail_indices = np.argpartition(port, k - 1, axis=0)[:k]
    tail = np.take_along_axis(port, tail_indices, axis=0)
    cvar_daily = -tail.mean(axis=0, dtype=np.float64)
    cvar = cvar_daily * np.sqrt(252.0)
    downside = np.minimum(port - target, 0.0).astype(np.float64)
    dd_daily = np.sqrt(np.mean(downside ** 2, axis=0))
    dd = dd_daily * np.sqrt(252.0)
    k_credit = risk_reduction_credit() if credit is None else max(float(credit), 0.0)
    score = (
        (ann_ret - bench["annual_return"])
        - _risk_excess(cvar, bench["cvar"], k_credit)
        - downside_weight * _risk_excess(dd, bench["downside_deviation"], k_credit)
    )
    out[ok] = np.where(np.isfinite(score), -score * SCORE_SCALE, 1e6)
    return out, {
        "valid": ok,
        "weights": W,
        "portfolio_returns": port,
        "tail_indices": tail_indices,
        "downside": downside,
        "downside_deviation_daily": dd_daily,
        "cvar_daily": cvar_daily,
    }


def neg_benchmark_relative_batch(raw_weights: np.ndarray, sim_rets: np.ndarray,
                                 mean_daily: np.ndarray, bench: dict,
                                 alpha: float = 0.05, downside_weight: float = 1.0,
                                 target: float = 0.0, annual_costs=0.0,
                                 normalize_weights: bool = True) -> np.ndarray:
    """Version vectorisée conservant l'interface historique (score uniquement)."""
    score, _ = benchmark_relative_batch_details(
        raw_weights,
        sim_rets,
        mean_daily,
        bench,
        alpha,
        downside_weight,
        target,
        annual_costs,
        normalize_weights=normalize_weights,
    )
    return score
