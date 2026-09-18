"""Optimiseur de portefeuille STARR via Monte Carlo + copule de Vine."""

from __future__ import annotations

import math
import time

import numpy as np
from scipy import stats
from scipy.optimize import minimize

from .allocation import broker_line_cap, is_fractional_broker
from .broker_availability import load_asset_classes, load_etf_tickers
from .config import Config


def _get_active_brokers() -> list[str]:
    return [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]


def _is_true(val) -> bool:
    import pandas as pd

    if pd.isna(val) or str(val).strip() == "":
        return False
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    try:
        return float(val) != 0
    except (ValueError, TypeError):
        pass
    return str(val).strip().upper() in ["VRAI", "TRUE", "OUI", "1", "1.0"]


def _get_broker_col(b_name: str, columns: list) -> str | None:
    import re

    def clean(v):
        return "".join(filter(str.isalnum, str(v).upper()))

    cb = clean(b_name)
    for c in columns:
        if cb == clean(c):
            return c
    bn = re.search(r"(\d+)$", b_name)
    for c in columns:
        cc = clean(c)
        if cb in cc or cc in cb:
            cn = re.search(r"(\d+)$", c)
            if (bn.group(1) if bn else None) == (cn.group(1) if cn else None):
                return c
    return None


def prepare_optimization(tickers: list[str], df) -> tuple[list, list]:
    """Retourne (matrix_access, active_brokers)."""
    import pandas as pd

    ticker_col = "Ticker Yahoo Finance"
    base_cols = {
        ticker_col,
        "Nom",
        "Pays",
        "Prix",
        "EPS",
        "PER",
        "Croissance",
        "PEG",
        "Volume",
        "Achat",
        "Chance MOAT",
        "Secteur",
        "Poids",
        "ISIN",
        "Execution Routes",
        "Fundamentals Symbol",
        "Primary MIC",
        "Primary Market",
    }
    broker_cols = [c for c in df.columns if c not in base_cols]
    active = _get_active_brokers()
    matrix = []
    for t in tickers:
        rows = df[df[ticker_col] == t]
        row_acc = []
        for b in active:
            col = _get_broker_col(b, broker_cols)
            # Une colonne absente ou vide signifie UNKNOWN, jamais disponible.
            access = False
            if col and not rows.empty:
                v = rows.iloc[0][col]
                if not pd.isna(v):
                    access = _is_true(v)
            row_acc.append(access)
        matrix.append(row_acc)
    return matrix, active


def meets_optimization_score_threshold(
    ticker: str,
    score: float,
    threshold: float,
    forced_tickers: list[str] | tuple[str, ...] | set[str] = (),
    *,
    is_etf: bool = False,
    quality_score: float | None = None,
    confidence_pct: float | None = None,
    comparable_to_standard: bool = True,
    model_complete: bool = True,
    fundamental_mismatch: bool = False,
    min_confidence_pct: float = 35.0,
) -> bool:
    """Vrai si un instrument peut recevoir une allocation cible.

    Une ancienne allocation ne constitue pas une dérogation au seuil : sinon
    une action passée sous 80 reste indéfiniment réinvestissable. Les seules
    exceptions sont les ETF explicitement typés et les tickers forcés.
    """
    forced = {str(item).strip().upper() for item in forced_tickers}
    normalized = str(ticker).strip().upper()
    if is_etf:
        return True
    # Un ticker forcé peut contourner un seuil de score, jamais un garde-fou
    # d'identité ou l'absence d'un modèle utilisable.
    if (
        not bool(comparable_to_standard)
        or not bool(model_complete)
        or bool(fundamental_mismatch)
    ):
        return False
    if normalized in forced:
        return True
    # Compatibilité des anciens appels qui ne disposent que du classement.
    if quality_score is None:
        return float(score or 0.0) >= float(threshold)
    return (
        float(quality_score) >= float(threshold)
        and float(confidence_pct or 0.0) >= float(min_confidence_pct)
        and bool(comparable_to_standard)
        and bool(model_complete)
        and not bool(fundamental_mismatch)
    )


def optimize_portfolio(
    tickers: list[str],
    returns,  # pd.DataFrame
    cov_mat: np.ndarray,
    matrix_access: list,
    active_brokers: list[str],
    vine,
    n_sim: int = 500_000,
) -> tuple[np.ndarray, float]:
    """Optimise le portefeuille (STARR via Monte Carlo + copule).

    Retourne (units_matrix [n_tickers × n_brokers, entiers 0-100], final_starr).
    """
    num_t = len(tickers)
    num_b = len(active_brokers)
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
                for i in avail:
                    w0[i * num_b + j] = val
        lb, ub = [b[0] for b in bounds], [b[1] for b in bounds]
        w0 = np.clip(w0, lb, ub)
        if fallback_w0 is None:
            fallback_w0 = w0.copy()
        if start > 0:
            w0 = np.clip(w0 + np.random.normal(0, 0.01, n_vars), lb, ub)
        res = minimize(
            lambda w: -starr(w)[2],
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-6, "maxiter": 500, "eps": 1e-3},
        )
        if res.success and -res.fun > best_val:
            best_val, best_w = -res.fun, res.x

    if best_w is None:
        best_w = fallback_w0
        best_val = starr(best_w)[2]

    # Phase 2 : Min CVaR dans zone STARR >= 90% du max
    target = 0.9 * best_val if best_val >= 0 else 1.1 * best_val
    res2 = minimize(
        lambda w: starr(w)[1],
        best_w,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints + [{"type": "ineq", "fun": lambda w: starr(w)[2] - target}],
        options={"ftol": 1e-6, "maxiter": 500, "eps": 1e-3},
    )
    final_w = res2.x if (res2.success and res2.x is not None) else best_w
    _, _, final_starr = starr(final_w)

    # Phase 3 : Discrétisation Hare-Niemeyer (1% incréments)
    wm = final_w.reshape(num_t, num_b)
    units = np.zeros((num_t, num_b), dtype=int)
    for j in range(num_b):
        if b_ratios[j] <= 0:
            continue
        pcts = wm[:, j] / b_ratios[j] * 100
        floors = np.floor(np.maximum(pcts, 0)).astype(int)
        rests = pcts - floors
        diff = 100 - floors.sum()
        if diff > 0:
            for idx in np.argsort(rests)[-diff:]:
                floors[idx] += 1
        units[:, j] = floors

    print(f"    * STARR final : {final_starr:.3f}")
    return units, final_starr


# ---------------------------------------------------------------------------
# Differential Evolution optimizer (remplace STARR SLSQP pour le portefeuille)
# ---------------------------------------------------------------------------


def assign_tickers_to_brokers(w, access, b_ratios, min_position: float = 0.0) -> np.ndarray:
    """Affecte chaque titre pondéré (``w >= min_position`` et ``w > 0``) à UN SEUL
    broker parmi ceux qui le proposent (budget > 0). Cantonnement strict.

    Heuristique min-dérive : les titres sont traités du plus gros poids au plus
    petit ; chacun va au broker ayant le plus de capacité € RESTANTE
    (``b_ratios[j] − Σ w déjà affectés``). Remplir chaque broker vers son budget
    minimise la dérive de poids ET évite de laisser un broker sans titre
    (anti-cash-oisif : un broker à vide a la capacité restante maximale, il attire
    donc le prochain titre disponible). Retourne un vecteur int [n] : indice de
    broker par titre, ``-1`` si non pondéré ou non plaçable (aucun broker dispo
    avec budget).
    """
    # Chemin chaud (appelé 1×/candidat × génération dans le malus DE) : on convertit
    # en listes Python une bonne fois pour éviter l'indexation numpy scalaire
    # (``acc[i, j]``) et ``np.argmax`` sur de petites listes, ~5-10× plus lents.
    acc = np.asarray(access, dtype=bool)
    n, num_b = acc.shape
    wl = np.asarray(w, dtype=float).tolist()
    br = np.asarray(b_ratios, dtype=float).tolist()
    acc_rows = acc.tolist()
    budget_ok = [br[j] > 0.0 for j in range(num_b)]
    remaining = list(br)
    assign = np.full(n, -1, dtype=int)
    order = [i for i in range(n) if wl[i] >= min_position and wl[i] > 0.0]
    order.sort(key=lambda i: wl[i], reverse=True)
    for i in order:
        row = acc_rows[i]
        best_j, best_rem = -1, None  # argmax de la capacité restante
        for j in range(num_b):  # (1er max en cas d'égalité, comme np.argmax)
            if row[j] and budget_ok[j] and (best_rem is None or remaining[j] > best_rem):
                best_rem, best_j = remaining[j], j
        if best_j >= 0:
            assign[i] = best_j
            remaining[best_j] -= wl[i]
    return assign


def per_broker_cardinality_penalty(
    w, access, b_ratios, max_per_broker: int, beta: float, threshold: float
) -> float:
    """Malus exponentiel quand un broker dépasse ``max_per_broker`` lignes RÉELLES.

    Compte les lignes réellement déployées par broker via
    ``assign_tickers_to_brokers`` (chaque titre pondéré affecté à UN seul broker),
    puis pénalise l'excès : ``Σ_broker exp(β·excès)−1``. Un titre partagé n'est plus
    compté en double — une ligne à 0 % chez un broker compte pour 0. Cap PAR broker
    (ex. 20 dans Trading212 ET 20 dans BoursDirect), pas un total global.
    """
    if beta <= 0:
        return 0.0
    a = assign_tickers_to_brokers(w, access, b_ratios, threshold)
    num_b = np.asarray(access).shape[1]
    counts = np.bincount(a[a >= 0], minlength=num_b)
    excess = counts - max_per_broker
    return float(np.sum(np.where(excess > 0, np.exp(beta * excess) - 1.0, 0.0)))


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


def country_exposure_matrix(
    tickers: list[str],
    exposures: dict[str, dict[str, float]],
    *,
    excluded_buckets: set[str] | None = None,
) -> tuple[list[str], np.ndarray]:
    """Construit la matrice pays en ignorant les seaux non géographiques."""
    excluded = excluded_buckets or set()
    countries = sorted({
        country
        for ticker in tickers
        for country in (exposures.get(ticker) or {})
        if country not in excluded
    })
    positions = {country: index for index, country in enumerate(countries)}
    matrix = np.zeros((len(tickers), len(countries)), dtype=float)
    for ticker_index, ticker in enumerate(tickers):
        for country, value in (exposures.get(ticker) or {}).items():
            country_index = positions.get(country)
            if country_index is not None:
                matrix[ticker_index, country_index] = float(value)
    return countries, matrix


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


def cap_sector_weights_cube(
    cube: np.ndarray,
    labels: list[str | None],
    max_sector,
    sector_matrix: np.ndarray | None = None,
    sector_names: list[str] | None = None,
) -> np.ndarray:
    """Applique un plafond sectoriel au capital total sans renormalisation.

    ``max_sector`` accepte un ``float`` (plafond unique, comportement historique)
    ou un ``SectorCaps`` porteur de surcharges par compartiment (ex. l'or).
    """
    from .sector_constraints import as_sector_caps

    caps = as_sector_caps(max_sector)
    capped = np.asarray(cube, dtype=float).copy()
    if caps.max() <= 0 or caps.min() >= 1:
        return capped
    if sector_matrix is not None:
        matrix = np.asarray(sector_matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != capped.shape[0]:
            raise ValueError("sector_matrix doit avoir une ligne par ticker")
        if sector_names is None and not caps.is_uniform():
            # Échouer bruyamment : sans les noms de colonnes, les surcharges
            # seraient silencieusement ignorées et l'or repasserait à 25 %.
            raise ValueError(
                "sector_names est requis quand les plafonds ne sont pas uniformes"
            )
        cap_vec = (
            caps.as_array(sector_names)
            if sector_names is not None
            else np.full(matrix.shape[1], caps.default, dtype=float)
        )
        if cap_vec.shape[0] != matrix.shape[1]:
            raise ValueError("sector_names doit couvrir chaque colonne de sector_matrix")
        # Projection conservatrice itérative. Un ETF mixte n'est réduit que de
        # la fraction qui contribue au secteur dépassé ; aucun secteur ne peut
        # ainsi être masqué derrière l'étiquette générique de l'ETF.
        # Pour un secteur s, on retire à chaque ligne une fraction k*s_i. Alors
        # E_nouveau = E - k*Σ(w_i*s_i²), ce qui donne directement le k requis.
        # Les secteurs suivants ne font que réduire les poids : un plafond déjà
        # respecté ne peut donc jamais être repercé.
        for sector_index in range(matrix.shape[1]):
            shares = matrix[:, sector_index]
            if not np.any(shares > 0):
                continue
            sector_cap = float(cap_vec[sector_index])
            if sector_cap <= 0 or sector_cap >= 1:
                continue
            for _ in range(3):
                total_by_ticker = capped.sum(axis=1)
                exposure = shares @ total_by_ticker
                over = exposure > sector_cap + 1e-12
                if not over.any():
                    break
                denominator = (shares * shares) @ total_by_ticker
                k = np.zeros_like(exposure)
                valid = over & (denominator > 1e-15)
                k[valid] = (exposure[valid] - sector_cap) / denominator[valid]
                multiplier = np.clip(1.0 - shares[:, None] * k[None, :], 0.0, 1.0)
                capped *= multiplier[:, None, :]
        return capped
    for sector in sorted({label for label in labels if label}):
        sector_cap = caps.for_label(sector)
        if sector_cap <= 0 or sector_cap >= 1:
            continue
        rows = np.array([label == sector for label in labels], dtype=bool)
        exposure = capped[rows, :, :].sum(axis=(0, 1))
        factor = np.ones_like(exposure)
        over = exposure > sector_cap + 1e-12
        factor[over] = sector_cap / exposure[over]
        capped[rows, :, :] *= factor[None, None, :]
    return capped


def cap_stock_weights_cube(
    cube: np.ndarray,
    is_etf: np.ndarray,
    max_position: float,
) -> np.ndarray:
    """Plafonne chaque action sur le capital total, après ventilation broker.

    La ventilation par broker peut renormaliser un sous-panier et faire repasser
    une action au-dessus du plafond appliqué au vecteur de préférences. Le
    reliquat reste en espèces : le redistribuer ici risquerait de violer à
    nouveau un plafond sectoriel ou une disponibilité broker.
    """
    capped = np.asarray(cube, dtype=float).copy()
    flags = np.asarray(is_etf, dtype=bool)
    if max_position <= 0 or max_position >= 1:
        return capped
    exposure = capped.sum(axis=1)
    over = (~flags[:, None]) & (exposure > max_position + 1e-12)
    factors = np.ones_like(exposure)
    factors[over] = max_position / exposure[over]
    capped *= factors[:, None, :]
    return capped


def redeploy_uninvested_cube(
    cube: np.ndarray,
    is_etf: np.ndarray,
    max_position: float,
    labels: list[str | None],
    max_sector,
    b_ratios,
    iterations: int = 3,
    fallback_basis: np.ndarray | None = None,
    max_lines: int | np.ndarray | None = None,
    sector_matrix: np.ndarray | None = None,
    sector_names: list[str] | None = None,
) -> np.ndarray:
    """Replace en titres le cash libéré par les plafonds action/secteur.

    Les plafonds écrêtent sans redistribuer : un secteur saturé (santé à 20 %)
    laissait mécaniquement plusieurs % du capital en espèces, que le portefeuille
    final affichait tel quel. Ici l'écart au budget de chaque broker est
    redéployé, au prorata des poids déjà présents, sur les seules lignes qui ont
    encore de la marge (plafond action ET plafond sectoriel), puis les plafonds
    sont réappliqués. On itère : chaque passe rapproche du budget sans violer une
    contrainte ni ouvrir une ligne indisponible chez le broker — seules les
    lignes déjà pondérées chez CE broker reçoivent le complément. Si
    ``fallback_basis`` est fourni, le redéploiement peut aussi ouvrir une ligne
    disponible mais encore nulle chez ce broker. C'est indispensable lorsqu'un
    petit broker n'a reçu qu'un titre d'un secteur ensuite plafonné.
    """
    from .sector_constraints import as_sector_caps

    caps = as_sector_caps(max_sector)
    flags = np.asarray(is_etf, dtype=bool)
    capped = cap_sector_weights_cube(
        cap_stock_weights_cube(cube, flags, max_position), labels, caps,
        sector_matrix, sector_names,
    )
    targets = np.asarray(b_ratios, dtype=float)[:, None]
    fallback = (
        np.maximum(np.asarray(fallback_basis, dtype=float), 0.0)
        if fallback_basis is not None
        else None
    )
    if fallback is not None and fallback.shape != capped.shape:
        raise ValueError("fallback_basis doit avoir la même forme que cube")
    sector_rows = [
        np.array([label == sector for label in labels], dtype=bool)
        for sector in sorted({label for label in labels if label})
    ] if sector_matrix is None else []
    # Le plafond de CHAQUE secteur, aligné sur sector_rows : sans cela, la marge
    # calculée plus bas laisserait l'or remonter jusqu'au plafond commun.
    sector_rows_caps = [
        caps.for_label(sector)
        for sector in sorted({label for label in labels if label})
    ] if sector_matrix is None else []
    for _ in range(max(0, int(iterations))):
        deficit = np.maximum(targets - capped.sum(axis=0), 0.0)   # [num_b × S]
        if float(np.max(deficit)) <= 1e-12:
            break
        exposure = capped.sum(axis=1)                              # [n × S]
        room = np.where(flags[:, None], np.inf, max_position - exposure)
        room = np.maximum(room, 0.0)
        for rows, sector_cap in zip(sector_rows, sector_rows_caps, strict=True):
            sector_room = np.maximum(
                sector_cap - capped[rows, :, :].sum(axis=(0, 1)), 0.0
            )
            room[rows] = np.minimum(room[rows], sector_room[None, :])
        basis = np.where(
            (capped > 1e-12) & (room[:, None, :] > 1e-12), capped, 0.0
        )
        if fallback is not None:
            candidates = np.where(
                (capped <= 1e-12)
                & (fallback > 1e-12)
                & (room[:, None, :] > 1e-12),
                fallback,
                0.0,
            )
            if max_lines is not None:
                # Respecte le plafond de lignes par broker en n'ouvrant que les
                # meilleures alternatives nécessaires pour chaque candidat.
                current_counts = (capped > 1e-12).sum(axis=0)
                for broker_index in range(capped.shape[1]):
                    line_limit = int(
                        max_lines
                        if np.ndim(max_lines) == 0
                        else np.asarray(max_lines)[broker_index]
                    )
                    for candidate_index in range(capped.shape[2]):
                        slots = max(
                            0,
                            line_limit - int(current_counts[broker_index, candidate_index]),
                        )
                        column = candidates[:, broker_index, candidate_index]
                        positive_count = int((column > 1e-12).sum())
                        if positive_count > slots:
                            if slots == 0:
                                column[:] = 0.0
                            else:
                                keep = np.argpartition(column, -slots)[-slots:]
                                mask = np.ones(len(column), dtype=bool)
                                mask[keep] = False
                                column[mask] = 0.0
            basis += candidates
        totals = basis.sum(axis=0)                                 # [num_b × S]
        usable = totals > 1e-12
        if not usable.any():
            break
        scale = np.zeros_like(totals)
        scale[usable] = deficit[usable] / totals[usable]
        capped = cap_sector_weights_cube(
            cap_stock_weights_cube(
                capped + basis * scale[None, :, :], flags, max_position
            ),
            labels,
            caps,
            sector_matrix,
            sector_names,
        )
    return capped


def split_budget_to_brokers(
    w, access, b_ratios, min_position: float = 0.0, fallback_max_lines: int | None = None
) -> np.ndarray:
    """Déploie le budget de chaque broker sur ses titres AFFECTÉS, au prorata du poids
    optimiseur ``w`` (somme 1). Retourne W [n_tickers × n_brokers, fraction du capital
    total].

    Cantonnement préférentiel : l'affectation principale place chaque titre chez
    un broker. Un complément partagé reste autorisé pour remplir un broker que
    cette première affectation aurait laissé vide.
    - ``min_position`` : les titres dont le poids < seuil ne sont PAS achetés (micro-
      lignes) ; leur part est redéployée sur les titres gardés du même broker via la
      normalisation prorata (l'argent reste investi).
    - Débordement : si le poids cible cumulé des titres affectés à un broker dépasse
      son budget, la normalisation prorata plafonne et redéploie l'excédent sur ces
      mêmes titres (dérive de poids, jamais un 2e broker).
    - Broker affamé : son complément privilégie les titres qui lui sont propres.
      À défaut, quelques titres partagés peuvent être utilisés, sans recopier
      automatiquement tout le panier de l'autre broker.
    """
    w = np.asarray(w, dtype=float)
    num_t = len(w)
    num_b = len(b_ratios)
    W = np.zeros((num_t, num_b))
    assign = assign_tickers_to_brokers(w, access, b_ratios, min_position)
    for j in range(num_b):
        if b_ratios[j] <= 0:
            continue
        kept = [i for i in range(num_t) if assign[i] == j]
        tot = sum(w[i] for i in kept)
        if tot <= 0:
            exclusive = [
                i for i in range(num_t)
                if access[i][j] and sum(bool(value) for value in access[i]) == 1
            ]
            weighted_exclusive = [i for i in exclusive if w[i] > 0]
            cand = weighted_exclusive or [
                i for i in range(num_t) if access[i][j] and w[i] >= min_position
            ]
            if not cand:
                cand = exclusive or [i for i in range(num_t) if access[i][j]]
            cand.sort(key=lambda i: w[i], reverse=True)
            useful_lines = (
                num_t
                if min_position <= 0
                else max(1, int(np.ceil(float(b_ratios[j]) / min_position)))
            )
            if min_position <= 0:
                # Aucun plafond politique de 20 lignes lorsque le seuil global
                # est désactivé. La limite réelle sera celle des actions
                # entières lors de la discrétisation finale.
                limit = min(int(fallback_max_lines or useful_lines), useful_lines)
            else:
                limit = min(
                    int(Config.STARR_MAX_LINES_PER_BROKER),
                    int(fallback_max_lines or useful_lines),
                    useful_lines,
                )
            cand = cand[: max(1, limit)]
            tot_av = sum(w[i] for i in cand)
            if tot_av > 0:
                for i in cand:
                    W[i, j] = b_ratios[j] * w[i] / tot_av
            elif cand:
                share = b_ratios[j] / len(cand)
                for i in cand:
                    W[i, j] = share
            continue
        for i in kept:
            W[i, j] = b_ratios[j] * w[i] / tot  # budget redéployé sur les affectés
    return W


def ticker_standalone_scores(
    sim_rets, mean_daily, alpha: float, downside_weight: float
) -> np.ndarray:
    """Score STARR de chaque titre PRIS SEUL (une colonne de ``sim_rets`` = un
    portefeuille mono-titre), vectorisé. Sert à ordonner l'univers pour la
    population initiale du DE (sans réduire l'univers : tous les titres restent
    optimisables)."""
    sim = np.asarray(sim_rets)
    n_sim = sim.shape[0]
    k = max(1, int(round(alpha * n_sim)))
    tail = np.partition(sim, k - 1, axis=0)[:k]
    cvar = -tail.mean(axis=0, dtype=np.float64)
    downside = np.minimum(sim, 0.0).astype(np.float64)
    dd = np.sqrt(np.mean(downside**2, axis=0))
    # Forme SOUSTRACTIVE, comme l'objectif : un ratio est invariant d'echelle et
    # classait premier tout actif a risque minuscule (un ETF monetaire sortait
    # devant les actions), ce qui orientait deja mal la population initiale.
    risk = (cvar + downside_weight * dd) * np.sqrt(252.0)
    return np.asarray(mean_daily, dtype=float) * 252.0 - risk


def build_init_population(
    n: int,
    pop_size: int,
    rng: np.random.Generator,
    scores: np.ndarray,
    seed_idx: int | None,
    warm_starts: list | None = None,
    jitter: float = 0.02,
    is_etf: np.ndarray | None = None,
) -> np.ndarray:
    """Population initiale SPARSE pour le DE, [max(pop_size, lignes requises) × n].

    Le latin hypercube par défaut démarre avec ~n titres pondérés à la fois
    (STARR médiocre, malus de cardinalité dès que ça se concentre) et laisse
    scipy créer popsize×n individus. Ici la population est concentrée d'emblée :
    - 1 individu mono-titre ``seed_idx`` (ETF monde / meilleur standalone) ;
    - one-hots des 5 meilleurs scores standalone + top-20/top-40 équipondérés ;
    - ``warm_starts`` (points de départ imposés) + une copie bruitée à ``jitter``,
      sautée quand ``jitter=0`` — les élites de screening et les variantes kickées
      sont déjà diverses, les bruiter n'ajouterait rien ;
    - lignes de COUVERTURE : chaque titre apparaît dans au moins un individu —
      une coordonnée nulle dans TOUTE la population resterait nulle à jamais
      (mutation DE = a + F·(b−c)), ce qui réduirait l'univers de fait ;
    - le reste : portefeuilles aléatoires de quelques titres (5-40).
    """
    order = np.argsort(np.asarray(scores, dtype=float))[::-1]
    rows: list[np.ndarray] = []

    def one_hot(i: int) -> np.ndarray:
        v = np.zeros(n)
        v[i] = 1.0
        return v

    if seed_idx is not None:
        rows.append(one_hot(int(seed_idx)))
    for i in order[: min(5, n)]:
        rows.append(one_hot(int(i)))
    for top in (20, 40):
        m = min(top, n)
        v = np.zeros(n)
        v[order[:m]] = 1.0 / m
        rows.append(v)
    # Départs stratifiés par classe d'actifs. Les deux classes sont explorées,
    # mais aucune présence d'action n'est imposée au portefeuille finalement
    # retenu : l'objectif STARR reste seul juge.
    if is_etf is not None:
        flags = np.asarray(is_etf, dtype=bool).reshape(-1)
        if flags.size != n:
            raise ValueError("is_etf incompatible avec la taille de l'univers")
        for class_mask in (~flags, flags):
            class_order = [int(index) for index in order if class_mask[int(index)]]
            for top in (5, 10, 20):
                selected = class_order[: min(top, len(class_order))]
                if not selected:
                    continue
                v = np.zeros(n)
                v[selected] = 1.0 / len(selected)
                rows.append(v)
    for x in warm_starts or []:
        x = np.clip(np.asarray(x, dtype=float), 0.0, 1.0)
        rows.append(x)
        if jitter > 0:
            # Un bruit absolu sur les zéros ajoutait ~0,02 à la moitié des
            # milliers de titres absents : le voisin du champion devenait un
            # portefeuille dense sans rapport avec lui. Perturber les poids
            # présents proportionnellement préserve ce point de départ local.
            noisy = x * np.exp(rng.normal(0.0, jitter, n))
            noisy_total = float(noisy.sum())
            if noisy_total > 0:
                noisy *= float(x.sum()) / noisy_total
            rows.append(np.clip(noisy, 0.0, 1.0))
    # Couverture : permutation de l'univers découpée en paquets de ~25 titres.
    perm = rng.permutation(n)
    for start in range(0, n, 25):
        idx = perm[start : start + 25]
        v = np.zeros(n)
        v[idx] = rng.uniform(0.2, 1.0, len(idx))
        rows.append(v)
    # Complément aléatoire sparse jusqu'à pop_size (minimum scipy : 5 individus).
    max_pick = min(40, n)
    while len(rows) < max(pop_size, 5):
        m = (
            int(rng.integers(1, max_pick + 1))
            if max_pick < 5
            else int(rng.integers(5, max_pick + 1))
        )
        idx = rng.choice(n, size=m, replace=False)
        v = np.zeros(n)
        v[idx] = rng.uniform(0.2, 1.0, m)
        rows.append(v)
    return np.asarray(rows, dtype=float)


def build_random_sparse_population(
    n: int,
    population_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Construit des portefeuilles aléatoires concentrés, sans seed déterministe."""
    size = max(1, int(population_size))
    max_pick = min(40, n)
    rows = np.zeros((size, n), dtype=float)
    for row in rows:
        picks = (
            int(rng.integers(1, max_pick + 1))
            if max_pick < 5
            else int(rng.integers(5, max_pick + 1))
        )
        idx = rng.choice(n, size=picks, replace=False)
        row[idx] = rng.uniform(0.2, 1.0, picks)
    return rows


def refine_portfolio_weights(
    candidate: np.ndarray,
    objective,
    *,
    active_indices: np.ndarray | None = None,
    max_rounds: int = 12,
    initial_step: float = 0.05,
) -> tuple[np.ndarray, float]:
    """Descente locale vectorisée, avec transferts de capital entre lignes.

    Les transferts deux à deux conservent le budget : contrairement à une
    variation isolée, ils peuvent progresser le long d'un plafond actif. Chaque
    lot utilise exactement l'objectif et les contraintes de la recherche.
    Aucun candidat moins bon, invalide ou infaisable n'est retenu.
    """
    original = np.maximum(np.asarray(candidate, dtype=float).reshape(-1), 0.0)
    original_energy = float(np.asarray(objective(original[:, None]))[0])
    active = (
        np.flatnonzero(original > 1e-12)
        if active_indices is None
        else np.asarray(active_indices, dtype=int)
    )
    if active.size < 2 or max_rounds <= 0:
        return original.copy(), original_energy
    best = np.zeros_like(original)
    best[active] = original[active]
    if float(best.sum()) <= 1e-12:
        return original.copy(), original_energy
    best /= float(best.sum())
    best_energy = float(np.asarray(objective(best[:, None]))[0])
    # La projection sur le support déployé peut changer la répartition broker.
    # Garder aussi le point original comme garantie de non-régression.
    incumbent, incumbent_energy = original.copy(), original_energy
    if np.isfinite(best_energy) and best_energy < incumbent_energy:
        incumbent, incumbent_energy = best.copy(), best_energy
    step = max(float(initial_step), 1e-5)
    unsuccessful_rounds = 0
    for iteration in range(max(0, int(max_rounds))):
        count = len(active)
        trials = np.repeat(best[:, None], 4 * count, axis=1)
        columns = np.arange(count)
        trials[active, columns] += step
        trials[active, count + columns] = np.maximum(best[active] - step, 0.0)
        # Faire tourner les partenaires explore plusieurs échanges sans créer
        # un lot quadratique en nombre de lignes à chaque passage.
        partners = np.roll(active, 1 + iteration % (count - 1))
        for offset, donors, recipients in (
            (2 * count, active, partners),
            (3 * count, partners, active),
        ):
            transfer = np.minimum(best[donors], step)
            trials[donors, offset + columns] -= transfer
            trials[recipients, offset + columns] += transfer
        totals = trials.sum(axis=0)
        trials[:, totals > 1e-12] /= totals[totals > 1e-12]
        energies = np.asarray(objective(trials), dtype=float).reshape(-1)
        usable = np.isfinite(energies) & (energies < INVALID_OBJECTIVE_ENERGY)
        if usable.any():
            index = int(np.flatnonzero(usable)[np.argmin(energies[usable])])
            if float(energies[index]) < best_energy - 1e-10:
                best = trials[:, index].copy()
                best_energy = float(energies[index])
                if best_energy < incumbent_energy:
                    incumbent, incumbent_energy = best.copy(), best_energy
                unsuccessful_rounds = 0
                continue
        unsuccessful_rounds += 1
        # Une famille d'échanges peut être bloquée par un plafond alors qu'une
        # autre reste utile. Réduire le pas avant un tour complet de partenaires
        # le faisait tendre vers zéro sans avoir exploré ces directions.
        if unsuccessful_rounds < count - 1:
            continue
        unsuccessful_rounds = 0
        step *= 0.5
        if step < 1e-4:
            break
    return incumbent, incumbent_energy


class PositiveSeedNotFound(RuntimeError):
    """Aucun point de depart positif trouve dans le budget d'essais imparti."""


class InvalidOptimizationObjective(RuntimeError):
    """L'objectif numérique est invalide pour tous les portefeuilles testés."""


INVALID_OBJECTIVE_ENERGY = 1e6


def find_positive_random_seed(
    n: int,
    rng: np.random.Generator,
    objective,
    *,
    batch_size: int,
    max_batches: int,
    progress_cb=None,
    should_stop=None,
    feasible=None,
) -> tuple[np.ndarray, float, int]:
    """Cherche un portefeuille aléatoire ADMISSIBLE pour amorcer le DE.

    ``objective`` suit la convention de scipy et retourne une énergie à minimiser;
    le score affiché est donc ``-énergie``. ``feasible`` reçoit la même population
    et renvoie un masque booléen : ``True`` là où le candidat respecte TOUTES les
    contraintes (défensif, plafond par pays, cardinalité), c'est-à-dire là où la
    pénalité est nulle.

    Le critère d'admissibilité est la **pénalité nulle**, et non un score positif.
    Tant que l'objectif était le ratio ``rendement / risque``, « positif » voulait
    simplement dire « rendement > 0 » — presque toujours vrai, donc un garde-fou
    quasi gratuit. Depuis que le score mesure l'ÉCART AU BENCHMARK, « positif »
    voudrait dire « battre CW8.PA dès le tirage au sort » : ce serait exiger d'un
    point de départ qu'il résolve déjà le problème que le DE doit résoudre.

    L'échec (``PositiveSeedNotFound``) garde en revanche tout son sens : il signale
    qu'aucun portefeuille aléatoire ne respecte les contraintes look-through, ce
    qui est exactement le cas où l'appelant doit les relâcher.
    """
    maximum = max(1, int(max_batches))
    best_score = float("-inf")
    best_vector: np.ndarray | None = None
    for batch_num in range(1, maximum + 1):
        candidates = build_random_sparse_population(n, batch_size, rng)
        energies = np.asarray(objective(candidates.T), dtype=float).reshape(-1)
        constraint_ok = np.ones(len(energies), dtype=bool)
        if feasible is not None:
            constraint_ok &= np.asarray(
                feasible(candidates.T), dtype=bool
            ).reshape(-1)
        objective_ok = (
            np.isfinite(energies)
            & (energies < INVALID_OBJECTIVE_ENERGY)
        )
        # 1e6 est la sentinelle explicite de starr.py pour poids nuls ou
        # calcul non fini. Elle ne doit jamais être acceptée comme un véritable
        # score (-1e6 côté interface), sinon chaque seed « converge » sur la
        # même erreur numérique et la boucle continue jusqu'à l'arrêt manuel.
        if constraint_ok.any() and not objective_ok[constraint_ok].any():
            sample = energies[constraint_ok]
            raise InvalidOptimizationObjective(
                "Tous les portefeuilles admissibles ont un objectif numérique "
                "invalide "
                f"(énergie min={float(np.nanmin(sample)):.6g}, "
                f"max={float(np.nanmax(sample)):.6g}, lot={batch_num})."
            )
        ok = constraint_ok & objective_ok
        admissible = np.flatnonzero(ok)
        if admissible.size:
            idx = int(admissible[np.argmin(energies[admissible])])
            score = -float(energies[idx])
            if score > best_score:
                best_score = score
                best_vector = candidates[idx].copy()
        if progress_cb is not None:
            progress_cb(batch_num, maximum, best_score if np.isfinite(best_score) else None)
        if best_vector is not None:
            return best_vector, best_score, batch_num
        if should_stop is not None and should_stop():
            raise RuntimeError("Optimisation arrêtée pendant la recherche initiale positive.")
        # Le job est exécuté dans le thread de fond FastAPI : laisser les routes
        # HTTP/SSE reprendre le GIL entre deux gros lots vectorisés.
        time.sleep(max(0.0, float(Config.STARR_COOPERATIVE_YIELD_SECONDS)))

    tested = maximum * max(1, int(batch_size))
    raise PositiveSeedNotFound(
        "Aucun portefeuille admissible trouvé après "
        f"{tested:,} essais aléatoires. Vérifiez les rendements et les contraintes."
    )


def relative_gain(current_energy: float, reference_energy: float) -> float:
    """De combien de POUR CENT le score s'est-il amélioré ? Décision pure.

    Les énergies sont des scores changés de signe. Le gain est rapporté au score
    de référence : passer de 4 à 6 vaut +50 %, et passer de −20 à −10 vaut +50 %
    aussi — ce qui compte pour un score négatif, cas réel de cet optimiseur.

    Rend 0 lorsqu'il n'existe aucune référence (première génération évaluée) :
    sans point de comparaison, un gain « infini » ferait plonger la température
    dès le premier tour, avant même que la recherche ait commencé.
    """
    reference = float(reference_energy)
    if not math.isfinite(reference):
        return 0.0
    score_reference = -reference
    score_courant = -float(current_energy)
    denominateur = max(abs(score_reference), 1e-6)
    return max(0.0, (score_courant - score_reference) / denominateur)


def next_temperature(
    temperature: float,
    *,
    gain: float,
    stagnation_streak: int,
    stop_requested: bool,
    heating: float | None = None,
    stop_cooling: float | None = None,
    improvement_t_max: float | None = None,
    t_min: float | None = None,
    t_max: float | None = None,
) -> float:
    """Loi de température du recuit adaptatif. Décision pure, sans solveur.

    - une amélioration REFROIDIT, À LA MESURE DE CE QU'ELLE APPORTE, et ramène
      au plus la température au plafond d'exploitation ``improvement_t_max`` ;
    - une génération sans amélioration RÉCHAUFFE, immédiatement : il n'y a AUCUN
      délai de carence. Une génération qui ne progresse pas, c'est déjà de la
      stagnation ;
    - un arrêt demandé GÈLE le réchauffage et force le refroidissement, pour que
      le run se termine sur un optimum abouti plutôt que sur une interruption.

    C'est cette dernière règle qui garantit qu'« arrêter » ne veut pas dire
    « couper au milieu d'une exploration ». Son refroidissement est le seul qui
    reste à taux FIXE : après un arrêt il n'y a plus forcément de gain, et une
    décroissance proportionnelle à un gain nul ne convergerait jamais.

    Le refroidissement appliquait auparavant un facteur unique (×0,90) à TOUTE
    amélioration jugée réelle. Une miette de 0,1 % coûtait donc autant qu'un gain
    massif, et éteignait l'exploration sans rien avoir rapporté.

    Le réchauffage est linéaire : chaque génération sans progrès ajoute une
    petite fraction fixe de la plage thermique. L'ancienne exponentielle
    atteignait T=1 trop vite puis produisait surtout des candidats infaisables.

    Le plancher ``t_min`` est volontairement NON NUL : le réchauffage étant
    multiplicatif, une température tombée à zéro ne pourrait plus jamais remonter
    et figerait définitivement la recherche.
    """
    heating = float(Config.STARR_DE_HEATING if heating is None else heating)
    freinage = float(
        Config.STARR_DE_STOP_COOLING if stop_cooling is None else stop_cooling
    )
    plafond_gain = float(
        Config.STARR_DE_IMPROVEMENT_T_MAX
        if improvement_t_max is None else improvement_t_max
    )
    low = float(Config.STARR_DE_T_MIN if t_min is None else t_min)
    high = float(Config.STARR_DE_T_MAX if t_max is None else t_max)
    value = float(temperature)
    if stop_requested:
        # Plus JAMAIS de réchauffage une fois l'arrêt demandé.
        return max(low, value * freinage)
    progres = max(0.0, float(gain))
    if progres > 0.0:
        if progres >= 1.0:
            # Le score a au moins doublé : plus rien à explorer pour l'instant,
            # on exploite au maximum.
            return low
        # Même un petit gain SIGNIFICATIF mérite une phase d'affinage. Le gain
        # reste proportionnel lorsqu'il impose un refroidissement plus fort.
        return max(low, min(value * (1.0 - progres), plafond_gain, high))
    streak = max(0, int(stagnation_streak))
    if streak >= 1:
        step = max(heating, 0.0) * max(high - low, 0.0)
        return min(high, value + step)
    return min(max(value, low), high)


def is_real_improvement(
    current_energy: float,
    reference_energy: float,
    *,
    absolute: float | None = None,
    relative: float | None = None,
) -> bool:
    """Le gain compte-t-il comme une VRAIE amélioration ? Décision pure.

    Le DE est ÉLITISTE : son meilleur individu grappille des miettes numériques
    presque à chaque génération. Avec un seuil purement ABSOLU (1e-6) sur un
    score de l'ordre de quelques points, chacune de ces miettes comptait comme
    un progrès — elle refroidissait la température ET réarmait la fenêtre de
    stagnation. La stagnation devenait donc structurellement indétectable, le
    réchauffage ne se déclenchait jamais et la température restait collée à son
    plancher (bande de mutation écrasée = exploitation pure, plus aucune
    amélioration). Le seuil est désormais PROPORTIONNEL au score, avec un
    plancher absolu pour les scores proches de zéro.
    """
    floor = max(0.0, float(Config.STARR_DE_MIN_IMPROVEMENT
                           if absolute is None else absolute))
    ratio = max(0.0, float(Config.STARR_DE_MIN_IMPROVEMENT_REL
                           if relative is None else relative))
    reference = float(reference_energy)
    if not math.isfinite(reference):
        # Aucune génération évaluée : la première est toujours un progrès.
        return True
    seuil = max(floor, ratio * abs(reference))
    return float(current_energy) < reference - seuil


def next_hot_plateau_streak(
    previous: int,
    *,
    improved: bool,
    temperature: float,
    t_max: float | None = None,
) -> int:
    """Compte uniquement la stagnation consecutive a temperature maximale."""
    maximum = float(Config.STARR_DE_T_MAX if t_max is None else t_max)
    if improved or float(temperature) < maximum - 1e-9:
        return 0
    return max(0, int(previous)) + 1


def accept_new_anchor(
    anchor_score: float,
    candidate_score: float,
    temperature: float,
    draw: float,
    *,
    scale: float | None = None,
) -> bool:
    """Acceptation de Metropolis ENTRE BASSINS (basin hopping).

    Le DE est élitiste : il n'accepte jamais une solution moins bonne, et le
    réécrire serait hors de proportion. La température agit donc un niveau plus
    haut — sur le point d'ANCRAGE d'où partent les perturbations, pas sur la
    population. L'incumbent livré, lui, ne régresse jamais.

    Sans cette dérive, toutes les perturbations resteraient clouées au même
    optimum et referaient indéfiniment le même trajet : c'est la cause du
    cyclage. ``draw`` est un tirage uniforme dans [0, 1[, fourni par l'appelant
    pour que la décision reste pure et reproductible.
    """
    if candidate_score > anchor_score:
        return True
    k = max(float(Config.STARR_DE_ACCEPT_SCALE if scale is None else scale), 1e-12)
    t = max(float(temperature), 0.0)
    if t <= 0.0:
        return False  # froid : descente stricte
    # candidate_score <= anchor_score, donc l'exposant est <= 0.
    return float(draw) < math.exp((float(candidate_score) - float(anchor_score)) / (t * k))


def support_signature(weights, min_position: float) -> frozenset:
    """Ensemble des lignes OUVERTES : l'identité discrète d'un portefeuille.

    L'espace des poids est continu — deux vecteurs identiques n'apparaissent
    jamais, une mémoire de vecteurs n'aurait donc aucun succès. Ce qui se répète
    d'un optimum local à l'autre, c'est le SUPPORT. C'est lui qu'on mémorise
    pour ne pas réexplorer deux fois le même voisinage.

    À ne PAS utiliser comme clé de cache de score : deux portefeuilles de mêmes
    lignes mais de pondérations différentes n'ont pas le même score.
    """
    values = np.asarray(weights, dtype=float)
    seuil = max(float(min_position), 0.0)
    return frozenset(np.flatnonzero(values > seuil).tolist())


def reheat_amplitude(temperature: float, open_lines: int) -> int:
    """Lignes remaniées lors d'un réchauffage : de UNE à TOUT le portefeuille.

    C'est ici que la température devient un geste concret. L'échelle est celle du
    portefeuille lui-même, pas une constante : à T=1 le support entier est remis
    en jeu — le portefeuille rendu par `kick_portfolio` n'a alors plus une seule
    ligne commune avec celui d'où il part, il est tiré au hasard. À T→0, une
    seule ligne bouge : le plus petit pas qui existe.

    L'amplitude était auparavant bornée par deux CONSTANTES (2 et 6 lignes).
    Sur un portefeuille d'une quarantaine de lignes, une température au plafond
    ne déplaçait donc que 15 % du support — la température montait, le
    portefeuille ne bougeait pas.
    """
    total = max(0, int(open_lines))
    if total == 0:
        return 0
    t = min(max(float(temperature), 0.0), 1.0)
    return max(1, int(round(t * total)))


def sample_kick_sizes(rng: np.random.Generator, ceiling: int) -> tuple[int, int]:
    """Combien de lignes on FERME et combien on OUVRE — deux tirages SÉPARÉS.

    Ces deux nombres recevaient la même valeur, si bien que la cardinalité du
    portefeuille était un invariant absolu du remaniement : un portefeuille à 11
    lignes restait à 11 lignes indéfiniment, quelle que soit la température. Le
    kick ne pouvait qu'échanger des titres un pour un, jamais changer la forme du
    portefeuille — on ne pouvait pas en retirer 10 pour en ajouter 15.

    Tirés indépendamment dans [0, ceiling], avec la seule garantie qu'il se passe
    QUELQUE CHOSE : une variante identique à son point de départ ne sert à rien.
    """
    high = max(0, int(ceiling))
    if high <= 0:
        return 0, 1
    n_drop = int(rng.integers(0, high + 1))
    n_add = int(rng.integers(0, high + 1))
    if n_drop == 0 and n_add == 0:
        n_add = 1
    return n_drop, n_add


def sample_multiscale_kick_sizes(
    rng: np.random.Generator,
    active_lines: int,
    ceiling: int,
) -> tuple[str, int, int]:
    """Tire un voisinage local, moyen, large ou entierement neuf.

    Contrairement au tirage uniforme historique, cette loi reserve explicitement
    une part du budget aux changements de structure. ``n_drop`` et ``n_add``
    restent independants : une reconstruction peut donc retirer quatre lignes et
    en ajouter neuf, ou changer la cardinalite dans l'autre sens.
    """
    active = max(0, int(active_lines))
    limit = max(1, int(ceiling))
    draw = float(rng.random())
    if draw < 0.35:
        mode = "local"
        drop_hi = max(1, min(2, active or 1))
        add_hi = max(1, min(2, limit))
        n_drop = int(rng.integers(1, drop_hi + 1)) if active else 0
        n_add = int(rng.integers(1, add_hi + 1))
    elif draw < 0.70:
        mode = "medium"
        lo = max(1, int(math.ceil(0.20 * max(active, 1))))
        hi = max(lo, int(math.ceil(0.50 * max(active, 1))))
        n_drop = min(active, int(rng.integers(lo, hi + 1)))
        add_lo = max(1, int(math.floor(0.75 * max(n_drop, 1))))
        add_hi = max(add_lo, min(limit, int(math.ceil(1.75 * max(n_drop, 1)))))
        n_add = int(rng.integers(add_lo, add_hi + 1))
    elif draw < 0.90:
        mode = "large"
        lo = max(1, int(math.ceil(0.60 * max(active, 1))))
        n_drop = min(active, int(rng.integers(lo, max(lo, active) + 1)))
        n_add = int(rng.integers(1, limit + 1))
    else:
        mode = "global"
        n_drop = active
        n_add = int(rng.integers(1, limit + 1))
    if n_drop == 0 and n_add == 0:
        n_add = 1
    return mode, n_drop, n_add


def temperature_child_kick_sizes(
    rng: np.random.Generator,
    *,
    active_lines: int,
    line_budget: int,
    temperature: float,
    child_rank: int,
    children_per_parent: int,
) -> tuple[str, int, int]:
    """Amplitude stratifiée d'un enfant, entièrement pilotée par T.

    Les huit enfants d'une lignée balaient toute l'amplitude permise par T : le
    premier est la plus petite perturbation de cette lignée, le dernier peut
    reconstruire tout son support à T=1. L'exploitation très fine du meilleur
    global est produite séparément par ``local_child_kick_sizes`` afin de ne pas
    consommer la moitié des enfants de CHACUNE des douze lignées.
    """
    active = max(0, int(active_lines))
    budget = max(1, int(line_budget))
    total = max(1, int(children_per_parent))
    rank = min(max(int(child_rank), 0), total - 1)
    t = min(max(float(temperature), 0.0), 1.0)
    fraction = t * float(rank + 1) / float(total)
    n_drop = min(active, max(1 if active else 0, int(round(fraction * active))))
    reference = max(n_drop, 1)
    add_low = max(1, int(math.floor(0.60 * reference)))
    add_high = max(add_low, min(budget, int(math.ceil(1.60 * reference))))
    n_add = int(rng.integers(add_low, add_high + 1))
    mode = (
        "local" if fraction <= 0.20
        else "medium" if fraction <= 0.50
        else "large" if fraction < 0.90
        else "global"
    )
    return mode, n_drop, n_add


def local_child_kick_sizes(
    rng: np.random.Generator,
    *,
    active_lines: int,
    line_budget: int,
    child_rank: int,
    local_children: int,
) -> tuple[str, int, int]:
    """Voisin fin du meilleur global : une ou deux lignes seulement.

    Dans le cas nominal de quatre enfants, les amplitudes sont 1, 1, 2, 2.
    Cette poche d'exploitation est constante même à T=1, mais n'existe qu'une
    fois par génération et non une fois par parent.
    """
    active = max(0, int(active_lines))
    budget = max(1, int(line_budget))
    total = max(1, int(local_children))
    rank = min(max(int(child_rank), 0), total - 1)
    n_drop = min(active, 1 + (2 * rank // total)) if active else 0
    reference = max(n_drop, 1)
    n_add = int(rng.integers(1, min(budget, reference + 1) + 1))
    return "local", n_drop, n_add


def select_unique_support_candidates(
    candidates: list[tuple[float, np.ndarray]],
    *,
    count: int,
    min_position: float,
    min_distance: float = 0.0,
    excluded_signatures: set[frozenset] | None = None,
) -> list[tuple[float, np.ndarray]]:
    """Garde les meilleurs candidats sans dupliquer un même portefeuille.

    Une première passe impose aussi une distance de Jaccard minimale. Si elle ne
    remplit pas les places, une seconde passe relâche uniquement cette distance,
    jamais l'unicité exacte du support.
    """
    wanted = max(0, int(count))
    if wanted == 0:
        return []
    ordered = sorted(
        (
            (float(energy), np.asarray(vector, dtype=float).copy())
            for energy, vector in candidates
            if math.isfinite(float(energy))
        ),
        key=lambda item: item[0],
    )
    blocked = set(excluded_signatures or set())
    selected: list[tuple[float, np.ndarray]] = []
    signatures: set[frozenset] = set(blocked)
    distance = min(max(float(min_distance), 0.0), 1.0)

    def add_pass(require_distance: bool) -> None:
        for energy, vector in ordered:
            if len(selected) >= wanted:
                return
            signature = support_signature(vector, min_position)
            if not signature or signature in signatures:
                continue
            if require_distance and distance > 0 and selected:
                if any(
                    support_jaccard_distance(vector, other, min_position) < distance
                    for _other_energy, other in selected
                ):
                    continue
            selected.append((energy, vector.copy()))
            signatures.add(signature)

    add_pass(require_distance=True)
    add_pass(require_distance=False)
    return selected


def select_novel_support_candidates(
    candidates: list[tuple[float, np.ndarray]],
    *,
    count: int,
    min_position: float,
    anchors: list[np.ndarray] | None = None,
    excluded_signatures: set[frozenset] | None = None,
) -> list[tuple[float, np.ndarray]]:
    """Sélection gloutonne par nouveauté, le score ne départageant que les ex æquo."""
    remaining = [
        (float(energy), np.asarray(vector, dtype=float).copy())
        for energy, vector in candidates
        if math.isfinite(float(energy))
    ]
    selected: list[tuple[float, np.ndarray]] = []
    references = [np.asarray(value, dtype=float) for value in (anchors or [])]
    blocked = set(excluded_signatures or set())
    while remaining and len(selected) < max(0, int(count)):
        eligible_indices = [
            index for index, item in enumerate(remaining)
            if support_signature(item[1], min_position) not in blocked
            and support_signature(item[1], min_position)
        ]
        if not eligible_indices:
            break

        def novelty_key(item: tuple[float, np.ndarray]) -> tuple[float, float]:
            energy, vector = item
            distance = min(
                (
                    support_jaccard_distance(vector, reference, min_position)
                    for reference in references
                ),
                default=1.0,
            )
            return distance, -energy

        chosen_index = max(eligible_indices, key=lambda index: novelty_key(remaining[index]))
        chosen = remaining.pop(chosen_index)
        selected.append(chosen)
        references.append(chosen[1])
        blocked.add(support_signature(chosen[1], min_position))
    return selected


def exposure_cap_feasible(
    exposure_matrix: np.ndarray,
    deployed: np.ndarray,
    maximum: float,
) -> np.ndarray:
    """Teste un plafond de poids sur chaque colonne d'une matrice look-through."""
    weights = np.asarray(deployed, dtype=float)
    if weights.ndim == 1:
        weights = weights[:, None]
    matrix = np.asarray(exposure_matrix, dtype=float)
    if not matrix.size:
        return np.ones(weights.shape[1], dtype=bool)
    return np.all((matrix.T @ weights) <= float(maximum) + 1e-9, axis=0)


def support_jaccard_distance(left, right, min_position: float = 0.0) -> float:
    """Distance de Jaccard entre deux supports (0 identique, 1 disjoint)."""
    a = support_signature(left, min_position)
    b = support_signature(right, min_position)
    union = a | b
    return 0.0 if not union else 1.0 - len(a & b) / len(union)


def update_diverse_support_archive(
    archive: list[tuple[float, np.ndarray]],
    candidate,
    energy: float,
    *,
    min_position: float,
    max_size: int,
    min_distance: float,
) -> list[tuple[float, np.ndarray]]:
    """Insere un candidat sans laisser des clones remplir l'archive elite."""
    if not math.isfinite(float(energy)) or max_size <= 0:
        return list(archive)
    out = [(float(e), np.asarray(x, dtype=float).copy()) for e, x in archive]
    vector = np.asarray(candidate, dtype=float).copy()
    threshold = min(max(float(min_distance), 0.0), 1.0)
    close = [
        i for i, (_e, existing) in enumerate(out)
        if support_jaccard_distance(existing, vector, min_position) < threshold
    ]
    if close:
        closest = min(
            close,
            key=lambda i: support_jaccard_distance(out[i][1], vector, min_position),
        )
        if float(energy) < out[closest][0]:
            out[closest] = (float(energy), vector)
    else:
        out.append((float(energy), vector))
    out.sort(key=lambda item: item[0])
    return out[: max(1, int(max_size))]


def _replacement_line_weights(
    remaining: np.ndarray,
    original_total: float,
    additions: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Finance les entrées avec le poids libéré, à l'échelle du parent.

    Une entrée à 0,2–1,0 après la sortie d'une ligne de 2 % remaniait presque
    tout le portefeuille, même lors d'un mouvement annoncé comme local.
    Sans sortie, les lignes existantes financent une part proportionnelle au
    nombre d'entrées ; leurs rapports de poids sont conservés.
    """
    if additions <= 0:
        return np.empty(0, dtype=float)
    remaining_total = float(remaining.sum())
    released = max(0.0, float(original_total) - remaining_total)
    if released <= 1e-12:
        if remaining_total > 1e-12:
            released = remaining_total * additions / (
                int(np.count_nonzero(remaining > 0)) + additions
            )
            remaining *= (remaining_total - released) / remaining_total
        else:
            released = 1.0
    weights = rng.uniform(0.2, 1.0, additions)
    return released * weights / float(weights.sum())


def guided_kick_portfolio(
    x,
    rng: np.random.Generator,
    *,
    n_drop: int,
    n_add: int,
    standalone_scores,
    correlation,
    guidance_weight: float = 0.55,
    eligible_mask=None,
    selection_noise: float = 0.08,
) -> np.ndarray:
    """Detruit un support puis le reconstruit avec rendement ET nouveaute.

    Les ajouts ne sont plus uniformes dans tout l'univers. A chaque pas, le
    candidat combine son score standalone et sa correlation positive maximale
    avec les lignes deja conservees. ``eligible_mask`` permet au déploiement de
    fournir les seuls titres accessibles chez un courtier actif. Un petit bruit
    permet a deux variantes de ne pas reconstruire exactement le meme support.
    """
    out = np.clip(np.asarray(x, dtype=float).copy(), 0.0, 1.0)
    scores = np.asarray(standalone_scores, dtype=float).reshape(-1)
    corr = np.asarray(correlation, dtype=float)
    if scores.size != out.size or corr.shape != (out.size, out.size):
        raise ValueError("scores/correlation incompatibles avec le portefeuille")
    if eligible_mask is None:
        eligible = np.ones(out.size, dtype=bool)
    else:
        eligible = np.asarray(eligible_mask, dtype=bool).reshape(-1)
        if eligible.size != out.size:
            raise ValueError("eligible_mask incompatible avec le portefeuille")
    active = np.flatnonzero(out > 0.0)
    # Une ligne retirée ne doit pas être immédiatement choisie comme entrée.
    available = (out <= 0.0) & eligible
    original_total = float(out.sum())
    drop = min(max(0, int(n_drop)), active.size)
    if drop:
        # Conserver plus souvent les lignes fortes, sans les rendre intouchables.
        weights = out[active]
        weakness = np.maximum(weights.max(initial=0.0) - weights, 0.0) + 0.05
        weakness /= weakness.sum()
        out[rng.choice(active, size=drop, replace=False, p=weakness)] = 0.0

    add = min(max(0, int(n_add)), int(np.count_nonzero(available)))
    entry_weights = _replacement_line_weights(out, original_total, add, rng)

    finite = scores[np.isfinite(scores)]
    lo = float(np.min(finite)) if finite.size else 0.0
    hi = float(np.max(finite)) if finite.size else 0.0
    quality = np.nan_to_num((scores - lo) / max(hi - lo, 1e-12), nan=0.0)
    blend = min(max(float(guidance_weight), 0.0), 1.0)
    for entry_weight in entry_weights:
        inactive = np.flatnonzero(available)
        kept = np.flatnonzero(out > 0.0)
        if kept.size:
            # Corrélation au portefeuille global plutôt qu'à une seule ligne.
            # Les corrélations négatives sont traitées comme une
            # diversification complète. Les rendements actions et ETF sont
            # déjà exprimés dans la même devise en amont.
            kept_weights = out[kept]
            kept_weights = kept_weights / max(float(kept_weights.sum()), 1e-12)
            portfolio_corr = corr[np.ix_(inactive, kept)] @ kept_weights
            redundancy = np.clip(portfolio_corr, 0.0, 1.0)
        else:
            redundancy = np.zeros(inactive.size, dtype=float)
        merit = blend * quality[inactive] + (1.0 - blend) * (1.0 - redundancy)
        noise = max(float(selection_noise), 0.0)
        if noise > 0.0:
            merit += rng.uniform(0.0, noise, inactive.size)
        chosen = int(inactive[int(np.argmax(merit))])
        out[chosen] = float(entry_weight)
        available[chosen] = False
    # Les préférences DE restent dans [0, 1], même si plusieurs grosses lignes
    # ont été regroupées. Cette homothétie ne change pas leur allocation.
    out /= max(1.0, float(out.max(initial=0.0)))
    return out


def geography_guided_child(
    x,
    rng: np.random.Generator,
    *,
    sector_matrix,
    country_matrix,
    standalone_scores,
    correlation,
    medium_exposure: float = 0.05,
    large_exposure: float = 0.10,
    temperature: float = 0.5,
    joint_matrix=None,
    eligible_mask=None,
) -> np.ndarray:
    """Ajoute un pays réellement nouveau au secteur matériel le plus concentré.

    Le mouvement est financé en réduisant la ligne active qui contribue le plus
    au couple secteur × pays dominant. Les ajouts sont limités à
    ``eligible_mask`` lorsqu'il est fourni. Il ne cherche pas à augmenter le
    nombre de lignes pour lui-même : si aucun candidat inactif n'améliore la
    diversité, le portefeuille est rendu inchangé.
    """
    out = np.clip(np.asarray(x, dtype=float).copy(), 0.0, 1.0)
    sectors = np.asarray(sector_matrix, dtype=float)
    countries = np.asarray(country_matrix, dtype=float)
    scores = np.asarray(standalone_scores, dtype=float).reshape(-1)
    corr = np.asarray(correlation, dtype=float)
    joint = None if joint_matrix is None else np.asarray(joint_matrix, dtype=float)
    n = out.size
    if eligible_mask is None:
        eligible = np.ones(n, dtype=bool)
    else:
        eligible = np.asarray(eligible_mask, dtype=bool).reshape(-1)
        if eligible.size != n:
            raise ValueError("eligible_mask incompatible avec le portefeuille")
    if (
        sectors.ndim != 2 or sectors.shape[0] != n
        or countries.ndim != 2 or countries.shape[0] != n
        or scores.size != n or corr.shape != (n, n)
        or (
            joint is not None
            and joint.shape != (n, sectors.shape[1], countries.shape[1])
        )
    ):
        raise ValueError("matrices incompatibles avec le portefeuille")
    total = float(out.sum())
    if total <= 1e-12 or not sectors.size or not countries.size:
        return out
    weights = out / total
    medium = max(float(medium_exposure), 0.0)
    large = max(float(large_exposure), medium)
    choices: list[tuple[float, int, np.ndarray, float]] = []
    for sector_index in range(sectors.shape[1]):
        buckets = (
            joint[:, sector_index, :].T @ weights
            if joint is not None
            else countries.T @ (weights * sectors[:, sector_index])
        )
        exposure = float(buckets.sum())
        target = 3.0 if exposure >= large else (2.0 if exposure >= medium else 0.0)
        if target <= 0 or exposure <= 1e-12:
            continue
        shares = buckets / exposure
        effective = 1.0 / max(float(np.sum(shares * shares)), 1e-12)
        deficit = max(target - effective, 0.0) / target
        if deficit > 1e-12:
            choices.append((exposure * deficit, sector_index, shares, target))
    if not choices:
        return out
    _priority, sector_index, country_shares, _target = max(choices, key=lambda x: x[0])
    inactive = np.flatnonzero((out <= 1e-12) & eligible)
    if not inactive.size:
        return out
    if joint is not None:
        candidate_buckets = joint[inactive, sector_index, :]
        sector_fit = candidate_buckets.sum(axis=1)
        normalized_candidates = candidate_buckets / np.maximum(
            sector_fit[:, None], 1e-12
        )
        novelty = 1.0 - normalized_candidates @ country_shares
    else:
        novelty = 1.0 - countries[inactive] @ country_shares
        sector_fit = sectors[inactive, sector_index]
    active = np.flatnonzero(out > 1e-12)
    redundancy = (
        np.maximum(0.0, np.max(corr[np.ix_(inactive, active)], axis=1))
        if active.size else np.zeros(inactive.size)
    )
    finite = scores[np.isfinite(scores)]
    lo = float(finite.min()) if finite.size else 0.0
    hi = float(finite.max()) if finite.size else 0.0
    quality = np.nan_to_num((scores[inactive] - lo) / max(hi - lo, 1e-12), nan=0.0)
    merit = sector_fit * np.maximum(novelty, 0.0)
    merit *= 0.55 + 0.25 * quality + 0.20 * (1.0 - redundancy)
    merit += rng.uniform(0.0, 1e-6, inactive.size)
    chosen_at = int(np.argmax(merit))
    if float(merit[chosen_at]) <= 1e-9:
        return out
    chosen = int(inactive[chosen_at])

    if joint is not None:
        donor_merit = out * (joint[:, sector_index, :] @ country_shares)
    else:
        dominant_country_affinity = countries @ country_shares
        donor_merit = out * sectors[:, sector_index] * dominant_country_affinity
    donor = int(np.argmax(donor_merit))
    if donor_merit[donor] <= 1e-12:
        return out
    t = min(max(float(temperature), 0.0), 1.0)
    transfer_fraction = 0.20 + 0.20 * t
    transfer = max(float(out[donor]) * transfer_fraction, 1e-4)
    transfer = min(transfer, float(out[donor]) * 0.75)
    out[donor] = max(0.0, out[donor] - transfer)
    out[chosen] = min(1.0, out[chosen] + transfer)
    return out


def kick_line_budget(
    malus_threshold: int,
    economic_capacity: int,
    *,
    factor: float | None = None,
) -> int:
    """Combien de lignes un kick peut OUVRIR — plus que le portefeuille n'en garde.

    Ce plafond valait le SEUIL DU MALUS de cardinalité, alors que la troncature
    réelle du déploiement est la CAPACITÉ ÉCONOMIQUE (23 contre 100 sur un cas
    réel). Le kick ne pouvait donc jamais ouvrir plus de lignes que le
    portefeuille final n'en garde : aucun candidat en surplus ne se disputait les
    places, et le tri revenait au tirage aléatoire plutôt qu'à l'objectif.

    En ouvrant davantage, on met des titres en COMPÉTITION. Le nombre de lignes
    retenues n'est jamais imposé : la discrétisation finale élimine uniquement
    les lignes sous le prix d'une action achetable ; pour T212, le pie conserve
    sa granularité de 1 % local. Aucun malus supplémentaire de cardinalité
    n'est appliqué.

    Deux bornes : le facteur limite la taille d'une perturbation, et la capacité
    économique reste la limite physique du capital continu.
    """
    seuil = max(0, int(malus_threshold))
    capacite = max(0, int(economic_capacity))
    coefficient = float(
        Config.STARR_DE_KICK_LINES_FACTOR if factor is None else factor
    )
    elargi = int(round(max(0.0, coefficient) * seuil))
    if capacite > 0:
        elargi = min(elargi, capacite)
    return max(1, elargi)


def reheat_quota(
    temperature: float,
    members: int,
    *,
    max_share: float | None = None,
) -> int:
    """Individus remplacés lors d'un réchauffage, proportionnellement à T.

    Une part de la population n'est JAMAIS remplacée. C'est ce qui distingue une
    secousse d'une destruction : remplacer 100 % des individus ne laisse au DE
    qu'UNE génération de croisement avant que tout soit jeté, il ne converge donc
    jamais — et un portefeuille de 23 lignes tirées au hasard parmi des milliers
    de candidats ne bat jamais un optimum affiné. Beaucoup de mouvement, presque
    aucun progrès.

    Mesuré sur 400 générations (banc de 300 titres, population 120) :

        plafond   score    améliorations après T=1   supports distincts
          100 %   8,6502                         6                    4
           70 %   9,3936                        15                   12
           50 %   9,3656                        14                   11
           25 %   9,0349                        25                   15

    Avec un plafond, une partie de la population continue de converger pendant
    que le reste est renouvelé, et le DE CROISE les deux : un tirage aléatoire
    peut transmettre une ligne intéressante sans imposer ses vingt autres. C'est
    par là qu'un nouveau ticker entre réellement au portefeuille.

    Effet de bord utile : les cibles étant les PIRES individus d'abord,
    l'incumbent (index 0) n'est atteint que si le quota couvre tout le monde. Un
    plafond strictement inférieur à 1 le protège donc sans aucun code dédié.
    """
    total = max(0, int(members))
    if total == 0:
        return 0
    part = float(
        Config.STARR_DE_MAX_REHEAT_SHARE if max_share is None else max_share
    )
    part = min(max(part, 0.0), 1.0)
    t = min(max(float(temperature), 0.0), 1.0)
    plafond = max(1, int(round(part * total)))
    return max(1, min(total, plafond, int(round(t * total))))


# Il n'existe VOLONTAIREMENT plus de « détente après refonte ». Une fonction
# ramenait la température à T0 dès qu'une refonte totale avait eu lieu, sans
# qu'aucun progrès ne l'ait justifié. Mesuré sur un run réel, cela produisait une
# refonte complète toutes les 18 générations : la remise à zéro artificielle
# interrompait l'évolution dictée par les gains et la stagnation, donc le solveur
# ne redescendait jamais naturellement dans le bassin qu'il venait d'ouvrir.
#
# La loi de température prévoit déjà tout : elle descend quand le score progresse
# (proportionnellement au gain) et monte quand il stagne. Un second mécanisme qui
# la court-circuite ne pouvait que la contredire. Cf. `next_temperature`.


def sample_elite_seeds(
    n: int,
    rng: np.random.Generator,
    objective,
    *,
    batch_size: int,
    max_batches: int,
    n_elites: int,
    feasible=None,
    should_stop=None,
) -> list[np.ndarray]:
    """Screening élitiste : les ``n_elites`` meilleurs portefeuilles aléatoires.

    Généralisation de ``find_positive_random_seed``, qui s'arrête au PREMIER
    candidat admissible : ici on continue à tirer et on garde une élite.

    Le seuil d'acceptation est le **pire élite courant**, c'est-à-dire un quantile
    du lot. Un seuil absolu (« 80 % du score maximal ») serait inapplicable : le
    score est un écart en points de % annuels au benchmark, sans borne supérieure,
    et exiger d'un tirage au sort qu'il approche le meilleur connu sur ~18 000
    dimensions ferait tourner la boucle à vide (même raison que celle documentée
    dans ``find_positive_random_seed``). Le nombre de lots est borné : la fonction
    rend ce qu'elle a trouvé, quitte à rendre moins que ``n_elites``, voire rien.

    Retourne les vecteurs triés par énergie croissante (meilleur en tête).
    """
    maximum = max(1, int(max_batches))
    wanted = max(1, int(n_elites))
    elites: list[tuple[float, np.ndarray]] = []
    for _ in range(maximum):
        candidates = build_random_sparse_population(n, batch_size, rng)
        energies = np.asarray(objective(candidates.T), dtype=float).reshape(-1)
        ok = np.isfinite(energies) & (energies < INVALID_OBJECTIVE_ENERGY)
        # La sentinelle 1e6 marque un objectif non calculable (poids nuls, valeur
        # non finie) : elle ne doit JAMAIS entrer dans les élites, sinon toutes
        # les seeds froides repartiraient de la même erreur numérique.
        if feasible is not None:
            ok &= np.asarray(feasible(candidates.T), dtype=bool).reshape(-1)
        for idx in np.flatnonzero(ok):
            elites.append((float(energies[idx]), candidates[idx].copy()))
        if len(elites) > wanted:
            elites.sort(key=lambda item: item[0])
            del elites[wanted:]
        if should_stop is not None and should_stop():
            break
    elites.sort(key=lambda item: item[0])
    return [vec for _energy, vec in elites[:wanted]]


def project_preferences_to_deployed_support(
    preferences,
    deployed_weights,
) -> np.ndarray:
    """Rend sparse un vecteur DE en conservant son portefeuille effectif.

    Après quelques générations, les mutations du DE rendent presque toutes les
    coordonnées strictement positives. Le portefeuille déployé reste pourtant
    sparse, car les plafonds et la sélection par broker ne gardent que ses
    meilleures lignes. Un kick appliqué directement au vecteur dense retire
    donc surtout des coordonnées sans effet et peut ne changer aucune ligne
    réellement détenue, même à température maximale.

    On projette l'ancre sur le support effectivement déployé avant de la
    perturber. Les préférences relatives originales sont conservées sur ce
    support ; les poids déployés servent de repli lorsqu'une ligne provient du
    mécanisme de secours d'un broker et avait une préférence nulle.
    """
    raw = np.maximum(np.asarray(preferences, dtype=float), 0.0)
    deployed = np.maximum(np.asarray(deployed_weights, dtype=float), 0.0)
    if raw.shape != deployed.shape:
        raise ValueError("preferences et deployed_weights doivent avoir la même forme")
    support = deployed > 1e-12
    sparse = np.where(support, raw, 0.0)
    missing = support & (sparse <= 1e-12)
    sparse[missing] = deployed[missing]
    return sparse


def build_forced_floor_probes(
    anchor,
    forced_indices,
    floor: float,
) -> np.ndarray:
    """Construit un candidat par instrument, force au plancher demande.

    Les autres poids gardent exactement leurs proportions relatives. Le retour
    suit la convention vectorisee de l'objectif : ``instrument x candidat``.
    Si l'instrument depasse deja le plancher, la colonne reste egale a l'ancre.
    Le deploiement broker peut ensuite rendre le plancher impossible ; l'appelant
    doit donc verifier le poids effectivement deploye avant de retenir la graine.
    """
    base = np.maximum(np.asarray(anchor, dtype=float).reshape(-1), 0.0)
    total = float(base.sum())
    if total > 1e-12:
        base = base / total
    indices = np.asarray(list(forced_indices), dtype=int).reshape(-1)
    if indices.size == 0:
        return np.empty((base.size, 0), dtype=float)
    if np.any(indices < 0) or np.any(indices >= base.size):
        raise IndexError("indice force hors de l'univers")
    requested = np.asarray(floor, dtype=float)
    if requested.ndim == 0:
        targets = np.full(indices.size, float(requested), dtype=float)
    else:
        targets = requested.reshape(-1)
        if targets.size != indices.size:
            raise ValueError("un plancher est requis par indice force")
    targets = np.clip(targets, 0.0, 1.0)
    probes = np.repeat(base[:, None], indices.size, axis=1)
    for column, index in enumerate(indices):
        target = float(targets[column])
        current = float(base[index])
        if current >= target - 1e-12:
            continue
        remaining = max(1.0 - current, 0.0)
        if remaining <= 1e-12:
            probes[:, column] = 0.0
            probes[index, column] = 1.0
            continue
        probes[:, column] *= (1.0 - target) / remaining
        probes[index, column] = target
    return probes


def select_stratified_probe_elites(
    energies,
    is_etf,
    count: int,
) -> np.ndarray:
    """Retient les meilleurs probes sans laisser une classe chasser l'autre.

    Au plus la moitie du quota est d'abord prise dans chaque classe (ETF et
    actions). Les places non utilisees sont ensuite remplies au meilleur score
    global. Les energies non finies sont toujours ignorees.
    """
    values = np.asarray(energies, dtype=float).reshape(-1)
    flags = np.asarray(is_etf, dtype=bool).reshape(-1)
    if values.shape != flags.shape:
        raise ValueError("energies et is_etf doivent avoir la meme forme")
    wanted = max(0, min(int(count), values.size))
    if wanted == 0:
        return np.empty(0, dtype=int)
    valid = np.isfinite(values) & (values < INVALID_OBJECTIVE_ENERGY)
    selected: list[int] = []
    reserved = wanted // 2
    for class_mask in (flags, ~flags):
        candidates = np.flatnonzero(valid & class_mask)
        if candidates.size:
            order = candidates[np.argsort(values[candidates])]
            selected.extend(int(i) for i in order[:reserved])
    already = set(selected)
    remaining = np.array(
        [i for i in np.flatnonzero(valid) if int(i) not in already],
        dtype=int,
    )
    if remaining.size and len(selected) < wanted:
        order = remaining[np.argsort(values[remaining])]
        selected.extend(int(i) for i in order[: wanted - len(selected)])
    return np.asarray(selected[:wanted], dtype=int)


def effective_forced_floor_targets(
    floor: float,
    access,
    broker_ratios,
) -> np.ndarray:
    """Plancher global atteignable par instrument selon ses brokers accessibles."""
    matrix = np.asarray(access, dtype=float)
    ratios = np.asarray(broker_ratios, dtype=float).reshape(-1)
    if matrix.ndim != 2 or matrix.shape[1] != ratios.size:
        raise ValueError("access et broker_ratios sont incompatibles")
    available = matrix @ ratios
    return np.minimum(min(max(float(floor), 0.0), 1.0), available)


def apply_forced_floor_batch(X, index: int, floor: float) -> np.ndarray:
    """Impose un plancher à une ligne de chaque portefeuille d'une matrice.

    Les colonnes sont normalisées et les autres poids sont réduits au prorata.
    Le ticker peut ensuite dépasser le plancher naturellement : une colonne qui
    le dépasse déjà reste inchangée. Cette transformation paramètre tout l'espace
    d'un DE contraint, au lieu de corriger un unique individu après coup.
    """
    values = np.maximum(np.asarray(X, dtype=float), 0.0)
    if values.ndim == 1:
        values = values[:, None]
    if index < 0 or index >= values.shape[0]:
        raise IndexError("indice force hors de l'univers")
    totals = values.sum(axis=0)
    normalized = np.zeros_like(values)
    valid = totals > 1e-12
    normalized[:, valid] = values[:, valid] / totals[valid]
    target = min(max(float(floor), 0.0), 1.0)
    current = normalized[index]
    missing = current < target - 1e-12
    if missing.any():
        remaining = np.maximum(1.0 - current[missing], 1e-12)
        normalized[:, missing] *= (1.0 - target) / remaining
        normalized[index, missing] = target
    return normalized


def kick_portfolio(
    x,
    rng: np.random.Generator,
    *,
    n_drop: int,
    n_add: int,
    eligible_mask=None,
) -> np.ndarray:
    """Perturbe le SUPPORT d'un portefeuille : ferme ``n_drop`` lignes, en ouvre ``n_add``.

    Sur ce problème à cardinalité contrainte, ce qui enferme le DE dans un bassin
    c'est le choix des lignes ouvertes, pas leur pondération. Le bruit gaussien à
    σ=0,02 utilisé jusqu'ici ne changeait jamais le support : il ne pouvait donc
    faire sortir d'aucun optimum local. Un échange de lignes suivi d'une
    re-descente est le mécanisme de la recherche locale itérée.

    ``n_drop`` et ``n_add`` sont ramenés à ce que le vecteur permet (on ne ferme
    pas plus de lignes qu'il n'y en a d'ouvertes, ni n'en ouvre plus qu'il n'y a
    de titres inactifs). Quand ``eligible_mask`` est fourni, les nouvelles
    lignes sont aussi limitées aux titres effectivement accessibles.
    """
    out = np.clip(np.asarray(x, dtype=float).copy(), 0.0, 1.0)
    if eligible_mask is None:
        eligible = np.ones(out.size, dtype=bool)
    else:
        eligible = np.asarray(eligible_mask, dtype=bool).reshape(-1)
        if eligible.size != out.size:
            raise ValueError("eligible_mask incompatible avec le portefeuille")
    active = np.flatnonzero(out > 0.0)
    inactive = np.flatnonzero((out <= 0.0) & eligible)
    original_total = float(out.sum())
    drop = min(max(0, int(n_drop)), active.size)
    add = min(max(0, int(n_add)), inactive.size)
    # `rng.choice(..., replace=False)` est déjà efficace pour un petit tirage
    # dans une grande population (numpy n'y permute pas tout le tableau) :
    # mesuré, le remplacer par un tirage-avec-rejet est 2 à 3 fois PLUS LENT sur
    # un univers de 5 000 à 18 000 titres. À ne pas « optimiser ».
    if drop:
        out[rng.choice(active, size=drop, replace=False)] = 0.0
    if add:
        selected = rng.choice(inactive, size=add, replace=False)
        out[selected] = _replacement_line_weights(out, original_total, add, rng)
    out /= max(1.0, float(out.max(initial=0.0)))
    return out


def build_kick_variants(
    x,
    rng: np.random.Generator,
    *,
    count: int,
    min_lines: int,
    max_lines: int,
) -> list[np.ndarray]:
    """``count`` variantes kickées, d'amplitude tirée dans [min_lines, max_lines]."""
    lo = max(1, int(min_lines))
    hi = max(lo, int(max_lines))
    return [
        kick_portfolio(
            x,
            rng,
            n_drop=int(rng.integers(lo, hi + 1)),
            n_add=int(rng.integers(lo, hi + 1)),
        )
        for _ in range(max(0, int(count)))
    ]


def class_aware_prior(raw_mean_daily, classes) -> np.ndarray:
    """Prior de rendement journalier : la médiane de la CLASSE de chaque titre.

    Remplace la médiane globale unique, qui tirait les obligations vers la médiane
    de tout l'univers (15,79 %/an mesuré) et leur offrait ainsi ~9 points de
    rendement fictif tout en leur laissant leur risque quasi nul.

    Le shrinkage lui-même reste indispensable : mesuré sur 2145 titres, le
    rendement passé ne prédit pas le rendement futur (Pearson 0,001) alors que le
    risque, lui, persiste (Spearman 0,935). Sans régularisation l'optimiseur
    achèterait des titres dont l'avantage s'évapore et dont le risque reste. Mais
    l'écart ENTRE CLASSES est structurel et persiste (taux 4,32 -> 5,52 %, actions
    13,32 -> 18,13 % d'un semestre à l'autre) : c'est le bon groupe de pairs.

    `classes` est aligné index par index sur `raw_mean_daily` ; `None` = classe
    inconnue -> médiane globale (comportement historique).

    PAS de taille minimale de classe : une classe à un seul membre dégénère en sa
    propre moyenne, ce qui pour une obligation est la réponse conservatrice
    correcte. Un seuil minimal ferait retomber les petites classes sur la médiane
    globale, c'est-à-dire réintroduirait le bug d'origine.
    """
    mu = np.asarray(raw_mean_daily, dtype=float)
    finite_all = mu[np.isfinite(mu)]
    global_median = float(np.median(finite_all)) if finite_all.size else 0.0
    prior = np.full(mu.shape, global_median, dtype=float)
    labels = list(classes)
    for name in {c for c in labels if c is not None}:
        mask = np.array([c == name for c in labels], dtype=bool)
        values = mu[mask]
        finite = values[np.isfinite(values)]
        if finite.size:
            prior[mask] = float(np.median(finite))
    return prior


def optimize_portfolio_de(
    tickers: list[str],
    returns,  # pd.DataFrame de rendements journaliers
    matrix_access: list,
    active_brokers: list[str],
    seed: int = 42,
    progress_cb=None,  # callable(seed_num, iteration, convergence, global_best, *, seed_score) | None
    initialization_cb=None,  # callable(batch_num:int, max_batches:int, best_score:float|None)
    discretize_cb=None,  # callable(W_continu) -> W_discret | None : rend la version
    # RÉELLEMENT EXÉCUTABLE (actions entières / pies) du
    # portefeuille retenu, pour la scorer elle aussi.
    preparation_cb=None,  # callable(message:str) -- jalons de la phase SILENCIEUSE
    # qui precede le DE (simulation Monte-Carlo, copule,
    # matrices secteur/pays). Sans elle, un run affiche
    # "seed 1, 0 generation" pendant toute la preparation
    # et ressemble a un blocage (#bug rapporte).
    on_new_best=None,  # callable(W: np.ndarray[n_tickers x n_brokers]) | None
    on_candidate=None,  # callable(W) périodique pour enrichissement ETF paresseux
    should_stop=None,  # callable() -> bool | None -- verifie entre deux GENERATIONS
    should_restart=None,  # callable() -> bool | None -- nouvelles compositions ETF
    # (jamais au milieu d'une) et entre deux seeds : l'arret
    # demande prend effet en ~1 generation, plus en ~1 seed
    # (un seed sur ~2900 titres peut durer des jours).
    # Sans callback : s'arrete apres exactement 1 seed (defaut sur).
    continuous_until_stopped: bool | None = None,
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
    current_weights: dict[str, float] | None = None,
    current_broker_holdings: dict[str, dict[str, float]] | None = None,
    sector_by_ticker: dict[str, str] | None = None,
    sector_exposures_by_ticker: dict[str, dict[str, float]] | None = None,
    defensive_exposures_by_ticker: dict[str, float] | None = None,
    country_exposures: dict[str, dict[str, float]] | None = None,
    economic_action_exposures: dict[str, dict[str, float]] | None = None,
    economic_unknown_exposures: dict[str, float] | None = None,
    sector_country_exposures_by_ticker: (
        dict[str, dict[str, dict[str, float]]] | None
    ) = None,
    world_tickers: set[str] | None = None,
    world_min_weight: float = 0.0,
    max_generations: int | None = None,
    ttf_tickers: set[str] | None = None,
    benchmark_returns=None,   # pd.Series de rendements EUR du benchmark
    quality_scores_by_ticker: dict[str, float] | None = None,
    seed_number_offset: int = 0,
    return_diagnostics: bool = False,
):
    """Optimise le rendement moins le risque baissier, relativement au benchmark.

    Le score financier est exprimé en points de pourcentage annuels. L'objectif
    de recherche y ajoute les coûts, les pénalités et les bonus configurés, sous
    contraintes de disponibilité, de budget et d'exposition. Les scénarios de
    marché sont simulés une fois et partagés par tous les candidats.

    Les préférences ticker sont normalisées puis déployées chez les brokers.
    Le score porte sur ces poids déployés, en fraction du capital total : le cash
    libéré par les plafonds ou l'arrondi reste explicitement non investi.
    Retourne (W [n_tickers × n_brokers], score_financier_final), éventuellement
    suivi des diagnostics de l'objectif et de l'allocation exécutable.
    """
    # Classe semi-privée mais stable de scipy : nécessaire pour piloter le DE
    # génération par génération (arrêt sur convergence naturelle avec un minimum
    # de générations), ce que la fonction publique differential_evolution() ne
    # permet pas (elle n'expose qu'un maxiter dur + un callback qui ne peut
    # qu'arrêter plus tôt, jamais empêcher un arrêt prématuré).
    from scipy.optimize._differentialevolution import DifferentialEvolutionSolver

    if continuous_until_stopped is None:
        # La présence d'un bouton/callback d'arrêt signifie que l'appelant veut
        # enchaîner les départs jusqu'à cet arrêt explicite. Sans callback, un
        # seul seed reste la valeur sûre pour les appels programmatiques/tests.
        continuous_until_stopped = should_stop is not None

    from .starr import (
        benchmark_relative_batch_details,
        benchmark_stats,
        correlation_stability_diagnostics,
        neg_benchmark_relative,
        simulate_regime_scenarios,
        stratified_scenario_indices,
    )

    # Le benchmark n'appartient pas forcement a l'univers d'optimisation -- mais
    # PEUT y figurer en pratique : s'il est deja eligible par lui-meme (cas reel
    # aujourd'hui, cf. cache_status.json -- CW8.PA y est score=200 ETF, Achat=true,
    # tres liquide), le runner le laisse dans `tickers`/`returns` comme un candidat
    # d'allocation legitime. C'est VOULU : un portefeuille 100% benchmark score
    # exactement 0 (jamais exploitable par le DE), donc en detenir une fraction
    # comme diversification est sain -- la correction n'est PAS de l'exclure.
    #
    # Dans ce cas, on REUTILISE sa colonne existante comme serie de reference : on
    # n'en injecte PAS une seconde. Sinon la meme serie apparaitrait deux fois des
    # qu'elle est combinee a `returns` pour la simulation -> paire de correlation
    # 1.0 -> matrice de correlation singuliere (l'ajustement de copule et la
    # decomposition de Cholesky y sont sensibles).
    #
    # Seulement s'il est ABSENT de `tickers` (cas fantome deja neutralise par le
    # runner -- score/Achat/liquidite insuffisants -- ou ecarte plus tard par la
    # dedup/selection ETF) sa seule source redevient la serie injectee par
    # l'appelant : sans elle le score relatif n'a aucun sens -> echec explicite.
    # Le message precise que c'est l'APPELANT qui n'a pas fourni la serie (pas
    # seulement "ticker introuvable") : le bouton manuel de creation de
    # portefeuille (app/api/finance/buffett.py, _run_portfolio_creation) a
    # longtemps appele optimize_portfolio_de sans passer benchmark_returns du
    # tout, et le message d'origine laissait croire a tort que CW8.PA lui-meme
    # etait injoignable.
    def _prep(message: str) -> None:
        """Jalon de la phase de préparation, avant que le DE ne compte des générations."""
        if preparation_cb is not None:
            try:
                preparation_cb(message)
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation

    tickers_upper = [str(t).upper() for t in tickers]
    bench_ticker_cfg = str(Config.STARR_BENCHMARK_TICKER).strip().upper()
    bench_in_universe = bool(bench_ticker_cfg) and bench_ticker_cfg in tickers_upper
    if bench_in_universe:
        bench_series = np.asarray(returns, dtype=float)[:, tickers_upper.index(bench_ticker_cfg)]
    else:
        if benchmark_returns is None or len(benchmark_returns) < 2:
            raise ValueError(
                f"benchmark {Config.STARR_BENCHMARK_TICKER} absent de l'univers "
                "optimise ET aucune serie benchmark_returns fournie par "
                "l'appelant : le score relatif ne peut pas etre calcule"
            )
        bench_series = np.asarray(benchmark_returns, dtype=float)
        if len(bench_series) < int(Config.STARR_MIN_HISTORY_DAYS):
            raise ValueError(
                f"benchmark {Config.STARR_BENCHMARK_TICKER} : "
                f"{len(bench_series)} jours < {Config.STARR_MIN_HISTORY_DAYS} requis"
            )

    n_sim = int(Config.STARR_N_SIM if n_sim is None else n_sim)
    alpha = float(Config.STARR_ALPHA if alpha is None else alpha)
    downside_weight = float(
        Config.STARR_DOWNSIDE_WEIGHT if downside_weight is None else downside_weight
    )
    min_position = float(Config.MIN_ALLOCATION_THRESHOLD if min_position is None else min_position)
    card_beta = float(Config.STARR_CARD_BETA)
    max_position = float(Config.MAX_POSITION_PCT)

    # ETF (depuis ToutBroker) -> exemptés du plafond de poids par titre.
    # `load_etf_tickers`/`load_asset_classes` sont importés en tête de module :
    # un `monkeypatch.setattr(optimizer, "load_etf_tickers", ...)` porte donc
    # réellement (l'import local précédent rendait tout patch de test inopérant).
    etf_set = load_etf_tickers()
    is_etf_full = np.array([str(t).upper() in etf_set for t in tickers], dtype=bool)

    num_t = len(tickers)
    num_b = len(active_brokers)
    # Trois nombres distincts, à ne jamais confondre :
    #
    #   max_per_broker        seuil historique conservé pour les diagnostics.
    #   broker_line_caps      CAPACITÉ ÉCONOMIQUE, propre à chaque broker :
    #                         combien de lignes il peut tenir AU-DESSUS du
    #                         plancher de 1 % (3 pour un broker à 3,5 %, ~96
    #                         pour un broker à 96 %).
    #   broker_hard_line_caps PLAFOND DUR effectivement appliqué à la troncature.
    #
    # Les fusionner a coûté deux bugs successifs. La capacité reste donc
    # indépendante du seuil historique et protège uniquement l'exécution d'un
    # petit broker étalé sur des micro-lignes non achetables.
    max_per_broker = int(Config.STARR_MAX_LINES_PER_BROKER)
    total_cap = sum(Config.BUDGET_BROKERS.values()) or 1.0
    b_ratios = np.array([Config.BUDGET_BROKERS[b] / total_cap for b in active_brokers])
    # CAPACITÉ ÉCONOMIQUE : combien de lignes le broker tient au-dessus du
    # plancher de 1 % (3 pour un broker à 3,5 %, ~96 pour un broker à 96 %).
    broker_capacity = np.asarray(
        [
            max(
                1,
                int(
                    math.floor(
                        1.0
                        / max(float(Config.STARR_MIN_T212_PIE_PCT), 0.01)
                    )
                ),
            )
            if is_fractional_broker(broker)
            else (
                # Bourse Direct / PEA : aucune capacité calculée à partir
                # d'un seuil de 1 %. Une ligne est retenue si la discrétisation
                # finale peut acheter au moins une action.
                num_t
                if min_position <= 0
                else broker_line_cap(Config.BUDGET_BROKERS[broker], total_cap)
            )
            for broker in active_brokers
        ],
        dtype=int,
    )
    # Avec le malus désactivé, la capacité réelle devient aussi la valeur
    # diagnostiquée : aucun seuil de 20 lignes ne doit continuer à limiter ou à
    # suggérer une limite politique.
    broker_line_caps = (
        broker_capacity
        if card_beta <= 0.0
        else np.minimum(broker_capacity, max_per_broker).astype(int)
    )
    # TRONCATURE : la capacité économique, et elle seule. Aucun plafond de
    # politique ne limite le score en fonction du nombre de lignes.
    broker_hard_line_caps = broker_capacity

    R = np.asarray(returns, dtype=float)
    mean_window_days = max(1, int(Config.STARR_MEAN_WINDOW_DAYS))
    R_mean = R[-min(len(R), mean_window_days):]
    raw_mean_daily = R_mean.mean(axis=0)
    mean_signal_weight = min(max(float(Config.STARR_MEAN_SIGNAL_WEIGHT), 0.0), 1.0)
    # Prior par CLASSE d'actif et non mediane globale : tirer une obligation vers la
    # mediane de tout l'univers (15,79 %/an mesure) lui offrait ~9 points de
    # rendement fictif tout en lui laissant son risque quasi nul -- c'est ce qui
    # faisait allouer 96 % du portefeuille a un ETF monetaire.
    asset_classes = load_asset_classes()
    ticker_classes = [asset_classes.get(str(t).upper()) for t in tickers]
    prior_daily = class_aware_prior(raw_mean_daily, ticker_classes)
    mean_daily_all = (
        mean_signal_weight * raw_mean_daily
        + (1.0 - mean_signal_weight) * prior_daily
    )
    std = R_mean.std(axis=0)

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
    access_inv = access[inv_idx]  # dispo broker restreinte aux titres investissables
    reconstruction_eligible = np.any(
        np.asarray(access_inv, dtype=bool)
        & (np.asarray(b_ratios, dtype=float)[None, :] > 0.0),
        axis=1,
    )
    inv_tickers_upper = [str(tickers[i]).upper() for i in inv_idx]
    # Le benchmark est simule AVEC l'univers : memes scenarios, memes dependances
    # de queue. S'il fait deja partie des titres investissables, on REUTILISE sa
    # colonne -- en ajouter une seconde ferait apparaitre la meme serie deux fois,
    # donc une paire de correlation 1,0 qui peut rendre la matrice singuliere
    # (l'ajustement de copule et la decomposition de Cholesky y sont sensibles).
    bench_pos = (
        inv_tickers_upper.index(bench_ticker_cfg)
        if bench_ticker_cfg in inv_tickers_upper
        else None
    )
    if bench_pos is None:
        bench_aligned = bench_series[-R_inv.shape[0]:]
        if len(bench_aligned) < R_inv.shape[0]:
            bench_aligned = np.concatenate(
                [np.zeros(R_inv.shape[0] - len(bench_aligned)), bench_aligned]
            )
        R_sim = np.column_stack([R_inv, bench_aligned])
    else:
        bench_aligned = R_inv[:, bench_pos]
        R_sim = R_inv
    print(
        f"    * Score vs {Config.STARR_BENCHMARK_TICKER} : {len(inv_idx)} titres, "
        f"{n_sim} scénarios (Monte-Carlo + copule, CVaR {int(alpha * 100)} %)..."
    )
    _prep(
        f"Simulation Monte-Carlo : {n_sim:,} scénarios sur {len(inv_idx)} titres "
        "(copule + marginales Student-t)…".replace(",", " ")
    )
    sim_full, regime_diagnostics = simulate_regime_scenarios(
        R_sim,
        n_sim=n_sim,
        seed=seed,
        windows=Config.STARR_REGIME_WINDOWS,
        min_coverage=Config.STARR_REGIME_MIN_COVERAGE,
    )
    if bench_pos is None:
        sim_rets = sim_full[:, :-1]
        bench_sim = sim_full[:, -1]
        # Le benchmark passe par le MEME estimateur que les candidats (prior de
        # classe « actions ») : comparer une estimation regularisee a une moyenne
        # brute biaiserait la comparaison en faveur du benchmark.
        raw_bench = float(
            np.mean(bench_aligned[-min(len(bench_aligned), mean_window_days):])
        )
        actions_mask = np.array([c == "actions" for c in ticker_classes], dtype=bool)
        pool = raw_mean_daily[actions_mask] if actions_mask.any() else raw_mean_daily
        finite_pool = pool[np.isfinite(pool)]
        bench_prior = float(np.median(finite_pool)) if finite_pool.size else 0.0
        bench_mean_daily = (
            mean_signal_weight * raw_bench + (1.0 - mean_signal_weight) * bench_prior
        )
    else:
        sim_rets = sim_full
        bench_sim = sim_full[:, bench_pos]
        bench_mean_daily = float(mean_daily[bench_pos])
    bench_full = benchmark_stats(bench_sim, bench_mean_daily, alpha, 0.0)
    print(
        f"    * Benchmark : rendement {bench_full['annual_return'] * 100:.2f} %, "
        f"CVaR {bench_full['cvar'] * 100:.2f} %, "
        f"baisse {bench_full['downside_deviation'] * 100:.2f} %"
    )
    _prep("Analyse de la stabilité des corrélations entre régimes…")
    correlation_diagnostics = correlation_stability_diagnostics(
        R_inv,
        [str(tickers[i]).upper() for i in inv_idx],
        windows=Config.STARR_REGIME_WINDOWS,
        min_coverage=Config.STARR_REGIME_MIN_COVERAGE,
    )
    window_text = ", ".join(
        f"{w['label']}={w['observations']}j/{w['weight']:.0%}"
        for w in regime_diagnostics["windows"]
    )
    print(f"    * Mélange de régimes : {window_text}")
    if correlation_diagnostics.get("available"):
        print(
            "    * Stabilité corrélations : "
            f"{correlation_diagnostics['unstable_pairs']}/"
            f"{correlation_diagnostics['n_pairs']} paires instables (delta >= 0,25), "
            f"{correlation_diagnostics['major_shift_pairs']} changements majeurs "
            "(delta >= 0,40)"
        )

    _prep("Construction des matrices de contraintes (secteurs, pays, look-through)…")
    holdings_by_ticker: dict[str, float] = {}
    if current_broker_holdings:
        for broker_values in current_broker_holdings.values():
            for ticker, weight in broker_values.items():
                key = str(ticker).upper()
                holdings_by_ticker[key] = holdings_by_ticker.get(key, 0.0) + max(
                    float(weight or 0.0), 0.0
                )
    # Les positions réellement détenues servent au calcul des frais de
    # transaction. La dernière cible optimisée a un rôle différent : c'est le
    # champion du run précédent, réévalué avec les données du run courant puis
    # injecté comme point de départ. Ne pas laisser les positions réelles
    # masquer ce champion lorsqu'elles sont disponibles.
    previous_champion_weights = {
        str(t).upper(): float(w or 0.0) for t, w in (current_weights or {}).items()
    }
    source_weights = holdings_by_ticker or previous_champion_weights
    current_full = np.array(
        [max(float(source_weights.get(str(t).upper(), 0.0) or 0.0), 0.0) for t in tickers],
        dtype=float,
    )
    current_inv = current_full[inv_idx]
    current_total = float(current_inv.sum())
    has_current_weights = current_total > 1e-12
    if has_current_weights:
        current_inv /= current_total
    champion_full = np.array(
        [
            max(float(previous_champion_weights.get(str(t).upper(), 0.0) or 0.0), 0.0)
            for t in tickers
        ],
        dtype=float,
    )
    champion_inv = champion_full[inv_idx]
    champion_input_total = float(sum(previous_champion_weights.values()))
    champion_retained_total = float(champion_inv.sum())
    has_previous_champion = champion_retained_total > 1e-12
    if has_previous_champion:
        champion_inv /= champion_retained_total
    # Plus de penalite de turnover : elle faisait DOUBLON avec les frais de
    # transaction, qui modelisent deja le cout en euros des ordres (x
    # REBALANCES_PER_YEAR). `current_inv` reste nécessaire pour ces frais et le
    # portefeuille détenu reste lui aussi un point de départ utile.

    # ── Contraintes look-through (défensif min, pays max) ────────────────────
    from .lookthrough import fill_unknown_countries, load_lookthrough

    requested_min_defensive = min(
        max(float(Config.MIN_DEFENSIVE_PCT), 0.0),
        1.0,
    )
    min_def = requested_min_defensive
    max_achievable_defensive: float | None = None
    defensive_floor_relaxed = False
    # « Sans ETF » ne signifie pas « sans contraintes ». Une forte concentration
    # géographique est autorisée pour un univers actions/PEA, mais le plancher
    # défensif reste obligatoire.
    actions_only_universe = not bool(np.any(is_etf_full[inv_idx]))
    # Une concentration européenne est structurelle dans un portefeuille PEA
    # sans ETF. Les plafonds durs sont déjà désactivés dans ce mode ; on rend
    # aussi les malus géographiques souples beaucoup moins directifs. Le bonus
    # de diversification reste disponible : il récompense une diversification
    # effectivement avantageuse sans l'imposer artificiellement.
    geographic_soft_penalty_factor = 0.10 if actions_only_universe else 1.0
    country_hard_cap_enabled = bool(
        getattr(Config, "COUNTRY_HARD_CAP_ENABLED", True)
    ) and not actions_only_universe
    max_country = float(Config.MAX_COUNTRY_PCT) if country_hard_cap_enabled else 1.0
    pen_k = float(Config.CONSTRAINT_PENALTY)
    cash_pen_k = float(Config.STARR_CASH_PENALTY)
    inv_tickers = [str(tickers[i]).upper() for i in inv_idx]
    world_names = {str(value).strip().upper() for value in (world_tickers or set())}
    world_mask = np.asarray([ticker in world_names for ticker in inv_tickers], dtype=bool)
    world_floor = min(max(float(world_min_weight), 0.0), 1.0)
    if world_floor > 0 and not world_mask.any():
        raise ValueError("plancher MSCI World demandé mais aucun ETF World n'est investissable")
    try:
        defmap, paysmap = load_lookthrough()
    except Exception:
        defmap, paysmap = {}, {}
    if defensive_exposures_by_ticker is not None:
        defmap.update({
            str(ticker).strip().upper(): min(max(float(value), 0.0), 1.0)
            for ticker, value in defensive_exposures_by_ticker.items()
        })
    if country_exposures is not None:
        paysmap.update({
            str(ticker).strip().upper(): dict(weights)
            for ticker, weights in country_exposures.items()
        })
    # Une donnée absente reste explicitement inconnue. Elle n'hérite jamais de la
    # moyenne des autres candidats, ce qui fabriquerait de la diversification.
    paysmap = fill_unknown_countries(paysmap, inv_tickers)
    d_vec = np.array([defmap.get(t, 0.0) for t in inv_tickers], dtype=float)
    # Or/matières premières physiques : absence réelle d'exposition à un pays
    # d'entreprise. Le seau reste visible en diagnostic mais n'est pas soumis au
    # plafond pays. ``Inconnu`` reste, lui, plafonné à 25 %.
    all_countries, C_mat = country_exposure_matrix(
        inv_tickers,
        paysmap,
        excluded_buckets={"Sans pays"},
    )
    # Le BUDGET DE RISQUE géographique ne porte que sur de vrais pays. « Inconnu »
    # et « Autres » sont des seaux fourre-tout : les pénaliser reviendrait à
    # sanctionner un défaut de donnée, pas une concentration réelle. Ils restent
    # en revanche soumis au plafond de poids, qui décourage de les accumuler.
    _risk_country_idx = [
        index
        for index, country in enumerate(all_countries)
        if country not in {"Inconnu", "Autres", "Unknown", "Other"}
    ]
    risk_countries = [all_countries[index] for index in _risk_country_idx]
    C_mat_risk = (
        C_mat[:, _risk_country_idx] if _risk_country_idx else C_mat[:, :0]
    )
    from .region_lookthrough import aggregate_regions
    region_map = aggregate_regions(paysmap)
    all_regions, R_mat = country_exposure_matrix(
        inv_tickers, region_map, excluded_buckets={"Inconnu"}
    )
    geographic_constraint_label = (
        "plafonds désactivés, malus souples ×10% (actions seules)"
        if actions_only_universe
        else f"pays<={max_country:.0%}, régions<={float(getattr(Config, 'MAX_REGION_PCT', 0.50)):.0%}"
    )
    print(
        f"    * Contraintes : defensif>={min_def:.0%} (dispo {float(d_vec.max() if len(d_vec) else 0):.0%} max), "
        f"géographie={geographic_constraint_label} ({len(all_countries)} pays)"
    )

    # ── Optimisation niveau TICKER (simplexe sum=1) sur l'objectif STARR ─────
    n_inv = len(inv_idx)
    bounds = [(0.0, 1.0)] * n_inv
    is_etf_inv = is_etf_full[inv_idx]
    direct_action_policy_enabled = quality_scores_by_ticker is not None
    direct_action_mask = ~is_etf_inv
    direct_action_candidates = int(np.sum(direct_action_mask))
    # Les actions restent dans l'univers et des candidats qui en contiennent sont
    # explicitement suivis, mais le portefeuille final reste totalement libre.
    direct_action_min_weight = 0.0
    direct_action_min_lines = 0
    direct_action_quality = np.zeros(n_inv, dtype=float)
    if quality_scores_by_ticker:
        for index, ticker in enumerate(inv_tickers):
            if is_etf_inv[index]:
                continue
            quality = float(quality_scores_by_ticker.get(ticker, 85.0) or 85.0)
            direct_action_quality[index] = min(max((quality - 85.0) / 15.0, 0.0), 1.0)
    direct_action_quality_bonus = float(Config.STARR_DIRECT_ACTION_QUALITY_BONUS)
    from .sector_constraints import (
        constrained_sector_labels,
        country_diversification_score_from_buckets,
        geographic_diversification_factors,
        sector_country_deficit_penalty,
        sector_country_diversification_components,
        sector_country_diversification_score,
        sector_country_exposures,
        sector_downside_risk_from_context,
        sector_downside_risk_penalty,
    )

    sector_labels = (
        constrained_sector_labels(
            inv_tickers,
            is_etf=is_etf_inv,
            fallback_sectors=sector_by_ticker,
        )
        if sector_by_ticker is not None
        else [None] * len(inv_tickers)
    )
    from .sector_lookthrough import sector_matrix
    sector_mat, sector_names = sector_matrix(
        inv_tickers,
        sector_exposures_by_ticker or {},
        sector_labels,
    )
    # Table exacte ticker × secteur × pays. Elle provient des constituants de
    # l'indice pour les ETF synthétiques et des positions officielles pour les
    # ETF physiques. On ne reconstruit plus le croisement comme le produit de
    # deux marginales indépendantes, qui pouvait inventer par exemple de la
    # technologie japonaise dans un ETF dont la technologie était américaine.
    from .breakdown import _canon_sector

    sector_positions = {
        str(sector).casefold(): index for index, sector in enumerate(sector_names)
    }
    country_positions = {
        str(country).casefold(): index for index, country in enumerate(all_countries)
    }
    joint_mat = np.zeros(
        (len(inv_tickers), len(sector_names), len(all_countries)), dtype=float
    )
    joint_by_ticker = {
        str(ticker).strip().upper(): values
        for ticker, values in (sector_country_exposures_by_ticker or {}).items()
    }
    for ticker_index, ticker in enumerate(inv_tickers):
        values = joint_by_ticker.get(ticker, {})
        for raw_sector, by_country in values.items():
            sector = _canon_sector(str(raw_sector))
            sector_index = sector_positions.get(sector.casefold())
            if sector_index is None:
                continue
            for raw_country, weight in (by_country or {}).items():
                country_index = country_positions.get(str(raw_country).casefold())
                if country_index is None:
                    continue
                joint_mat[ticker_index, sector_index, country_index] += max(
                    float(weight), 0.0
                )
        # Une action directe constitue un couple secteur-pays exact. Ce repli
        # ne s'applique jamais aux ETF : leur composition doit être publiée.
        if not is_etf_inv[ticker_index] and not np.any(joint_mat[ticker_index]):
            sector = _canon_sector(str(sector_labels[ticker_index] or ""))
            sector_index = sector_positions.get(sector.casefold())
            if sector_index is not None:
                for raw_country, weight in paysmap.get(ticker, {}).items():
                    country_index = country_positions.get(str(raw_country).casefold())
                    if country_index is not None:
                        joint_mat[ticker_index, sector_index, country_index] += max(
                            float(weight), 0.0
                        )
    economic_map = {
        str(ticker).upper(): {
            str(action).upper(): max(float(weight), 0.0)
            for action, weight in values.items()
            if float(weight) > 0
        }
        for ticker, values in (economic_action_exposures or {}).items()
    }
    # Une action directe est connue à 100 %. Un ETF sans composition économique
    # suffisante reste une ligne nulle et ne reçoit jamais une diversification
    # fictive.
    for index, ticker in enumerate(inv_tickers):
        if not is_etf_inv[index] and ticker not in economic_map:
            economic_map[ticker] = {ticker: 1.0}
    economic_actions = sorted({
        action for ticker in inv_tickers for action in economic_map.get(ticker, {})
    })
    action_positions = {action: index for index, action in enumerate(economic_actions)}
    E_mat = np.zeros((len(inv_tickers), len(economic_actions)), dtype=float)
    for ticker_index, ticker in enumerate(inv_tickers):
        for action, weight in economic_map.get(ticker, {}).items():
            E_mat[ticker_index, action_positions[action]] = weight
    max_economic_action = max(
        0.0, float(getattr(Config, "STARR_MAX_ECONOMIC_ACTION_PCT", 0.08))
    )
    unknown_equity_by_ticker = {
        str(ticker).upper(): min(max(float(weight), 0.0), 1.0)
        for ticker, weight in (economic_unknown_exposures or {}).items()
    }
    unknown_equity_vec = np.asarray(
        [unknown_equity_by_ticker.get(ticker, 0.0) for ticker in inv_tickers],
        dtype=float,
    )
    max_sector = float(Config.MAX_SECTOR_PCT)
    # Plafonds par compartiment : défaut commun + surcharges (or, ...).
    from .sector_constraints import SectorCaps
    sector_caps = SectorCaps.from_config()
    max_sector_risk_share = max(
        0.0,
        float(Config.STARR_MAX_SECTOR_RISK_SHARE),
    )
    sector_risk_penalty_coefficient = max(
        0.0,
        float(Config.STARR_SECTOR_RISK_PENALTY),
    )
    sector_risk_cap_overrides = {
        _canon_sector(str(sector)): max(float(value), 0.0)
        for sector, value in getattr(
            Config, "STARR_MAX_SECTOR_RISK_SHARE_OVERRIDES", {}
        ).items()
    }
    sector_risk_penalty_overrides = {
        _canon_sector(str(sector)): max(float(value), 0.0)
        for sector, value in getattr(
            Config, "STARR_SECTOR_RISK_PENALTY_OVERRIDES", {}
        ).items()
    }
    sector_risk_caps = np.asarray(
        [
            sector_risk_cap_overrides.get(sector, max_sector_risk_share)
            for sector in sector_names
        ],
        dtype=float,
    )
    sector_risk_penalties = np.asarray(
        [
            sector_risk_penalty_overrides.get(
                sector, sector_risk_penalty_coefficient
            )
            for sector in sector_names
        ],
        dtype=float,
    )
    max_country_risk_share = max(
        0.0,
        float(getattr(Config, "STARR_MAX_COUNTRY_RISK_SHARE", 0.0)),
    )
    country_risk_penalty_coefficient = max(
        0.0,
        float(getattr(Config, "STARR_COUNTRY_RISK_PENALTY", 0.0)),
    ) * geographic_soft_penalty_factor
    max_region = min(
        max(float(getattr(Config, "MAX_REGION_PCT", 0.50)), 0.0), 1.0
    )
    region_hard_cap_enabled = bool(
        not actions_only_universe and R_mat.shape[1] >= 2 and max_region < 1.0
    )
    max_region_risk_share = max(
        0.0, float(getattr(Config, "STARR_MAX_REGION_RISK_SHARE", 0.40))
    )
    region_risk_penalty_coefficient = max(
        0.0, float(getattr(Config, "STARR_REGION_RISK_PENALTY", 5.0))
    ) * geographic_soft_penalty_factor
    sector_country_deficit_penalty_coefficient = max(
        0.0, float(Config.STARR_SECTOR_COUNTRY_DEFICIT_PENALTY)
    ) * geographic_soft_penalty_factor
    sector_country_bonus = max(
        0.0,
        float(Config.STARR_SECTOR_COUNTRY_DIVERSIFICATION_BONUS),
    )
    sector_country_significant_exposure = max(
        0.0,
        float(Config.STARR_SECTOR_COUNTRY_SIGNIFICANT_PCT),
    )
    sector_country_significant_weight = max(
        0.0,
        float(Config.STARR_SECTOR_COUNTRY_SIGNIFICANT_BONUS_WEIGHT),
    )
    geographic_bonus = max(
        0.0,
        float(getattr(Config, "STARR_GEOGRAPHIC_DIVERSIFICATION_BONUS", 0.0)),
    )
    geographic_country_std_exponent = max(
        0.0,
        float(getattr(Config, "STARR_GEOGRAPHIC_COUNTRY_STD_EXPONENT", 0.0)),
    )
    geographic_region_std_exponent = max(
        0.0,
        float(getattr(Config, "STARR_GEOGRAPHIC_REGION_STD_EXPONENT", 0.0)),
    )
    # Cible de déploiement du malus « cash oisif » : somme des budgets brokers
    # (1.0 quand tout le capital est réparti entre brokers actifs), MAIS bornée
    # par ce que les plafonds rendent atteignable. Sur un univers étroit (une
    # poignée de titres, plafond de 15 % par action), 100 % investi est
    # structurellement impossible : pénaliser l'écart à 1.0 rendrait alors TOUT
    # portefeuille inadmissible (même le point de départ du DE). On ne pénalise
    # donc que le cash réellement évitable.
    # Le calcul est fait PAR BROKER : un broker dont les titres accessibles ne
    # peuvent pas absorber son budget (peu de titres × plafond de 15 %) laisse un
    # cash irréductible qu'il serait absurde — et bloquant — de pénaliser.
    _caps_inv = np.where(is_etf_inv, 1.0, max_position)
    deployable_total = 0.0
    for _j in range(num_b):
        if b_ratios[_j] <= 0:
            continue
        _sector_capacity: dict[str, float] = {}
        _free_capacity = 0.0
        for _i, (_label, _cap_i) in enumerate(zip(sector_labels, _caps_inv, strict=True)):
            if not access_inv[_i, _j]:
                continue
            if _label:
                _sector_capacity[_label] = _sector_capacity.get(_label, 0.0) + float(_cap_i)
            else:
                _free_capacity += float(_cap_i)
        capacity_j = _free_capacity + sum(
            min(sector_caps.for_label(_label), value)
            for _label, value in _sector_capacity.items()
        )
        deployable_total += min(float(b_ratios[_j]), capacity_j)
    # Le plafond sectoriel porte sur le capital TOTAL : la somme des capacités
    # par broker peut le surestimer. On reborne globalement.
    _global_sector: dict[str, float] = {}
    _global_free = 0.0
    for _label, _cap_i in zip(sector_labels, _caps_inv, strict=True):
        if _label:
            _global_sector[_label] = _global_sector.get(_label, 0.0) + float(_cap_i)
        else:
            _global_free += float(_cap_i)
    deployable_total = min(
        deployable_total,
        _global_free
        + sum(
            min(sector_caps.for_label(_label), v)
            for _label, v in _global_sector.items()
        ),
    )
    from app.services.finance import fx

    from .transaction_costs import TransactionCostModel, first_year_cost_summary

    transaction_costs_enabled = bool(Config.TRANSACTION_COSTS_ENABLED)
    gbp_eur_rate = 1.0
    if transaction_costs_enabled:
        try:
            # Le warm-up FX du run a déjà alimenté le cache avant l'optimisation.
            gbp_eur_rate = float(fx.get_rate("GBP", "EUR") or 1.0)
        except Exception:
            gbp_eur_rate = 1.0
    transaction_cost_model = TransactionCostModel(
        inv_tickers, is_etf_inv, ttf_tickers, gbp_eur_rate=gbp_eur_rate
    )
    # Le prochain rééquilibrage est une transition unique, pas un ordre
    # hypothétique répété quatre fois dans l'année.
    trade_cost_multiplier = 1.0

    # Recherche DE sur un SOUS-ÉCHANTILLON de scénarios en float32 : le coût est
    # dominé par le produit sim @ W (bande passante mémoire), et cette précision
    # suffit largement pour COMPARER des candidats entre eux. Le STARR final est
    # recalculé sur les n_sim scénarios complets en float64 (cf. fin).
    n_search = max(1, min(n_sim, int(Config.STARR_N_SIM_SEARCH)))
    search_indices, search_regime_counts = stratified_scenario_indices(
        regime_diagnostics, n_search, seed=seed + 7919,
    )
    sim_search = np.ascontiguousarray(sim_rets[search_indices], dtype=np.float32)
    bench_search_sim = np.asarray(bench_sim[search_indices], dtype=float)
    bench = benchmark_stats(bench_search_sim, bench_mean_daily, alpha, 0.0)
    regime_diagnostics["search_sample"] = {
        "n_sim": int(len(search_indices)),
        "counts": search_regime_counts,
        "stratified": True,
        "seed": int(seed + 7919),
    }

    use_lookthrough_constraints = True
    # Initialisé uniformément puis remplacé, avant la première évaluation, par
    # un classement déterministe des scores standalone. Sert uniquement si un
    # candidat ne donne aucun titre à un broker ayant pourtant du budget.
    fallback_preferences = np.ones(n_inv, dtype=float)

    def _broker_allocation_batch(preferences: np.ndarray, broker_index: int) -> np.ndarray:
        """Allocation normalisée d'un broker, vectorisée sur tous les candidats."""
        available = access_inv[:, broker_index, None]
        offered = np.where(available, preferences, 0.0)
        # Le plancher est exprimé sur le portefeuille global, pas sur le broker.
        selected = np.where(offered >= min_position, offered, 0.0)
        empty = selected.sum(axis=0) <= 1e-12
        if empty.any():
            selected[:, empty] = offered[:, empty]
        still_empty = selected.sum(axis=0) <= 1e-12
        if still_empty.any():
            fallback = np.broadcast_to(
                np.where(available, fallback_preferences[:, None], 0.0),
                selected.shape,
            )
            selected[:, still_empty] = fallback[:, still_empty]

        # La capacité borne seulement le déploiement continu. Le terme de
        # cardinalité est désactivé par défaut (`STARR_CARD_BETA=0`) ; STARR
        # choisit donc librement le nombre de lignes dans cette enveloppe.
        line_cap = int(broker_hard_line_caps[broker_index])
        if selected.shape[0] > line_cap:
            top_idx = np.argpartition(selected, -line_cap, axis=0)[-line_cap:]
            top = np.zeros_like(selected)
            np.put_along_axis(
                top,
                top_idx,
                np.take_along_axis(selected, top_idx, axis=0),
                axis=0,
            )
            selected = top

        totals = selected.sum(axis=0)
        valid = totals > 1e-12
        allocation = np.zeros_like(selected)
        allocation[:, valid] = selected[:, valid] / totals[valid]
        return allocation

    # Utiliser en priorité la provenance réelle des positions. Le repli legacy
    # reste disponible pour les anciennes installations sans table Position.
    current_broker_weights = np.zeros((n_inv, num_b), dtype=float)
    has_real_broker_holdings = bool(current_broker_holdings)
    if has_real_broker_holdings:
        for j, broker in enumerate(active_brokers):
            by_ticker = current_broker_holdings.get(broker, {})
            broker_values = np.asarray(
                [by_ticker.get(t, 0.0) for t in inv_tickers],
                dtype=float,
            )
            current_broker_weights[:, j] = np.where(
                np.isfinite(broker_values),
                np.maximum(broker_values, 0.0),
                0.0,
            )
    elif has_current_weights:
        for j in range(num_b):
            current_broker_weights[:, j] = (
                b_ratios[j] * _broker_allocation_batch(current_inv[:, None], j)[:, 0]
            )

    def _split_budget_batch(preferences: np.ndarray) -> np.ndarray:
        """Ventile les préférences par broker, pour toute la population.

        La boucle porte uniquement sur le rang des titres ; tous les candidats
        DE sont traités ensemble par NumPy. L'affectation principale cantonne
        les titres ; le complément borné d'un broker vide peut rester partagé.
        """
        prefs = np.asarray(preferences, dtype=float)
        n_candidates = prefs.shape[1]
        candidate_cols = np.arange(n_candidates)
        remaining = np.broadcast_to(
            b_ratios[:, None], (num_b, n_candidates)
        ).copy()
        assignments = np.full((n_inv, n_candidates), -1, dtype=np.int16)
        order = np.argsort(prefs, axis=0)[::-1]
        budget_enabled = b_ratios > 0

        for rank in range(n_inv):
            ticker_rows = order[rank]
            values = prefs[ticker_rows, candidate_cols]
            access_rows = access_inv[ticker_rows, :]
            eligible = (
                access_rows
                & budget_enabled[None, :]
                & (values[:, None] > 1e-12)
                & (values[:, None] >= min_position * b_ratios[None, :])
            )
            choices = np.where(
                eligible,
                remaining.T,
                -np.inf,
            )
            broker_choice = np.argmax(choices, axis=1)
            has_choice = np.isfinite(
                choices[candidate_cols, broker_choice]
            )
            if not has_choice.any():
                continue
            cols = candidate_cols[has_choice]
            rows = ticker_rows[has_choice]
            brokers = broker_choice[has_choice]
            assignments[rows, cols] = brokers
            remaining[brokers, cols] -= values[has_choice]

        cube = np.zeros((n_inv, num_b, n_candidates), dtype=float)
        for j in range(num_b):
            selected = np.where(assignments == j, prefs, 0.0)
            # Plafond ABSOLU (et non le seuil du malus, cf. plus haut).
            line_cap = int(broker_hard_line_caps[j])
            if n_inv > line_cap:
                top_idx = np.argpartition(
                    selected, -line_cap, axis=0
                )[-line_cap:]
                capped = np.zeros_like(selected)
                np.put_along_axis(
                    capped,
                    top_idx,
                    np.take_along_axis(selected, top_idx, axis=0),
                    axis=0,
                )
                selected = capped
            totals = selected.sum(axis=0)
            valid = totals > 1e-12
            if valid.any():
                cube[:, j, valid] = (
                    b_ratios[j] * selected[:, valid] / totals[valid]
                )
            # Un petit broker peut rester vide quand le gros broker a absorbé
            # toutes les préférences significatives. Ne pas recopier tout son
            # panier : privilégier les titres propres au broker puis limiter le
            # complément au nombre de lignes utile pour son poids budgétaire.
            starved = ~valid
            if starved.any() and b_ratios[j] > 0:
                source = prefs[:, starved]
                available = access_inv[:, j, None]
                exclusive = available & (
                    access_inv.sum(axis=1, keepdims=True) == 1
                )
                exclusive_offered = np.where(exclusive, source, 0.0)
                has_exclusive = exclusive_offered.sum(axis=0) > 1e-12
                offered = np.where(available, source, 0.0)
                offered[:, has_exclusive] = exclusive_offered[:, has_exclusive]
                empty = offered.sum(axis=0) <= 1e-12
                if empty.any():
                    fallback_pool = exclusive if exclusive.any() else available
                    ranked = np.broadcast_to(
                        np.where(
                            fallback_pool,
                            fallback_preferences[:, None],
                            0.0,
                        ),
                        offered.shape,
                    )
                    offered[:, empty] = ranked[:, empty]
                useful_lines = line_cap
                if n_inv > useful_lines:
                    top_idx = np.argpartition(
                        offered, -useful_lines, axis=0
                    )[-useful_lines:]
                    limited = np.zeros_like(offered)
                    np.put_along_axis(
                        limited,
                        top_idx,
                        np.take_along_axis(offered, top_idx, axis=0),
                        axis=0,
                    )
                    offered = limited
                fallback_totals = offered.sum(axis=0)
                usable = fallback_totals > 1e-12
                if usable.any():
                    starved_cols = np.flatnonzero(starved)
                    cube[:, j, starved_cols[usable]] = (
                        b_ratios[j]
                        * offered[:, usable]
                        / fallback_totals[usable]
                    )
        return cube

    def _apply_final_caps_cube(
        cube: np.ndarray,
        preferences: np.ndarray,
        iterations: int | None = None,
    ) -> np.ndarray:
        """Applique les plafonds au portefeuille réellement ventilé, PUIS replace
        le cash ainsi libéré sur les lignes qui ont encore de la marge.

        Les deux contraintes doivent être vérifiées après la normalisation des
        budgets broker. Le reliquat n'est laissé en espèces que s'il n'existe
        aucune ligne capable de l'absorber sans violer un plafond.
        """
        alternatives = np.zeros_like(cube)
        for broker_index in range(num_b):
            alternatives[:, broker_index, :] = (
                b_ratios[broker_index]
                * _broker_allocation_batch(preferences, broker_index)
            )
        capped = redeploy_uninvested_cube(
            cube,
            is_etf_inv,
            max_position,
            sector_labels,
            sector_caps,
            b_ratios,
            iterations=(
                int(Config.STARR_CASH_REDEPLOY_PASSES)
                if iterations is None
                else iterations
            ),
            fallback_basis=alternatives,
            max_lines=broker_hard_line_caps,
            sector_matrix=(sector_mat if sector_exposures_by_ticker else None),
            sector_names=sector_names,
        )
        # Après normalisation et plafonds, une préférence initialement grande
        # peut devenir une micro-ligne réelle. On la retire du portefeuille
        # effectivement scoré, puis on redéploie uniquement sur les lignes
        # significatives déjà ouvertes.
        if min_position > 0:
            small = (capped > 1e-12) & (capped < min_position - 1e-12)
            if small.any():
                before = capped
                capped = capped.copy()
                capped[small] = 0.0
                # FILET : un broker dont TOUTES les lignes étaient des
                # micro-lignes se retrouve vide, et le redéploiement ci-dessous
                # ne peut rien y faire — il n'alimente que les lignes ENCORE
                # ouvertes. Son budget disparaissait alors en silence (#bug :
                # Trading212 entièrement non investi). On lui restitue sa
                # meilleure ligne : mieux vaut une ligne sous le plancher qu'un
                # budget évaporé, et le plafond de capacité rend ce cas rare.
                emptied = (capped.sum(axis=0) <= 1e-12) & (before.sum(axis=0) > 1e-12)
                if emptied.any():
                    brokers, candidates = np.nonzero(emptied)
                    best = np.argmax(before[:, brokers, candidates], axis=0)
                    capped[best, brokers, candidates] = before[
                        best, brokers, candidates
                    ]
                capped = redeploy_uninvested_cube(
                    capped,
                    is_etf_inv,
                    max_position,
                    sector_labels,
                    sector_caps,
                    b_ratios,
                    iterations=(
                        int(Config.STARR_CASH_REDEPLOY_PASSES)
                        if iterations is None
                        else int(iterations)
                    ),
                    max_lines=broker_hard_line_caps,
                    sector_matrix=(
                        sector_mat if sector_exposures_by_ticker else None
                    ),
                    sector_names=sector_names,
                )
        return capped

    def _deploy_batch(
        X: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convertit des préférences ticker en portefeuilles RÉELLEMENT déployés.

        Le STARR doit porter sur la somme des allocations par broker après
        disponibilité et budgets, pas sur le vecteur théorique qui les précède.
        Retourne les poids globaux déployés [ticker × candidat] et le nombre de
        lignes réellement détenues [broker × candidat].
        """
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        deployed = np.zeros_like(X, dtype=float)
        counts = np.zeros((num_b, X.shape[1]), dtype=float)
        annual_costs = np.zeros(X.shape[1], dtype=float)
        positive = np.maximum(X, 0.0)
        totals = positive.sum(axis=0)
        valid = totals > 1e-12
        preferences = np.zeros_like(positive)
        preferences[:, valid] = positive[:, valid] / totals[valid]
        if world_floor > 0 and world_mask.any():
            current = preferences[world_mask].sum(axis=0)
            missing = current < world_floor - 1e-12
            if missing.any():
                non_world = ~world_mask
                for column in np.flatnonzero(missing):
                    have = float(current[column])
                    if have > 1e-12:
                        preferences[world_mask, column] *= world_floor / have
                    else:
                        preferences[world_mask, column] = world_floor / int(world_mask.sum())
                    other = float(preferences[non_world, column].sum())
                    if other > 1e-12:
                        preferences[non_world, column] *= (1.0 - world_floor) / other
                    else:
                        preferences[non_world, column] = 0.0
        broker_cube = _apply_final_caps_cube(
            _split_budget_batch(preferences),
            preferences,
        )
        deployed = broker_cube.sum(axis=1)
        for j in range(num_b):
            broker_weights = broker_cube[:, j, :]
            counts[j] = (broker_weights > 1e-12).sum(axis=0)
            if transaction_costs_enabled:
                signed_orders = (
                    broker_weights - current_broker_weights[:, j, None]
                ) * total_cap
                trade_fraction = transaction_cost_model.trade_costs_eur(
                    active_brokers[j], signed_orders
                ) / total_cap
                holding_fraction = transaction_cost_model.annual_holding_cost(
                    active_brokers[j], broker_weights
                )
                annual_costs += (
                    trade_fraction * trade_cost_multiplier
                    + holding_fraction
                )
        return deployed, counts, annual_costs

    def _deploy_one(
        preferences: np.ndarray,
        *,
        iterations: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Version unitaire retournant aussi la matrice ticker × broker."""
        raw = np.maximum(np.asarray(preferences, dtype=float), 0.0)
        total = float(raw.sum())
        normalized = raw / total if total > 1e-12 else raw
        if world_floor > 0 and world_mask.any() and float(normalized[world_mask].sum()) < world_floor:
            have = float(normalized[world_mask].sum())
            if have > 1e-12:
                normalized[world_mask] *= world_floor / have
            else:
                normalized[world_mask] = world_floor / int(world_mask.sum())
            other = float(normalized[~world_mask].sum())
            if other > 1e-12:
                normalized[~world_mask] *= (1.0 - world_floor) / other
        # Solution retenue (pas un candidat de génération) : on s'autorise
        # beaucoup plus de passes de redéploiement, le coût est négligeable.
        broker_weights = _apply_final_caps_cube(
            _split_budget_batch(normalized[:, None]),
            normalized[:, None],
            iterations=(
                int(Config.STARR_CASH_REDEPLOY_PASSES_FINAL)
                if iterations is None
                else int(iterations)
            ),
        )[:, :, 0]
        deployed = broker_weights.sum(axis=1)
        return deployed, broker_weights

    def _portfolio_cost_details(broker_weights: np.ndarray) -> dict:
        """Coût de la cible par rapport aux positions courantes, par broker."""
        per_broker = []
        trade_total = 0.0
        holding_total = 0.0
        if transaction_costs_enabled:
            for j, broker in enumerate(active_brokers):
                signed_orders = (
                    broker_weights[:, j] - current_broker_weights[:, j]
                ) * total_cap
                trade_eur = float(
                    transaction_cost_model.trade_costs_eur(broker, signed_orders)[0]
                )
                holding_fraction = float(
                    transaction_cost_model.annual_holding_cost(
                        broker, broker_weights[:, j]
                    )[0]
                )
                holding_eur = holding_fraction * total_cap
                trade_total += trade_eur
                holding_total += holding_eur
                per_broker.append({
                    "broker": broker,
                    "trade_cost_eur": trade_eur,
                    "annual_custody_eur": holding_eur,
                })
        summary = first_year_cost_summary(trade_total, holding_total, total_cap)
        return {
            "enabled": transaction_costs_enabled,
            "trade_cost_eur": trade_total,
            "trade_cost_pct": trade_total / total_cap,
            "annual_custody_eur": holding_total,
            **summary,
            # Alias de compatibilité pendant la transition de l'API.
            "annualized_cost_eur": summary["first_year_cost_eur"],
            "annualized_cost_pct": summary["first_year_cost_pct"],
            "rebalances_per_year": int(Config.REBALANCES_PER_YEAR),
            "trade_cost_multiplier": trade_cost_multiplier,
            "current_positions_source": (
                "positions_by_broker" if has_real_broker_holdings
                else "legacy_reconstructed"
            ),
            "brokers": per_broker,
        }

    def _penalties_split(
        deployed: np.ndarray, counts: np.ndarray, ok: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Pénalités par candidat retenu, séparées en (autres, look-through).

        La part look-through (plancher défensif + plafond pays) est rendue à part
        parce qu'elle sert DEUX fois : elle s'ajoute au score des candidats
        admissibles (où elle vaut zéro par construction), et surtout elle gradue
        l'énergie sentinelle des candidats INADMISSIBLES. Sans cette séparation,
        tous les infaisables recevaient exactement 1e6 : un plateau parfaitement
        plat, sur lequel le DE n'a aucune direction de descente vers la zone
        admissible. Il ne pouvait qu'y tomber par hasard.
        """
        W = deployed[:, ok]
        pen = np.zeros(W.shape[1])
        pen_lookthrough = np.zeros(W.shape[1])
        # Cash résiduel : le capital non investi ne rapporte rien mais ne coûtait
        # rien à l'objectif (il réduit aussi le risque), donc le DE pouvait
        # préférer un panier qui sature un secteur et laisse 10 % en espèces.
        # Malus quadratique sur l'écart au capital totalement déployé.
        if cash_pen_k > 0:
            idle = np.maximum(deployable_total - W.sum(axis=0), 0.0)
            pen += cash_pen_k * idle * idle
        if card_beta > 0:
            # Seuil PROPRE À CHAQUE BROKER : min(capacité, 20). Les malus se
            # CUMULENT ensuite d'un broker à l'autre — chacun mesuré par rapport
            # à son propre seuil — d'où le `.sum(axis=0)`.
            excess = counts[:, ok] - broker_line_caps[:, None]
            pen += np.where(
                excess > 0, np.exp(np.minimum(card_beta * excess, 700.0)) - 1.0, 0.0
            ).sum(axis=0)
        if world_floor > 0 and world_mask.any():
            short = np.maximum(world_floor - W[world_mask].sum(axis=0), 0.0)
            pen += pen_k * short * short
        # Contraintes look-through (défensif / pays). Si elles empêchent toute
        # initialisation admissible (notamment un PEA concentré sur un ETF monde),
        # la seconde passe les désactive, mais conserve les autres règles telles
        # que la cardinalité par broker.
        if use_lookthrough_constraints:
            if len(d_vec) and float(np.max(d_vec)) > 0:
                short = np.maximum(min_def - (d_vec @ W), 0.0)
                pen_lookthrough += pen_k * short * short
            if country_hard_cap_enabled and C_mat.size:
                over = np.maximum((C_mat.T @ W) - max_country, 0.0)
                pen_lookthrough += pen_k * np.sum(over * over, axis=0)
        if region_hard_cap_enabled:
            over = np.maximum((R_mat.T @ W) - max_region, 0.0)
            pen += pen_k * np.sum(over * over, axis=0)
        return pen, pen_lookthrough

    def _penalties_batch(deployed: np.ndarray, counts: np.ndarray, ok: np.ndarray) -> np.ndarray:
        """Somme de TOUTES les pénalités de contrainte, par candidat retenu.

        Réutilisée telle quelle par la recherche du point de départ, qui a besoin
        de savoir si un candidat est ADMISSIBLE (pénalité nulle) indépendamment
        de son score.
        """
        pen, pen_lookthrough = _penalties_split(deployed, counts, ok)
        return pen + pen_lookthrough

    def _penalty_breakdown(deployed: np.ndarray, counts: np.ndarray) -> dict:
        """Détaille, terme par terme, la pénalité d'UN portefeuille déployé.

        L'objectif additionne des malus d'échelles très différentes (cash à
        plusieurs centaines de points, cardinalité exponentielle, look-through
        quadratique). Sans cette ventilation, impossible de savoir lequel pilote
        réellement l'allocation retenue — ni de repérer un coefficient devenu
        dominant après un changement de réglage.
        """
        W = deployed.reshape(deployed.shape[0], -1)[:, :1]
        detail: dict[str, float] = {}
        idle = float(max(deployable_total - float(W.sum()), 0.0))
        detail["cash_oisif"] = float(cash_pen_k * idle * idle) if cash_pen_k > 0 else 0.0
        if card_beta > 0:
            excess = counts.reshape(counts.shape[0], -1)[:, :1] - broker_line_caps[:, None]
            detail["lignes_par_broker"] = float(
                np.where(
                    excess > 0,
                    np.exp(np.minimum(card_beta * excess, 700.0)) - 1.0,
                    0.0,
                ).sum()
            )
        else:
            detail["lignes_par_broker"] = 0.0
        detail["plancher_defensif"] = 0.0
        detail["plafond_pays"] = 0.0
        detail["plafond_region"] = 0.0
        detail["composition_actions_inconnue"] = 0.0
        if use_lookthrough_constraints:
            if len(d_vec) and float(np.max(d_vec)) > 0:
                # `d_vec @ W` renvoie un vecteur (1,) : NumPy 2 refuse float()
                # sur un tableau non scalaire, d'où l'agrégation explicite.
                defensive_share = float(np.asarray(d_vec @ W).ravel()[0])
                short = max(min_def - defensive_share, 0.0)
                detail["plancher_defensif"] = float(pen_k * short * short)
            if country_hard_cap_enabled and C_mat.size:
                over = np.maximum((C_mat.T @ W) - max_country, 0.0)
                detail["plafond_pays"] = float(pen_k * np.sum(over * over))
        if region_hard_cap_enabled:
            over = np.maximum((R_mat.T @ W) - max_region, 0.0)
            detail["plafond_region"] = float(pen_k * np.sum(over * over))
        detail["cash_non_deploye_pct"] = idle
        return detail

    def _sector_country_diversification_batch(
        W: np.ndarray,
        eligible_sectors: np.ndarray | None = None,
    ) -> np.ndarray:
        """Bonus de pays fondé sur les couples secteur-pays exacts.

        Le score combine le logarithme du nombre effectif de pays et celui du
        nombre de pays significatifs. Les pays inconnus ne peuvent pas augmenter
        le score ; leur part réduit au contraire la couverture connue.
        """
        score = np.zeros(W.shape[1], dtype=float)
        if not C_mat.size or not joint_mat.size:
            return score
        unknown = np.asarray([
            str(country).casefold() in {"inconnu", "unknown", "autres", "other"}
            for country in all_countries
        ], dtype=bool)
        for sector_index in range(joint_mat.shape[1]):
            buckets = joint_mat[:, sector_index, :].T @ W
            exposure = buckets.sum(axis=0)
            valid = exposure > 1e-12
            if not valid.any():
                continue
            contribution = country_diversification_score_from_buckets(
                buckets[:, valid],
                unknown,
                significant_exposure=sector_country_significant_exposure,
                significant_weight=sector_country_significant_weight,
            )
            if eligible_sectors is not None:
                contribution *= eligible_sectors[sector_index, valid]
            score[valid] += contribution
        return score

    def _sector_country_deficit_batch(W: np.ndarray) -> np.ndarray:
        """Malus vectorisé de déficit en pays effectifs, secteurs connus seuls."""
        out = np.zeros(W.shape[1], dtype=float)
        coefficient = sector_country_deficit_penalty_coefficient
        if coefficient <= 0 or not C_mat.size or not joint_mat.size:
            return out
        medium = max(float(Config.STARR_SECTOR_COUNTRY_MEDIUM_EXPOSURE), 0.0)
        large = max(float(Config.STARR_SECTOR_COUNTRY_LARGE_EXPOSURE), medium)
        unknown = np.asarray([
            str(country).casefold() in {"inconnu", "unknown", "autres", "other"}
            for country in all_countries
        ], dtype=bool)
        for sector_index in range(sector_mat.shape[1]):
            buckets = joint_mat[:, sector_index, :].T @ W
            exposure = buckets.sum(axis=0)
            valid = exposure >= medium
            if not valid.any():
                continue
            shares = buckets[:, valid] / np.maximum(exposure[valid], 1e-12)
            hhi = (
                np.sum(shares[~unknown] * shares[~unknown], axis=0)
                + np.sum(shares[unknown], axis=0)
            )
            effective = 1.0 / np.maximum(hhi, 1e-12)
            target = np.where(exposure[valid] >= large, 3.0, 2.0)
            deficit = np.maximum(target - effective, 0.0) / target
            out[valid] += coefficient * exposure[valid] * deficit * deficit
        return out

    def _geographic_diversification_batch(W: np.ndarray) -> np.ndarray:
        """Bonus global pays × régions × nombre de pays significatifs."""
        if geographic_bonus <= 0 or not C_mat.size or not R_mat.size:
            return np.zeros(W.shape[1], dtype=float)
        factors = geographic_diversification_factors(
            C_mat.T @ W,
            R_mat.T @ W,
            country_names=all_countries,
            region_names=all_regions,
            significant_exposure=sector_country_significant_exposure,
            country_std_exponent=geographic_country_std_exponent,
            region_std_exponent=geographic_region_std_exponent,
        )
        return factors["combined"]

    def _diversification_adjustment_batch(
        deployed: np.ndarray,
        ok: np.ndarray,
        eligible_sectors: np.ndarray,
    ) -> np.ndarray:
        """Bonus géographique, hors portefeuilles trop risqués sectoriellement.

        Cet ajustement est volontairement séparé de ``_penalties_batch`` : les
        préférences de diversification restent souples et ne peuvent pas rendre
        un seed infaisable. Aucun nombre minimal de lignes ni aucune concentration
        propre à un broker n'est récompensé/pénalisé : seul le risque GLOBAL
        compte. Le bonus pays est supprimé si un secteur dépasse son budget de
        risque, afin qu'il ne puisse jamais compenser ce dépassement.
        """
        adjustment = np.zeros(int(np.sum(ok)), dtype=float)
        if sector_country_bonus > 0:
            raw_bonus = (
                sector_country_bonus
                * _sector_country_diversification_batch(
                    deployed[:, ok], eligible_sectors[:, ok]
                )
            )
            adjustment -= raw_bonus
        if geographic_bonus > 0:
            adjustment -= geographic_bonus * _geographic_diversification_batch(
                deployed[:, ok]
            )
        adjustment += _sector_country_deficit_batch(deployed[:, ok])
        return adjustment

    def _lookthrough_feasible_batch(deployed: np.ndarray) -> np.ndarray:
        """Faisabilite pays/defensif sur les poids reellement deployes."""
        feasible = np.ones(deployed.shape[1], dtype=bool)
        if use_lookthrough_constraints:
            if len(d_vec) and float(np.max(d_vec)) > 0:
                feasible &= (d_vec @ deployed) >= min_def - 1e-9
            if country_hard_cap_enabled and C_mat.size:
                feasible &= np.all(
                    (C_mat.T @ deployed) <= max_country + 1e-9,
                    axis=0,
                )
        if region_hard_cap_enabled:
            feasible &= exposure_cap_feasible(R_mat, deployed, max_region)
        if world_floor > 0 and world_mask.any():
            feasible &= world_mask.astype(float) @ deployed >= world_floor - 1e-9
        if direct_action_min_weight > 0:
            feasible &= (
                direct_action_mask.astype(float) @ deployed
                >= direct_action_min_weight - 1e-9
            )
        if direct_action_min_lines > 0:
            direct_lines = np.sum(
                deployed[direct_action_mask] >= max(min_position, 1e-12), axis=0
            )
            feasible &= direct_lines >= direct_action_min_lines
        return feasible

    def _objective_for_deployed_batch(
        deployed: np.ndarray,
        counts: np.ndarray,
        annual_costs: np.ndarray,
        ok: np.ndarray,
    ) -> np.ndarray:
        """Même objectif sur les poids déployés, continus ou exécutables."""
        base, risk_context = benchmark_relative_batch_details(
            deployed, sim_search, mean_daily, bench, alpha, downside_weight,
            annual_costs=annual_costs,
            normalize_weights=False,
        )
        if direct_action_quality_bonus > 0 and np.any(direct_action_quality):
            base -= direct_action_quality_bonus * (direct_action_quality @ deployed)
        # Une colonne par secteur économique + le résidu non renseigné. Un
        # dépassement coupe uniquement le bonus de SON secteur, jamais celui des
        # autres poches géographiquement saines.
        sector_bonus_eligible = np.ones(
            (sector_mat.shape[1], deployed.shape[1]), dtype=float
        )
        risk_valid = np.asarray(risk_context["valid"], dtype=bool)
        if risk_valid.any() and sector_mat.shape[1]:
            risk_details = sector_downside_risk_from_context(
                sim_search,
                sector_labels,
                risk_context,
                downside_weight=downside_weight,
                sector_matrix=sector_mat,
                sector_names=sector_names,
            )
            risk_penalty, risk_exceeded = sector_downside_risk_penalty(
                risk_details,
                max_risk_share=sector_risk_caps,
                coefficient=sector_risk_penalties,
            )
            base[risk_valid] += risk_penalty
            shares = np.asarray(risk_details["risk_shares"], dtype=float)
            sector_bonus_eligible[:sector_mat.shape[1], risk_valid] = (
                shares[:, risk_valid]
                <= sector_risk_caps[:, None] + 1e-12
            )
        # Même budget de risque, appliqué aux PAYS. La fonction est générique :
        # on lui passe la matrice d'exposition géographique au lieu de la
        # matrice sectorielle. Les deux budgets se cumulent sans arbitrage,
        # chaque axe décrivant l'intégralité du portefeuille.
        if (
            risk_valid.any()
            and C_mat_risk.shape[1]
            and max_country_risk_share > 0
            and country_risk_penalty_coefficient > 0
        ):
            country_risk_details = sector_downside_risk_from_context(
                sim_search,
                [None] * len(inv_tickers),
                risk_context,
                downside_weight=downside_weight,
                sector_matrix=C_mat_risk,
                sector_names=risk_countries,
            )
            country_penalty, _ = sector_downside_risk_penalty(
                country_risk_details,
                max_risk_share=max_country_risk_share,
                coefficient=country_risk_penalty_coefficient,
            )
            base[risk_valid] += country_penalty
        if (
            risk_valid.any()
            and R_mat.shape[1]
            and max_region_risk_share > 0
            and region_risk_penalty_coefficient > 0
        ):
            region_risk_details = sector_downside_risk_from_context(
                sim_search,
                [None] * len(inv_tickers),
                risk_context,
                downside_weight=downside_weight,
                sector_matrix=R_mat,
                sector_names=all_regions,
            )
            region_penalty, _ = sector_downside_risk_penalty(
                region_risk_details,
                max_risk_share=max_region_risk_share,
                coefficient=region_risk_penalty_coefficient,
            )
            base[risk_valid] += region_penalty
        pen_lookthrough = np.zeros(int(np.sum(ok)), dtype=float)
        if ok.any():
            pen_other, pen_lookthrough = _penalties_split(deployed, counts, ok)
            base[ok] += pen_other + pen_lookthrough
            base[ok] += _diversification_adjustment_batch(
                deployed,
                ok,
                sector_bonus_eligible,
            )
        # Les contraintes look-through restent LEXICOGRAPHIQUES : un portefeuille
        # pays/defensif non conforme ne peut pas acheter un meilleur score STARR
        # en payant simplement un petit malus -- tout candidat faisable reste tres
        # loin sous 1e6. Mais la sentinelle est GRADUEE par la penalite, au lieu
        # d'etre un plateau plat : les infaisables sont ainsi ordonnes par leur
        # distance a la faisabilite, ce qui donne enfin au DE une direction de
        # descente vers la zone admissible. Le plateau plat expliquait qu'il faille
        # jusqu'a 51 200 tirages aleatoires pour trouver un point de depart.
        # `find_positive_random_seed` reste correct : son test
        # `energies < INVALID_OBJECTIVE_ENERGY` exclut toujours ces candidats,
        # dont l'energie ne peut que croitre.
        if use_lookthrough_constraints and ok.any():
            constraint_ok = _lookthrough_feasible_batch(deployed)
            infeasible = ok & ~constraint_ok
            if infeasible.any():
                graded = np.zeros(deployed.shape[1], dtype=float)
                graded[ok] = pen_lookthrough
                base[infeasible] = INVALID_OBJECTIVE_ENERGY + graded[infeasible]
        base[~ok] = INVALID_OBJECTIVE_ENERGY
        return base

    def neg_obj_batch(X: np.ndarray) -> np.ndarray:
        """Objectif pénalisé vectorisé, avec déploiement broker identique au final."""
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        positive = np.maximum(X, 0.0)
        deployed, counts, annual_costs = _deploy_batch(positive)
        return _objective_for_deployed_batch(
            deployed, counts, annual_costs, positive.sum(axis=0) > 1e-12
        )

    def _score_for_display(
        energy: float | None,
        vector: np.ndarray | None = None,
    ) -> float | None:
        """Retourne un score STARR affichable, jamais la sentinelle interne.

        Les contraintes look-through sont lexicographiques dans l'optimiseur :
        une solution infaisable reçoit une énergie proche de 1e6 afin qu'elle ne
        puisse pas battre une solution faisable. Cette énergie n'est pas un score
        financier. Pour la progression, on réévalue donc le même portefeuille
        sans le verrou lexicographique et on affiche son score réel pénalisé par
        les coûts/risques souples. La sentinelle reste utilisée en interne pour
        le classement et la faisabilité.
        """
        nonlocal use_lookthrough_constraints
        if energy is None or not np.isfinite(float(energy)):
            return None
        value = float(energy)
        if value < INVALID_OBJECTIVE_ENERGY:
            return -value
        if vector is None:
            return None
        saved = use_lookthrough_constraints
        try:
            # Ne pas transformer une contrainte dure en simple malus dans le DE :
            # ce mode n'est utilisé que pour informer l'interface.
            use_lookthrough_constraints = False
            raw_energy = float(
                neg_obj_batch(np.asarray(vector, dtype=float)[:, None])[0]
            )
        finally:
            use_lookthrough_constraints = saved
        if np.isfinite(raw_energy) and raw_energy < INVALID_OBJECTIVE_ENERGY:
            return -raw_energy
        return None

    def feasible_batch(X: np.ndarray) -> np.ndarray:
        """Masque des candidats qui respectent TOUTES les contraintes.

        Sert de critère d'admissibilité au point de départ du DE : exiger un score
        positif reviendrait, depuis que le score mesure l'écart au benchmark, à
        demander au tirage aléatoire de battre déjà CW8.PA.
        """
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        Xp = np.maximum(X, 0.0)
        ok = Xp.sum(axis=0) > 1e-12
        out = np.zeros(X.shape[1], dtype=bool)
        if not ok.any():
            return out
        deployed, _, _ = _deploy_batch(Xp)
        # ``_penalties_batch`` also contains soft objective terms (cash
        # résiduel and cardinalité). They must not
        # decide whether a random point can seed the DE: doing so rejected
        # almost every sparse population and falsely reported no feasible
        # portfolio after the look-through constraints had been relaxed.
        out[ok] = _lookthrough_feasible_batch(deployed[:, ok])
        return out

    def neg_obj(x: np.ndarray) -> float:
        """Version scalaire (polish Nelder-Mead) — mêmes numériques que le batch."""
        return float(neg_obj_batch(np.asarray(x, dtype=float)[:, None])[0])

    # ── Population initiale SPARSE : partir de portefeuilles concentrés déjà
    # bons — dont « 1 seul ETF monde » — plutôt que du latin hypercube qui
    # pondère tout l'univers à la fois (STARR de départ médiocre + malus de
    # cardinalité, et population scipy de popsize×n individus).
    scores = ticker_standalone_scores(sim_search, mean_daily, alpha, downside_weight)
    # Matrice de guidage bon marche pour la reconstruction des supports. Le
    # score final reste exclusivement celui de l'objectif complet ; cette
    # matrice sert seulement a proposer des ajouts moins redondants que le hasard.
    search_corr = np.atleast_2d(np.corrcoef(R_inv[-len(R_mean):], rowvar=False))
    search_corr = np.nan_to_num(search_corr, nan=0.75, posinf=0.75, neginf=-0.75)
    shrink = min(max(float(Config.STARR_CORRELATION_SHRINKAGE), 0.0), 1.0)
    search_corr *= 1.0 - shrink
    np.fill_diagonal(search_corr, 1.0)
    standalone_order = np.argsort(scores)[::-1]
    fallback_preferences = np.zeros(n_inv, dtype=float)
    fallback_preferences[standalone_order] = np.arange(n_inv, 0, -1, dtype=float)

    def _estimate_max_achievable_defensive() -> float:
        """Estime le maximum défensif réellement déployable.

        Le plancher est exprimé sur les poids après répartition entre brokers,
        plafonds de lignes, plafonds sectoriels et redéploiement du cash. Un
        simple ``d_vec.sum()`` surestimerait donc fortement ce qui est possible
        dans un univers actions/PEA. Quelques paniers déterministes couvrent les
        cas importants (tous les défensifs, par broker, préfixes et titres
        unitaires) à un coût négligeable devant une génération DE.
        """
        defensive = np.asarray(d_vec, dtype=float).reshape(-1)
        accessible = np.any(np.asarray(access_inv, dtype=bool), axis=1)
        candidates = np.flatnonzero(accessible & (defensive > 1e-12))
        if candidates.size == 0:
            return 0.0

        score_values = np.nan_to_num(
            np.asarray(scores, dtype=float),
            nan=-np.inf,
            posinf=-np.inf,
            neginf=-np.inf,
        )
        order = candidates[
            np.lexsort(
                (
                    -score_values[candidates],
                    -defensive[candidates],
                )
            )
        ]
        probes: list[np.ndarray] = []

        def add_probe(indices: np.ndarray, values: np.ndarray | None = None) -> None:
            selected = np.asarray(indices, dtype=int).reshape(-1)
            if selected.size == 0:
                return
            probe = np.zeros(n_inv, dtype=float)
            if values is None:
                probe[selected] = 1.0
            else:
                probe[selected] = np.maximum(
                    np.asarray(values, dtype=float).reshape(-1),
                    1e-6,
                )
            if float(probe.sum()) > 1e-12:
                probes.append(probe)

        add_probe(candidates, defensive[candidates])
        add_probe(candidates)
        for count in range(1, min(int(order.size), 16) + 1):
            selected = order[:count]
            add_probe(selected, defensive[selected])
            add_probe(selected)
        for index in candidates:
            add_probe(np.asarray([index], dtype=int))
        for broker_index in range(num_b):
            broker_candidates = candidates[access_inv[candidates, broker_index]]
            add_probe(broker_candidates, defensive[broker_candidates])

        if not probes:
            return 0.0
        deployed, _counts, _costs = _deploy_batch(np.column_stack(probes))
        exposure = np.asarray(d_vec @ deployed, dtype=float).reshape(-1)
        finite = exposure[np.isfinite(exposure)]
        return float(np.max(finite)) if finite.size else 0.0

    max_achievable_defensive = _estimate_max_achievable_defensive()
    if (
        use_lookthrough_constraints
        and requested_min_defensive > max_achievable_defensive + 1e-8
        and max_achievable_defensive > 1e-8
    ):
        # Une contrainte dure impossible ne doit ni produire un faux score
        # sentinelle ni forcer le DE à chercher indéfiniment. On conserve le
        # filtre défensif en le ramenant au maximum démontrable par l'exécution
        # courante, avec une marge numérique pour que ce maximum soit faisable.
        min_def = max(
            0.0,
            max_achievable_defensive
            - max(1e-6, requested_min_defensive * 1e-4),
        )
        defensive_floor_relaxed = True
        print(
            "    * ATTENTION : plancher défensif demandé "
            f"{requested_min_defensive:.2%}, maximum atteignable "
            f"{max_achievable_defensive:.2%} avec l'univers, les brokers et "
            f"les plafonds ; recherche limitée à {min_def:.2%}."
        )
    seed_ticker = str(getattr(Config, "STARR_DE_SEED_TICKER", "") or "").strip().upper()
    if seed_ticker and seed_ticker in inv_tickers:
        seed_pos: int | None = inv_tickers.index(seed_ticker)
    elif is_etf_inv.any():
        etf_pos = np.flatnonzero(is_etf_inv)
        seed_pos = int(etf_pos[np.argmax(scores[etf_pos])])
    else:
        seed_pos = int(np.argmax(scores)) if len(scores) else None

    init_batch_size = int(Config.STARR_DE_POSITIVE_INIT_BATCH_SIZE)
    init_max_batches = int(Config.STARR_DE_POSITIVE_INIT_MAX_BATCHES)

    def _find_positive_seed(search_seed: int, *, use_previous: bool = False):
        if use_previous and has_previous_champion:
            return (
                champion_inv.copy(),
                float(previous_champion_score),
                0,
            )
        return find_positive_random_seed(
            n_inv,
            np.random.default_rng(search_seed),
            neg_obj_batch,
            batch_size=init_batch_size,
            max_batches=init_max_batches,
            progress_cb=initialization_cb,
            should_stop=should_stop,
            feasible=feasible_batch,
        )

    previous_champion_energy: float | None = None
    previous_champion_score: float | None = None
    previous_champion_display_score: float | None = None
    previous_champion_accepted = False
    previous_champion_feasible = False
    previous_champion_rejection_reason: str | None = None
    previous_champion_repaired = False
    previous_champion_repair_score: float | None = None
    if has_previous_champion:
        candidate_energy = float(neg_obj_batch(champion_inv[:, None])[0])
        candidate_feasible = bool(feasible_batch(champion_inv[:, None])[0])
        previous_champion_accepted = True
        previous_champion_feasible = candidate_feasible
        if np.isfinite(candidate_energy):
            previous_champion_energy = candidate_energy
            previous_champion_score = -candidate_energy
            previous_champion_display_score = _score_for_display(
                candidate_energy,
                champion_inv,
            )
        else:
            previous_champion_energy = float(INVALID_OBJECTIVE_ENERGY)
            previous_champion_score = -float(INVALID_OBJECTIVE_ENERGY)
            previous_champion_rejection_reason = "objectif_non_fini"
        if candidate_energy >= INVALID_OBJECTIVE_ENERGY:
            previous_champion_rejection_reason = "objectif_invalide"
        elif not candidate_feasible:
            previous_champion_rejection_reason = "contraintes_courantes"
    _prep(
        "Champion précédent : "
        f"poids reçu={champion_input_total:.1%}, "
        f"poids investissable={champion_retained_total:.1%}, "
        f"titres investissables={int(np.count_nonzero(champion_inv > 1e-12))}…"
    )
    _prep(
        "Réévaluation du meilleur portefeuille du run précédent…"
        if previous_champion_accepted
        else "Recherche d'un portefeuille de départ admissible…"
    )
    if not previous_champion_accepted and champion_input_total > 1e-12:
        raise InvalidOptimizationObjective(
            "Le portefeuille précédent a été fourni mais aucun de ses titres "
            "n'est investissable dans l'univers courant après les filtres "
            f"(poids reçu={champion_input_total:.4f}, "
            f"poids investissable={champion_retained_total:.4f}). "
            "Recherche aléatoire interdite : vérifier l'accès broker et "
            "l'historique de cours des titres du portefeuille précédent."
        )
    try:
        positive_seed, positive_score, positive_batch = _find_positive_seed(
            seed,
            use_previous=True,
        )
    except InvalidOptimizationObjective as exc:
        probe = np.zeros(n_inv, dtype=float)
        if seed_pos is not None:
            probe[seed_pos] = 1.0
        else:
            probe[:] = 1.0
        deployed_probe, _, costs_probe = _deploy_batch(probe[:, None])
        probe_energy = float(neg_obj_batch(probe[:, None])[0])
        bench_values = np.asarray(list(bench.values()), dtype=float)
        raise InvalidOptimizationObjective(
            "Optimisation impossible : l'objectif STARR est non fini. "
            f"simulation_finie={bool(np.isfinite(sim_search).all())}, "
            f"moyennes_finies={bool(np.isfinite(mean_daily).all())}, "
            f"benchmark_fini={bool(np.isfinite(bench_values).all())}, "
            f"poids_deployes={float(deployed_probe.sum()):.6f}, "
            f"cout_annuel_fini={bool(np.isfinite(costs_probe).all())}, "
            f"energie_test={probe_energy:.6g}. "
            "Aucun seed supplémentaire n'a été lancé."
        ) from exc
    except PositiveSeedNotFound as first_exc:
        if actions_only_universe:
            # En mode actions seules, la géographie est volontairement libre,
            # mais le minimum défensif reste obligatoire.
            raise PositiveSeedNotFound(
                "Aucun portefeuille admissible trouvé avec le plancher "
                f"défensif de {min_def:.0%} en mode sans ETF ; "
                "la contrainte défensive n'a pas été relâchée."
            ) from first_exc
        use_lookthrough_constraints = False
        print(
            "    * Aucun portefeuille admissible avec les contraintes look-through; "
            "nouvelle tentative sans minimum defensif ni plafond par pays."
        )
        print(
            f"    * ATTENTION : contraintes relachees -- defensif >= "
            f"{float(Config.MIN_DEFENSIVE_PCT):.0%} et plafond pays "
            f"{float(Config.MAX_COUNTRY_PCT):.0%} ne sont PLUS appliques. "
            "Verifier les plafonds sectoriels et la profondeur de l'univers defensif."
        )
        try:
            positive_seed, positive_score, positive_batch = _find_positive_seed(seed + 1)
        except PositiveSeedNotFound as exc:
            tested = init_batch_size * init_max_batches
            raise PositiveSeedNotFound(
                "Aucun portefeuille admissible trouvé, même sans minimum "
                f"défensif ni plafond par pays, après {tested:,} nouveaux essais aléatoires."
            ) from exc
    if previous_champion_accepted:
        print(
            "    * Champion du run précédent réévalué : "
            f"score={previous_champion_display_score:.5f} "
            "(nouveaux cours, risques et contraintes)"
            if previous_champion_display_score is not None
            else "    * Champion du run précédent réévalué : score indisponible"
        )
    else:
        print(
            "    * Initialisation admissible : "
            f"score={positive_score:.5f}, trouvé au lot aléatoire #{positive_batch}"
        )

    def _report(
        seed_num: int,
        iteration: int,
        convergence: float,
        seed_score: float,
        global_best_score: float,
        temperature: float | None = None,
        forced_labels: list[str] | None = None,
        forced_action_count: int | None = None,
        forced_etf_count: int | None = None,
        seed_vector: np.ndarray | None = None,
        global_vector: np.ndarray | None = None,
    ) -> None:
        def _display_report_score(
            score: float,
            vector: np.ndarray | None,
        ) -> float | None:
            if not np.isfinite(float(score)):
                return None
            # Les appels historiques transmettent un score (= -énergie), alors
            # que `_score_for_display` reçoit l'énergie interne.
            if float(score) > -INVALID_OBJECTIVE_ENERGY:
                return float(score)
            return _score_for_display(-float(score), vector)

        display_seed_score = _display_report_score(seed_score, seed_vector)
        display_global_score = _display_report_score(
            global_best_score,
            global_vector,
        )
        if progress_cb is not None:
            try:
                progress_cb(
                    seed_num,
                    iteration,
                    float(convergence),
                    display_global_score,
                    seed_score=display_seed_score,
                    temperature=(
                        None if temperature is None else float(temperature)
                    ),
                    forced_labels=forced_labels,
                    forced_action_count=forced_action_count,
                    forced_etf_count=forced_etf_count,
                )
            except TypeError:
                pass
            else:
                return
            # Repli en cascade : un appelant qui ne connait pas encore les
            # libelles forces peut tout de meme conserver la temperature.
            try:
                progress_cb(
                    seed_num,
                    iteration,
                    float(convergence),
                    display_global_score,
                    seed_score=display_seed_score,
                    temperature=(
                        None if temperature is None else float(temperature)
                    ),
                )
                return
            except TypeError:
                try:
                    progress_cb(
                        seed_num,
                        iteration,
                        float(convergence),
                        display_global_score,
                        seed_score=display_seed_score,
                    )
                    return
                except TypeError:
                    # Compatibilité avec les callbacks externes/tests à quatre
                    # paramètres créés avant l'historique multi-seed.
                    progress_cb(
                        seed_num,
                        iteration,
                        float(convergence),
                        display_global_score,
                    )
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation

    max_gen = int(
        Config.STARR_DE_MAX_GENERATIONS
        if max_generations is None
        else max(1, max_generations)
    )  # garde-fou, pas l'arrêt normal
    de_tol = float(Config.STARR_DE_TOL)
    min_improvement = max(0.0, float(Config.STARR_DE_MIN_IMPROVEMENT))

    # ── Conversion vecteur DE brut -> allocation par broker, réutilisée pour le
    # résultat final ET les mises à jour progressives (on_new_best). Il est
    # essentiel d'utiliser exactement le meme deploiement que dans l'objectif :
    # seuil minimum, cardinalite, disponibilites, plafonds et frais portent ainsi
    # sur le portefeuille effectivement retourne. Une projection SLSQP finale sur
    # tout l'univers contournait ces garde-fous et creait des centaines de lignes.
    def _to_broker_matrix(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = np.maximum(x, 0.0)
        s = raw.sum()
        w_inv = raw / s if s > 0 else raw
        deployed_inv, W_inv = _deploy_one(w_inv)
        if not bool(_lookthrough_feasible_batch(deployed_inv[:, None])[0]):
            # Les passes finales de redéploiement peuvent déplacer quelques
            # décimales de plus que les passes utilisées pendant la recherche.
            # Revenir au mapping effectivement validé par le DE préserve alors
            # la contrainte hard sans aucune projection dense post-hoc.
            deployed_inv, W_inv = _deploy_one(
                w_inv,
                iterations=int(Config.STARR_CASH_REDEPLOY_PASSES),
            )
        W = np.zeros((num_t, num_b), dtype=float)
        W[inv_idx, :] = W_inv
        return deployed_inv, W

    def _evaluate_executable_matrix(W_candidate: np.ndarray) -> dict | None:
        """Évalue une seule discrétisation, sans renormaliser le cash résiduel."""
        if discretize_cb is None:
            return None
        try:
            executable = np.asarray(discretize_cb(W_candidate), dtype=float)
        except Exception as exc:
            print(f"    * Score exécutable indisponible : {exc}")
            return None
        if (
            executable.shape != (num_t, num_b)
            or not np.isfinite(executable).all()
            or np.any(executable < -1e-12)
        ):
            print("    * Score exécutable ignoré : matrice invalide.")
            return None
        broker_weights = executable[inv_idx, :]
        deployed = broker_weights.sum(axis=1)
        counts = (broker_weights > 1e-12).sum(axis=0).reshape(-1, 1)
        costs = _portfolio_cost_details(broker_weights)
        objective_energy = float(_objective_for_deployed_batch(
            deployed[:, None],
            counts,
            np.asarray([costs["first_year_cost_pct"]]),
            np.asarray([bool(deployed.sum() > 1e-12)]),
        )[0])
        feasible = bool(
            deployed.sum() > 1e-12
            and _lookthrough_feasible_batch(deployed[:, None])[0]
            and np.all(executable[~access] <= 1e-12)
            and np.all(executable[~investable] <= 1e-12)
            and np.all(executable.sum(axis=0) <= b_ratios + 1e-9)
            and np.all(counts[:, 0] <= broker_hard_line_caps)
        )
        if 0 < max_position < 1:
            feasible = feasible and bool(
                np.all(deployed[~is_etf_inv] <= max_position + 1e-9)
            )
        if sector_mat.shape[1]:
            sector_limits = sector_caps.as_array(sector_names)
            limited = (sector_limits > 0) & (sector_limits < 1)
            feasible = feasible and bool(np.all(
                (sector_mat.T @ deployed)[limited]
                <= sector_limits[limited] + 1e-9
            ))
        score = -neg_benchmark_relative(
            deployed, sim_rets, mean_daily, bench, alpha, downside_weight,
            annual_cost=costs["first_year_cost_pct"],
            normalize_weights=False,
        )
        return {
            "weights": executable,
            "score": float(score) if np.isfinite(score) else None,
            "objective_score": (
                -objective_energy
                if feasible and np.isfinite(objective_energy)
                and objective_energy < INVALID_OBJECTIVE_ENERGY
                else None
            ),
            "feasible_under_current_constraints": feasible,
        }

    _last_emit_t = 0.0
    _last_candidate_t = 0.0

    def _maybe_emit_progress(x: np.ndarray) -> None:
        nonlocal _last_emit_t
        if on_new_best is None:
            return
        now = time.time()
        if now - _last_emit_t < 2.0:  # throttle : évite le spam DB en tout début de DE
            return
        _last_emit_t = now
        try:
            _, w_matrix = _to_broker_matrix(x)
            on_new_best(w_matrix)
        except Exception:
            pass  # la progression ne doit jamais casser l'optimisation

    def _maybe_emit_candidate(x: np.ndarray) -> None:
        nonlocal _last_candidate_t
        if on_candidate is None:
            return
        now = time.time()
        if now - _last_candidate_t < 5.0:
            return
        _last_candidate_t = now
        try:
            _, w_matrix = _to_broker_matrix(x)
            on_candidate(w_matrix)
        except Exception:
            pass

    # Le DE part obligatoirement d'un portefeuille positif. Cette énergie est
    # partagée entre tous les seeds et ne peut donc jamais régresser sous zéro.
    global_best_energy = -positive_score
    global_best_x = np.asarray(positive_seed, dtype=float).copy()
    # Archive inter-seeds réservée à la validation finale. ``support_archive``
    # est réinitialisée à chaque nouveau départ.
    validation_archive: list[tuple[float, np.ndarray]] = [
        (float(global_best_energy), global_best_x.copy())
    ]

    # ── Seeds illimités : chaque nouveau départ (rng=seed+k, toujours distinct)
    # explore le paysage différemment. On garde le meilleur de tous les seeds
    # faits et on logge l'écart entre eux (mesure de robustesse : si les
    # scores divergent fort d'un seed à l'autre, le paysage a plusieurs optima
    # locaux comparables). should_stop() est consulté entre deux GENERATIONS,
    # mais l'arrêt demandé ne coupe PAS la seed en cours : elle est menée jusqu'à
    # sa fin naturelle (convergence, stagnation ou plafond de générations) pour
    # que le portefeuille retenu soit un optimum abouti, et c'est seulement le
    # lancement d'une seed SUIVANTE qui est annulé. Sans should_stop : 1 seul seed
    # (comportement par défaut sûr, jamais de boucle infinie).
    #
    # Les seeds ALTERNENT deux rôles (cf. seed_mode). Auparavant chacune était
    # warm-startée sur le meilleur x de TOUTES les précédentes : combinée à la
    # stratégie scipy par défaut best1bin, qui mute autour du meilleur individu,
    # la population initiale contenait déjà l'optimum précédent et le solveur y
    # retombait en quelques générations. Plus rien ne progressait après la seed 0.
    stop_requested = False
    restart_requested = False
    de_seed = seed + seed_number_offset
    pop_rng = np.random.default_rng(de_seed)
    seed_label = seed_number_offset + 1

    # Population initiale : le champion précédent réévalué, le portefeuille
    # réellement détenu et les meilleurs candidats d'un large screening
    # aléatoire. Le reste assure la couverture de l'univers —
    # chaque titre doit apparaître dans au moins un individu, sans quoi ses
    # coordonnées nulles le resteraient à jamais (mutation DE = a + F·(b−c)).
    warm_starts: list[np.ndarray] = [positive_seed]
    for candidate in (
        champion_inv if has_previous_champion else None,
        current_inv if has_current_weights else None,
    ):
        if candidate is not None and not any(
            np.allclose(candidate, existing, atol=1e-12, rtol=0.0)
            for existing in warm_starts
        ):
            warm_starts.append(candidate.copy())
    elites = sample_elite_seeds(
        n_inv,
        pop_rng,
        neg_obj_batch,
        batch_size=init_batch_size,
        max_batches=int(Config.STARR_DE_ELITE_BATCHES),
        n_elites=int(Config.STARR_DE_ELITE_COUNT),
        feasible=feasible_batch,
        should_stop=should_stop,
    )
    if elites:
        elite_scores = -np.asarray(
            neg_obj_batch(np.column_stack(elites)), dtype=float
        )
        print(
            f"    * Screening initial : {len(elites)} élites "
            f"(meilleur {elite_scores.max():.4f}, "
            f"médian {float(np.median(elite_scores)):.4f})"
        )
        warm_starts.extend(elites)
    init_pop = build_init_population(
        n_inv, int(Config.STARR_DE_POPSIZE), pop_rng, scores, seed_pos,
        warm_starts, jitter=0.02, is_etf=is_etf_inv,
    )
    print(
        f"    * DE vectorise : population {init_pop.shape[0]} individus "
        f"(init sparse, depart mono-titre "
        f"{inv_tickers[seed_pos] if seed_pos is not None else 'aucun'}), "
        f"recherche sur {n_search} scenarios float32"
    )

    # ── Seeds indépendantes, chacune pilotée par sa température ──────────────
    # Dans une seed, la température baisse quand le score progresse et monte
    # lentement quand il stagne. Après son plateau chaud, le support est poli et
    # une population neuve repart sans l'incumbent global.
    #
    # Le DE étant ÉLITISTE, la température n'agit pas sur l'acceptation dans la
    # population mais ENTRE BASSINS : l'ANCRE (point de perturbation) peut
    # dériver vers un optimum moins bon, l'INCUMBENT livré jamais. Sans cette
    # dérive, toutes les perturbations resteraient clouées au même point et
    # referaient indéfiniment le même trajet.
    f_lo, f_hi = 0.5, 1.5
    def _make_solver(population: np.ndarray, rng_seed: int):
        return DifferentialEvolutionSolver(
            neg_obj_batch,  # vectorized=True : toute la population en 1 matmul BLAS
            bounds=bounds,
            rng=rng_seed,
            maxiter=max_gen,
            tol=de_tol,
            mutation=(f_lo, f_hi),
            recombination=0.9,
            init=population,
            polish=False,
            vectorized=True,
            updating="deferred",
        )

    solver = _make_solver(init_pop, de_seed)

    independent_seed_random_search_failed = False

    def _independent_seed_population(seed_value: int) -> tuple[np.ndarray, np.ndarray, float]:
        """Construit une population neuve sans réinjecter l'incumbent global."""
        nonlocal independent_seed_random_search_failed
        fresh_rng = np.random.default_rng(seed_value)
        try:
            if independent_seed_random_search_failed:
                raise PositiveSeedNotFound(
                    "la recherche aléatoire a déjà échoué pour cet univers"
                )
            fresh_start, fresh_score, _batch = _find_positive_seed(seed_value)
        except PositiveSeedNotFound as exc:
            # Une seed indépendante ne doit pas rendre tout le run invalide
            # simplement parce que la probabilité de tirer au hasard une
            # combinaison admissible est faible (plancher défensif, budgets et
            # plafonds broker). Le champion global reste une base faisable ; on
            # le réutilise uniquement comme point de départ de cette nouvelle
            # population, dont les autres individus restent neufs et aléatoires.
            # Ainsi, on conserve l'exploration inter-seeds sans jamais retomber
            # sur le faux score sentinelle ni interrompre une run saine.
            independent_seed_random_search_failed = True
            fallback_candidates: list[tuple[float, np.ndarray, str]] = []
            for energy, vector, source in (
                (global_best_energy, global_best_x, "meilleur_global"),
                (best_energy, best_x, "meilleur_seed"),
                *[
                    (energy, vector, "archive_support")
                    for energy, vector in support_archive
                ],
            ):
                value = float(energy)
                candidate = np.asarray(vector, dtype=float).reshape(-1)
                if (
                    candidate.size != n_inv
                    or not np.isfinite(value)
                    or value >= INVALID_OBJECTIVE_ENERGY
                ):
                    continue
                if not bool(feasible_batch(candidate[:, None])[0]):
                    continue
                fallback_candidates.append((value, candidate.copy(), source))
            if not fallback_candidates:
                raise exc
            fallback_energy, fallback_vector, fallback_source = min(
                fallback_candidates,
                key=lambda item: item[0],
            )
            fresh_start = fallback_vector
            fresh_score = -fallback_energy
            print(
                "    * Seed indépendante : aucun nouveau portefeuille "
                f"admissible trouvé ({exc}) ; reprise sécurisée du "
                f"{fallback_source} score={fresh_score:.5f}."
            )
        if independent_seed_random_search_failed:
            # Le screening élitiste réévalue jusqu'à 25 600 tirages sur cet
            # univers, alors que la campagne complète vient de montrer qu'une
            # combinaison admissible aléatoire est pratiquement introuvable.
            # La population neuve ci-dessous conserve malgré tout ses individus
            # aléatoires ; seul ce screening redondant est évité aux seeds
            # suivantes (un nouvel appel à l'optimiseur réinitialise le constat).
            fresh_elites = []
        else:
            fresh_elites = sample_elite_seeds(
                n_inv,
                fresh_rng,
                neg_obj_batch,
                batch_size=init_batch_size,
                max_batches=int(Config.STARR_DE_ELITE_BATCHES),
                n_elites=int(Config.STARR_DE_ELITE_COUNT),
                feasible=feasible_batch,
                should_stop=None,
            )
        population = build_init_population(
            n_inv,
            int(Config.STARR_DE_POPSIZE),
            fresh_rng,
            scores,
            seed_pos,
            [fresh_start, *fresh_elites],
            jitter=0.02,
            is_etf=is_etf_inv,
        )
        return population, fresh_start, -float(fresh_score)

    def _supports_of(matrice: np.ndarray) -> list:
        """Signatures des portefeuilles DÉPLOYÉS (pas des vecteurs de préférences).

        Prend une MATRICE (un portefeuille par colonne) : le déploiement est
        vectorisé, et le réchauffage a désormais lieu à chaque génération de
        stagnation. Colonne par colonne, cette boucle Python coûtait plus cher
        que la génération de DE elle-même.
        """
        deployed, _counts, _costs = _deploy_batch(
            np.maximum(np.asarray(matrice, dtype=float), 0.0)
        )
        return [
            support_signature(deployed[:, j], min_position)
            for j in range(deployed.shape[1])
        ]

    def _support_of(vector: np.ndarray) -> frozenset:
        """Signature d'un portefeuille unique."""
        return _supports_of(np.asarray(vector, dtype=float)[:, None])[0]

    # Nombre de lignes qu'un kick peut OUVRIR — délibérément plus que le
    # portefeuille n'en gardera.
    #
    # Le kick ouvre davantage de titres en compétition jusqu'à la capacité
    # économique. Le nombre de lignes n'est plus pénalisé par le score ; le
    # plafond par position et les contraintes pays/région restent actifs.
    reference_lines = (
        int(np.sum(broker_capacity))
        if card_beta <= 0.0
        else kick_line_budget(
            int(np.sum(broker_line_caps)), int(np.sum(broker_capacity))
        )
    )
    best_action_energy = float("inf")
    best_action_x: np.ndarray | None = None
    # File locale de la sonde « un ticker à la fois ». Elle vit pendant toute
    # l'optimisation, y compris entre les seeds, afin de ne pas réessayer le
    # même candidat lorsque son ajout n'a pas amélioré le champion.
    singleton_probed_indices: set[int] = set()

    def _record_action_candidate(
        candidate: np.ndarray,
        energy: float,
        *,
        deployed: np.ndarray | None = None,
        verify_feasible: bool = False,
    ) -> None:
        """Mémorise le meilleur candidat découvert contenant une action.

        Ce suivi est purement diagnostique : il ne modifie ni l'énergie ni le
        portefeuille retenu. Il permet de mesurer ce que coûte réellement la
        présence d'une action sans créer de poche minimale artificielle.
        """
        nonlocal best_action_energy, best_action_x
        value = float(energy)
        if not np.isfinite(value) or value >= best_action_energy:
            return
        vector = np.asarray(candidate, dtype=float).reshape(-1)
        if verify_feasible and not bool(feasible_batch(vector[:, None])[0]):
            return
        actual = deployed
        if actual is None:
            actual, _counts, _costs = _deploy_batch(vector[:, None])
            actual = actual[:, 0]
        if not np.any(np.asarray(actual)[~is_etf_inv] > 1e-12):
            return
        best_action_energy = value
        best_action_x = vector.copy()

    def _scan_action_population(population: np.ndarray, energies: np.ndarray) -> None:
        matrix = np.asarray(population, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix[:, None]
        values = np.asarray(energies, dtype=float).reshape(-1)
        if matrix.shape[1] != values.size:
            raise ValueError("population/energies incompatibles")
        deployed, _counts, _costs = _deploy_batch(matrix)
        has_action = np.any(deployed[~is_etf_inv, :] > 1e-12, axis=0)
        usable = has_action & np.isfinite(values) & (
            values < INVALID_OBJECTIVE_ENERGY
        )
        if not usable.any():
            return
        positions = np.flatnonzero(usable)
        selected = int(positions[int(np.argmin(values[positions]))])
        _record_action_candidate(
            matrix[:, selected],
            float(values[selected]),
            deployed=deployed[:, selected],
            verify_feasible=True,
        )
    forced_probes_tested = 0
    forced_probes_injected = 0
    explored_forced: set[int] = set()
    forced_floor = min(max(float(Config.STARR_DE_FORCED_FLOOR), 0.0), 1.0)
    probe_floor_candidates = [
        min(max(float(value), 0.0), forced_floor)
        for value in Config.STARR_DE_PROBE_FLOORS
    ]
    probe_floors = tuple(sorted({
        value for value in probe_floor_candidates if value > 0.0
    }))
    if forced_floor > 0.0 and forced_floor not in probe_floors:
        probe_floors = (*probe_floors, forced_floor)
    accessible_budget_share = np.asarray(access_inv, dtype=float) @ np.asarray(
        b_ratios, dtype=float
    )

    def _forced_floor_elites(
        anchor: np.ndarray,
        maximum: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Sonde chaque ticker à plusieurs poids et rend les meilleurs bassins."""
        nonlocal forced_probes_tested
        if not probe_floors or maximum <= 0:
            return (
                np.empty((n_inv, 0)), np.empty(0), np.empty(0, dtype=int),
                np.empty(0), np.empty(0),
            )
        deployed_anchor, _counts, _costs = _deploy_batch(
            np.maximum(np.asarray(anchor, dtype=float), 0.0)[:, None]
        )
        base = deployed_anchor[:, 0]
        energies = np.full(n_inv, float("inf"), dtype=float)
        best_preference_targets = np.zeros(n_inv, dtype=float)
        best_deployed_targets = np.zeros(n_inv, dtype=float)
        batch_size = max(1, int(Config.STARR_DE_FORCED_PROBE_BATCH_SIZE))
        for floor in probe_floors:
            deployed_targets = effective_forced_floor_targets(
                floor, access_inv, b_ratios
            )
            preference_targets = np.minimum(
                deployed_targets / np.maximum(accessible_budget_share, 1e-12), 1.0
            )
            for start in range(0, n_inv, batch_size):
                indices = np.arange(start, min(start + batch_size, n_inv), dtype=int)
                probes = build_forced_floor_probes(
                    base, indices, preference_targets[indices]
                )
                deployed, _probe_counts, _probe_costs = _deploy_batch(probes)
                actual = deployed[indices, np.arange(indices.size)]
                batch_energies = np.asarray(
                    neg_obj_batch(probes), dtype=float
                ).reshape(-1)
                opens_basin = base[indices] < deployed_targets[indices] - 1e-6
                valid = (
                    opens_basin
                    & (actual >= deployed_targets[indices] - 1e-6)
                    & np.isfinite(batch_energies)
                    & (batch_energies < INVALID_OBJECTIVE_ENERGY)
                )
                better = valid & (batch_energies < energies[indices])
                chosen = indices[better]
                energies[chosen] = batch_energies[better]
                best_preference_targets[chosen] = preference_targets[chosen]
                best_deployed_targets[chosen] = deployed_targets[chosen]
                forced_probes_tested += int(indices.size)
        if explored_forced:
            energies[np.asarray(sorted(explored_forced), dtype=int)] = float("inf")
        wanted = min(maximum, int(Config.STARR_DE_FORCED_PROBE_ELITES))
        selected = select_stratified_probe_elites(
            energies,
            is_etf_inv,
            wanted,
        )
        # Un probe direct peut être infaisable alors qu'un DE CONTRAINT complet
        # trouverait une combinaison faisable autour du même titre. Ne jamais
        # laisser ce filtre rapide vider la moitié « actions » : sinon une ancre
        # ETF produirait encore une campagne 100 % ETF. On remplace les ETF de
        # remplissage par les meilleures actions standalone accessibles ; leur
        # DE dédié décidera honnêtement après convergence.
        selected_list = [int(item) for item in selected]
        action_target = min(wanted, max(1, wanted // 2))
        action_count = sum(not bool(is_etf_inv[item]) for item in selected_list)
        if action_count < action_target:
            fallback_actions = [
                int(item)
                for item in np.argsort(scores)[::-1]
                if (
                    not bool(is_etf_inv[int(item)])
                    and int(item) not in selected_list
                    and int(item) not in explored_forced
                    and accessible_budget_share[int(item)] > 1e-12
                )
            ]
            while action_count < action_target and fallback_actions:
                replace_at = next(
                    (
                        pos for pos in range(len(selected_list) - 1, -1, -1)
                        if bool(is_etf_inv[selected_list[pos]])
                    ),
                    None,
                )
                candidate = fallback_actions.pop(0)
                if replace_at is None:
                    if len(selected_list) >= wanted:
                        break
                    selected_list.append(candidate)
                else:
                    selected_list[replace_at] = candidate
                action_count += 1
        selected = np.asarray(selected_list[:wanted], dtype=int)
        if selected.size == 0:
            return (
                np.empty((n_inv, 0)), np.empty(0), selected,
                np.empty(0), np.empty(0),
            )
        # Les replis standalone peuvent ne pas avoir de probe faisable direct :
        # ils démarrent alors au plus petit poids atteignable de l'entonnoir.
        missing = best_preference_targets[selected] <= 0.0
        if missing.any():
            fallback_deployed = effective_forced_floor_targets(
                probe_floors[0], access_inv, b_ratios
            )[selected[missing]]
            best_deployed_targets[selected[missing]] = fallback_deployed
            best_preference_targets[selected[missing]] = np.minimum(
                fallback_deployed
                / np.maximum(accessible_budget_share[selected[missing]], 1e-12),
                1.0,
            )
        probes = build_forced_floor_probes(
            base, selected, best_preference_targets[selected]
        )
        selected_energies = np.asarray(neg_obj_batch(probes), dtype=float).reshape(-1)
        return (
            probes, selected_energies, selected,
            best_preference_targets[selected], best_deployed_targets[selected],
        )

    def _reheat(
        anchor: np.ndarray, temperature: float
    ) -> tuple[
        int, np.ndarray | None, float, list[tuple[int, int]], np.ndarray,
        np.ndarray, np.ndarray,
    ]:
        """Réinjecte des variantes à support remanié dans les PIRES individus.

        L'ampleur du geste est entièrement commandée par la température : combien
        d'individus (`reheat_quota`) et combien de lignes remaniées dans chacun
        (`reheat_amplitude`). À T=1 la population entière est refondue en
        portefeuilles tirés au hasard ; à T→0 une poignée d'individus voit une
        seule ligne changer.

        Les cibles sont les PIRES individus d'abord. L'incumbent (index 0) n'est
        donc atteint qu'à T=1, quand le quota couvre tout le monde — et ce n'est
        pas une perte : `best_x` conserve le meilleur portefeuille hors de la
        population, et c'est lui qui est livré. `_promote_lowest_energy` rétablit
        ensuite l'invariant « index 0 = meilleur » attendu par `best1bin`.
        """
        members = int(solver.population.shape[0])
        if members < 2:
            return (0, None, float("-inf"), [], np.empty(0, dtype=int),
                    np.empty(0), np.empty(0))
        quota = reheat_quota(temperature, members)
        ordre = list(np.argsort(solver.population_energies)[::-1])
        cibles = ordre[:quota]
        if not cibles:
            return (0, None, float("-inf"), [], np.empty(0, dtype=int),
                    np.empty(0), np.empty(0))
        # Échelle du remaniement. Volontairement PAS le support courant seul :
        # sinon un portefeuille de 11 lignes ne pourrait jamais en ouvrir 15, et
        # un portefeuille étroit resterait étroit à jamais. La référence est le
        # nombre de lignes que le portefeuille a le droit de porter — c'est cette
        # taille-là qu'une refonte doit pouvoir reconstruire de zéro.
        plafond = reheat_amplitude(temperature, reference_lines)
        # Le vecteur interne du DE devient dense très vite, tandis que le
        # portefeuille réellement détenu reste sparse. Kicker le vecteur brut
        # retirait quelques coordonnées quelconques parmi des milliers et ne
        # touchait souvent aucune ligne déployée. La température montait donc à
        # 1 sans que l'univers exploré change réellement.
        deployed_anchor, _counts, _costs = _deploy_batch(
            np.maximum(np.asarray(anchor, dtype=float), 0.0)[:, None]
        )
        kick_anchor = project_preferences_to_deployed_support(
            anchor, deployed_anchor[:, 0]
        )
        # Chaque variante tire SES propres n_drop / n_add, indépendamment l'un de
        # l'autre : une secousse peut retirer 10 lignes et en ouvrir 15, une
        # autre n'en fermer aucune et en ajouter 3. C'est ce qui fait varier la
        # forme du portefeuille, pas seulement son contenu.
        def _variante() -> np.ndarray:
            nonlocal lns_moves
            if bool(Config.STARR_LNS_ENABLED):
                # Une archive diverse fournit d'autres points de depart que le
                # seul incumbent. Les redemarrages globaux ignorent naturellement
                # ce support en le detruisant entierement.
                source = kick_anchor
                if support_archive and float(pop_rng.random()) < 0.45:
                    source = support_archive[int(pop_rng.integers(len(support_archive)))][1]
                    source_deployed, _c, _k = _deploy_batch(source[:, None])
                    source = project_preferences_to_deployed_support(
                        source, source_deployed[:, 0]
                    )
                active_count = int(np.count_nonzero(source > 0.0))
                mode, n_drop, n_add = sample_multiscale_kick_sizes(
                    pop_rng, active_count, plafond
                )
                lns_moves[mode] += 1
                return np.clip(
                    guided_kick_portfolio(
                        source,
                        pop_rng,
                        n_drop=n_drop,
                        n_add=n_add,
                        standalone_scores=scores,
                        correlation=search_corr,
                        guidance_weight=float(Config.STARR_LNS_GUIDANCE_WEIGHT),
                        eligible_mask=reconstruction_eligible,
                    ),
                    0.0,
                    1.0,
                )
            n_drop, n_add = sample_kick_sizes(pop_rng, plafond)
            return np.clip(
                kick_portfolio(
                    kick_anchor,
                    pop_rng,
                    n_drop=n_drop,
                    n_add=n_add,
                    eligible_mask=reconstruction_eligible,
                ),
                0.0, 1.0,
            )

        # Les variantes ne sont PLUS confrontées au tabou. Cette confrontation
        # exigeait jusqu'à trois déploiements complets de toute la matrice par
        # génération — mesuré à 8,7 % du temps de la boucle — pour un bénéfice
        # marginal : 13 variantes retirées sur 107 réchauffages. Les tirages
        # indépendants de n_drop/n_add fournissent déjà la diversité recherchée.
        # Le tabou garde son rôle utile et bon marché : reconnaître qu'un OPTIMUM
        # déjà visité a été atteint de nouveau (une seule colonne déployée).
        matrice = np.column_stack([_variante() for _ in cibles])
        # A chaque phase de stagnation, réserver une variante à l'expérience
        # structurée demandée par la stratégie d'exploration : conserver le
        # portefeuille global et ouvrir exactement UN titre encore absent,
        # celui dont la corrélation au portefeuille pondéré est la plus faible.
        # Les autres variantes restent multi-échelles et aléatoires. Cette
        # sonde évite qu'une longue série de kicks se contente de permuter les
        # mêmes lignes sans jamais tester proprement le prochain candidat.
        singleton_eligible = np.asarray(reconstruction_eligible, dtype=bool).copy()
        if singleton_probed_indices:
            singleton_eligible[list(singleton_probed_indices)] = False
        if cibles and np.any((kick_anchor <= 0.0) & singleton_eligible):
            singleton = guided_kick_portfolio(
                kick_anchor,
                pop_rng,
                n_drop=0,
                n_add=1,
                standalone_scores=scores,
                correlation=search_corr,
                guidance_weight=0.0,
                eligible_mask=singleton_eligible,
                selection_noise=0.0,
            )
            if not np.allclose(singleton, kick_anchor):
                matrice[:, 0] = singleton
                singleton_probed_indices.update(
                    int(index)
                    for index in np.flatnonzero(
                        (singleton > 0.0) & (kick_anchor <= 0.0)
                    )
                )
                lns_moves["correlation_singleton"] = (
                    lns_moves.get("correlation_singleton", 0) + 1
                )
        forced_count = 0
        forced_indices = np.empty(0, dtype=int)
        forced_preference_targets = np.empty(0)
        forced_deployed_targets = np.empty(0)
        # Au plafond, un kick aléatoire ne suffit plus : on balaie explicitement
        # tout l'univers à 1/3/5/10 %. Les meilleures actions ET les meilleurs ETF
        # remplacent une partie des variantes avant l'entonnoir dédié.
        if (
            not bool(Config.STARR_LNS_ENABLED)
            and temperature >= float(Config.STARR_DE_T_MAX) - 1e-9
        ):
            (
                forced, forced_energies, forced_indices,
                forced_preference_targets, forced_deployed_targets,
            ) = _forced_floor_elites(anchor, len(cibles))
            forced_count = int(forced.shape[1])
            if forced_count:
                matrice[:, :forced_count] = forced
        energies_var = np.asarray(neg_obj_batch(matrice), dtype=float).reshape(-1)
        if forced_count:
            # Les energies viennent deja d'etre calculees durant le balayage ;
            # les reutiliser garantit aussi le meme classement des elites.
            energies_var[:forced_count] = forced_energies
        # Une énergie non finie rendrait `convergence` infinie et `converged()`
        # faux : on n'injecte que des individus réellement évaluables.
        utilisables = np.isfinite(energies_var) & (
            energies_var < INVALID_OBJECTIVE_ENERGY
        )
        injectes = 0
        for position, cible in enumerate(cibles):
            if not utilisables[position]:
                continue
            solver.population[cible] = matrice[:, position]
            solver.population_energies[cible] = energies_var[position]
            injectes += 1
        promoted_index = int(np.argmin(solver.population_energies))
        if injectes and hasattr(solver, "_promote_lowest_energy"):
            solver._promote_lowest_energy()
        # La MEILLEURE variante est rendue à l'appelant : c'est elle, et non
        # l'incumbent, qui est proposée comme nouvelle ancre. Sans un candidat
        # DIFFÉRENT du point de départ, la dérive entre bassins ne peut pas avoir
        # lieu — cf. la boucle.
        meilleure, score_meilleure = None, float("-inf")
        if utilisables.any():
            position = int(np.flatnonzero(utilisables)[
                int(np.argmin(energies_var[utilisables]))
            ])
            meilleure = matrice[:, position].copy()
            score_meilleure = -float(energies_var[position])
            _record_action_candidate(
                meilleure,
                float(energies_var[position]),
                verify_feasible=True,
            )
            if bool(Config.STARR_LNS_ENABLED):
                support_archive[:] = update_diverse_support_archive(
                    support_archive,
                    meilleure,
                    float(energies_var[position]),
                    min_position=min_position,
                    max_size=int(Config.STARR_LNS_ARCHIVE_SIZE),
                    min_distance=float(Config.STARR_LNS_ARCHIVE_MIN_DISTANCE),
                )
        forced_assignments = [
            (int(cibles[position]), int(forced_indices[position]))
            for position in range(forced_count)
            if utilisables[position] and int(cibles[position]) != promoted_index
        ]
        return (
            injectes,
            meilleure,
            score_meilleure,
            forced_assignments,
            forced_indices.copy(),
            forced_preference_targets.copy(),
            forced_deployed_targets.copy(),
        )

    evolution_parent_pool: list[tuple[float, np.ndarray]] = []
    evolution_resets = 0

    def _repair_evolution_matrix(
        matrix: np.ndarray,
        anchors: np.ndarray | None = None,
    ) -> np.ndarray:
        """Répare les enfants avant scoring sans affaiblir les contraintes dures."""
        values = np.clip(np.asarray(matrix, dtype=float), 0.0, 1.0).copy()
        if values.ndim == 1:
            values = values[:, None]
        # Réparation générique des contraintes linéaires restantes (défensif,
        # pays, World) : conserver autant que possible l'enfant,
        # puis le rapprocher par dichotomie grossière du meilleur global, qui est
        # déjà faisable. Cette étape évite de brûler le scoring sur des enfants
        # manifestement incompatibles sans transformer tous les enfants en clones.
        # Un seul déploiement initial suffit : l'objectif redéploiera ensuite ces
        # mêmes préférences pour établir leur score exact.
        deployed, _counts, _costs = _deploy_batch(values)
        feasible = _lookthrough_feasible_batch(deployed)
        unresolved = np.flatnonzero(~feasible)
        original_children = values.copy()
        repair_anchors = [best_x.copy()]
        if anchors is not None and np.asarray(anchors).size:
            anchor_values = np.asarray(anchors, dtype=float)
            if anchor_values.ndim == 1:
                anchor_values = anchor_values[:, None]
            repair_anchors.extend(
                anchor_values[:, index].copy()
                for index in range(anchor_values.shape[1])
            )
        # Ne jamais rabattre tous les candidats invalides sur le seul incumbent.
        # Chaque enfant choisit l'ancre faisable au support le plus éloigné.
        unique_anchors = select_unique_support_candidates(
            [(0.0, vector) for vector in repair_anchors],
            count=len(repair_anchors),
            min_position=min_position,
        )
        anchor_matrix = np.column_stack(
            [vector for _energy, vector in unique_anchors] or [best_x]
        )
        # Après quelques générations de DE, les préférences sont souvent
        # strictement positives pour presque tout l'univers, alors que le
        # déploiement ne garde qu'un support réduit par broker et plafonds. La
        # distance calculée sur ``original_children`` ferait donc croire que
        # tous les enfants ont le même support et choisirait toujours la même
        # ancre. Revenir au support effectivement déployé conserve la diversité
        # que la réparation est justement censée préserver.
        original_support = project_preferences_to_deployed_support(
            original_children,
            deployed,
        )
        chosen_anchor_indices = np.asarray([
            max(
                range(anchor_matrix.shape[1]),
                key=lambda anchor_index: support_jaccard_distance(
                    original_support[:, column_index],
                    anchor_matrix[:, anchor_index],
                    min_position,
                ),
            )
            for column_index in unresolved
        ], dtype=int)
        # Tester chaque niveau de rapprochement en un seul lot est strictement
        # équivalent à la boucle enfant par enfant, mais évite jusqu'à plusieurs
        # centaines de déploiements Python par génération.
        for child_share in (0.75, 0.50, 0.25, 0.10, 0.0):
            if not len(unresolved):
                break
            trials = (
                child_share * original_children[:, unresolved]
                + (1.0 - child_share) * anchor_matrix[:, chosen_anchor_indices]
            )
            trial_deployed, _c, _k = _deploy_batch(trials)
            accepted = _lookthrough_feasible_batch(trial_deployed)
            if accepted.any():
                accepted_local = np.flatnonzero(accepted)
                for local_index in accepted_local:
                    column_index = int(unresolved[local_index])
                    values[:, column_index] = project_preferences_to_deployed_support(
                        trials[:, local_index], trial_deployed[:, local_index]
                    )
                unresolved = unresolved[~accepted]
                chosen_anchor_indices = chosen_anchor_indices[~accepted]
        return np.clip(values, 0.0, 1.0)

    def _repair_infeasible_previous_champion() -> None:
        """Rend l'ancien champion admissible avant de lancer le DE."""
        nonlocal positive_seed, positive_score, global_best_energy, global_best_x
        nonlocal validation_archive, previous_champion_repaired
        nonlocal previous_champion_repair_score
        if not has_previous_champion or previous_champion_feasible:
            return

        base = np.clip(np.asarray(champion_inv, dtype=float).reshape(-1), 0.0, 1.0)
        if float(base.sum()) <= 1e-12:
            return
        base /= float(base.sum())
        options: list[tuple[float, np.ndarray, str]] = []

        def consider(candidate: np.ndarray, source: str) -> None:
            vector = np.clip(np.asarray(candidate, dtype=float).reshape(-1), 0.0, 1.0)
            total = float(vector.sum())
            if total <= 1e-12:
                return
            vector /= total
            deployed, _counts, _costs = _deploy_batch(vector[:, None])
            if not bool(_lookthrough_feasible_batch(deployed)[0]):
                return
            energy = float(neg_obj_batch(vector[:, None])[0])
            if np.isfinite(energy) and energy < INVALID_OBJECTIVE_ENERGY:
                options.append((energy, vector.copy(), source))

        consider(base, "champion_sans_modification")

        defensive = np.asarray(d_vec, dtype=float).reshape(-1)
        accessible = np.any(np.asarray(access_inv, dtype=bool), axis=1)
        candidates = np.flatnonzero(accessible & (defensive > 1e-12))
        if candidates.size:
            order = candidates[
                np.lexsort(
                    (
                        -np.asarray(scores, dtype=float)[candidates],
                        -defensive[candidates],
                    )
                )
            ]
            for count in range(1, min(int(order.size), 12) + 1):
                selected = order[:count]
                target = np.zeros(n_inv, dtype=float)
                target[selected] = np.maximum(defensive[selected], 1e-6)
                target_sum = float(target.sum())
                if target_sum <= 1e-12:
                    continue
                target /= target_sum
                target_deployed, _target_counts, _target_costs = _deploy_batch(
                    target[:, None]
                )
                if not bool(_lookthrough_feasible_batch(target_deployed)[0]):
                    continue
                low, high = 0.0, 1.0
                for _ in range(22):
                    middle = (low + high) / 2.0
                    probe = (1.0 - middle) * base + middle * target
                    deployed, _probe_counts, _probe_costs = _deploy_batch(
                        probe[:, None]
                    )
                    if bool(_lookthrough_feasible_batch(deployed)[0]):
                        high = middle
                    else:
                        low = middle
                consider(
                    (1.0 - high) * base + high * target,
                    f"champion_repare_panier_defensif_{count}",
                )

        # Le DE a déjà évalué sa population initiale : utiliser ses points
        # faisables comme dernier filet, sans réintroduire une recherche aveugle.
        population = np.asarray(solver.population, dtype=float).T
        population_feasible = feasible_batch(population)
        for index in np.flatnonzero(population_feasible):
            consider(population[:, int(index)], "population_initiale_faisable")
        if not options:
            raise InvalidOptimizationObjective(
                "Le portefeuille précédent ne respecte plus les contraintes "
                "courantes et aucune réparation faisable n'a été trouvée ; "
                "aucun faux score sentinelle ne sera utilisé."
            )

        energy, repaired, source = min(options, key=lambda item: item[0])
        positive_seed = repaired.copy()
        positive_score = -float(energy)
        previous_champion_repaired = True
        previous_champion_repair_score = -float(energy)
        global_best_energy = float(energy)
        global_best_x = repaired.copy()
        validation_archive[:] = [(float(energy), repaired.copy())]

        worst = int(np.argmax(np.asarray(solver.population_energies, dtype=float)))
        solver.population[worst] = repaired
        solver.population_energies[worst] = float(energy)
        if hasattr(solver, "_promote_lowest_energy"):
            solver._promote_lowest_energy()
        print(
            "    * Champion précédent infaisable sous les contraintes actuelles : "
            f"réparation déterministe ({source}), score={-energy:.5f}."
        )

    def _evolutionary_generation(
        temperature: float,
        stagnation: int,
    ) -> tuple[dict, np.ndarray | None, float]:
        """Un meilleur protégé + 12 parents uniques → enfants → survivants."""
        nonlocal evolution_parent_pool, evolution_resets, best_energy, best_x
        nonlocal global_best_energy, global_best_x
        parent_target = max(0, int(Config.STARR_EVOLUTION_PARENT_COUNT))
        children_per_parent = max(
            0, int(Config.STARR_EVOLUTION_CHILDREN_PER_PARENT)
        )
        geography_children = min(
            children_per_parent,
            max(0, int(Config.STARR_EVOLUTION_GEOGRAPHY_CHILDREN)),
        )
        global_local_children = max(
            0, int(Config.STARR_EVOLUTION_GLOBAL_LOCAL_CHILDREN)
        )
        random_target = max(
            0, int(Config.STARR_EVOLUTION_RANDOM_CANDIDATES)
        )
        min_parent_distance = float(Config.STARR_EVOLUTION_MIN_PARENT_DISTANCE)

        # Les meilleurs individus du DE et l'archive diverse fournissent un pool
        # compact. Leurs supports sont projetés puis rescorrés avec le même
        # objectif avant le classement : la projection peut modifier les frais,
        # les plafonds ou la normalisation. La réparation complète reste réservée
        # aux nouveaux enfants et aux candidats aléatoires.
        population_order = np.argsort(solver.population_energies)
        source_limit = min(
            len(population_order), max(48, 4 * max(parent_target, 1))
        )
        pool_energies = [float(best_energy)]
        pool_vectors = [np.asarray(best_x, dtype=float).copy()]
        for index in population_order[:source_limit]:
            energy = float(solver.population_energies[int(index)])
            if np.isfinite(energy) and energy < INVALID_OBJECTIVE_ENERGY:
                pool_energies.append(energy)
                pool_vectors.append(
                    np.asarray(solver.population[int(index)], dtype=float).copy()
                )
        for energy, vector in support_archive:
            if np.isfinite(energy) and energy < INVALID_OBJECTIVE_ENERGY:
                pool_energies.append(float(energy))
                pool_vectors.append(np.asarray(vector, dtype=float).copy())
        pool_matrix = np.column_stack(pool_vectors)
        pool_deployed, _pool_counts, _pool_costs = _deploy_batch(pool_matrix)
        projected_pool = np.column_stack([
            project_preferences_to_deployed_support(
                vector, pool_deployed[:, column]
            )
            for column, vector in enumerate(pool_vectors)
        ])
        # La projection retire les préférences qui ne seront effectivement pas
        # déployées. Elle peut donc modifier la normalisation, les plafonds et
        # les frais : l'énergie du vecteur brut n'est pas nécessairement celle
        # du support projeté. Reclasser ces points avec l'ancien score envoyait
        # parfois un parent médiocre dans la lignée « élite ». Ce re-score est
        # fait une seule fois au démarrage de chaque seed ; ensuite la sélection
        # des parents repose sur ``evolution_parent_pool``, dont les enfants sont
        # déjà évalués après leur projection, et le coût ne revient pas à chaque
        # génération.
        if evolution_parent_pool:
            pool = [
                (float(energy), projected_pool[:, index])
                for index, energy in enumerate(pool_energies)
                if np.isfinite(float(energy))
                and float(energy) < INVALID_OBJECTIVE_ENERGY
            ]
        else:
            projected_energies = np.asarray(
                neg_obj_batch(projected_pool), dtype=float
            ).reshape(-1)
            pool = []
            for index, (energy, vector) in enumerate(
                zip(pool_energies, pool_vectors, strict=True)
            ):
                projected_energy = float(projected_energies[index])
                if np.isfinite(projected_energy) and (
                    projected_energy < INVALID_OBJECTIVE_ENERGY
                ):
                    pool.append((projected_energy, projected_pool[:, index]))
                elif (
                    np.isfinite(float(energy))
                    and float(energy) < INVALID_OBJECTIVE_ENERGY
                ):
                    # Filet de sécurité : une projection exceptionnelle devenue
                    # infaisable ne doit pas faire disparaître un point déjà validé.
                    pool.append((float(energy), np.asarray(vector, dtype=float).copy()))
        # ``best_x`` est généralement le premier élément, mais une projection
        # archivée peut avoir amélioré le score après la dernière génération DE
        # (répartition par courtier, frais ou plafonds). Trier avant de choisir
        # l'ancre rend cette amélioration immédiatement exploitable au lieu de la
        # laisser dormir dans l'archive jusqu'à un réchauffage ultérieur.
        pool.sort(key=lambda item: float(item[0]))
        if pool and float(pool[0][0]) < best_energy:
            best_energy = float(pool[0][0])
            best_x = np.asarray(pool[0][1], dtype=float).copy()
        if pool and float(pool[0][0]) < global_best_energy:
            global_best_energy = float(pool[0][0])
            global_best_x = np.asarray(pool[0][1], dtype=float).copy()
            _maybe_emit_progress(global_best_x)
        global_parent = pool[0][1]
        global_signature = support_signature(global_parent, min_position)
        parent_source = evolution_parent_pool if evolution_parent_pool else pool
        other_parents = select_unique_support_candidates(
            parent_source,
            count=parent_target,
            min_position=min_position,
            min_distance=min_parent_distance,
            excluded_signatures={global_signature},
        )

        # Cas défensif des toutes premières générations : compléter les parents
        # manquants avec des portefeuilles aléatoires réparés et faisables.
        fill_attempts = 0
        while len(other_parents) < parent_target and fill_attempts < 4:
            fill_attempts += 1
            random_fill = build_random_sparse_population(
                n_inv, max(32, 4 * (parent_target - len(other_parents))), pop_rng
            ).T
            anchor_columns = [global_parent] + [
                vector for _energy, vector in other_parents
            ]
            random_fill = _repair_evolution_matrix(
                random_fill,
                np.column_stack(anchor_columns),
            )
            fill_energies = np.asarray(neg_obj_batch(random_fill), dtype=float).reshape(-1)
            pool.extend(
                (float(fill_energies[index]), random_fill[:, index])
                for index in range(random_fill.shape[1])
                if np.isfinite(fill_energies[index])
                and fill_energies[index] < INVALID_OBJECTIVE_ENERGY
            )
            other_parents = select_unique_support_candidates(
                pool,
                count=parent_target,
                min_position=min_position,
                min_distance=min_parent_distance,
                excluded_signatures={global_signature},
            )

        parents = [global_parent] + [vector for _energy, vector in other_parents]
        children: list[np.ndarray] = []

        # Quatre voisins très fins, une seule fois, autour du meilleur global.
        global_active = int(np.count_nonzero(global_parent > 0.0))
        for child_rank in range(global_local_children):
            mode, n_drop, n_add = local_child_kick_sizes(
                pop_rng,
                active_lines=global_active,
                line_budget=reference_lines,
                child_rank=child_rank,
                local_children=global_local_children,
            )
            lns_moves[mode] += 1
            children.append(
                guided_kick_portfolio(
                    global_parent,
                    pop_rng,
                    n_drop=n_drop,
                    n_add=n_add,
                    standalone_scores=scores,
                    correlation=search_corr,
                    guidance_weight=float(Config.STARR_LNS_GUIDANCE_WEIGHT),
                    eligible_mask=reconstruction_eligible,
                )
            )

        # Les douze autres lignées conservent huit enfants chacune et couvrent
        # toute l'amplitude commandée par la température.
        for parent in (vector for _energy, vector in other_parents):
            active = int(np.count_nonzero(parent > 0.0))
            for child_rank in range(children_per_parent):
                if child_rank < geography_children:
                    child = geography_guided_child(
                        parent,
                        pop_rng,
                        sector_matrix=sector_mat,
                        country_matrix=C_mat,
                        standalone_scores=scores,
                        correlation=search_corr,
                        medium_exposure=float(
                            Config.STARR_SECTOR_COUNTRY_MEDIUM_EXPOSURE
                        ),
                        large_exposure=float(
                            Config.STARR_SECTOR_COUNTRY_LARGE_EXPOSURE
                        ),
                        temperature=temperature,
                        joint_matrix=joint_mat,
                        eligible_mask=reconstruction_eligible,
                    )
                    if not np.allclose(child, parent):
                        lns_moves["geography"] = lns_moves.get("geography", 0) + 1
                        children.append(child)
                        continue
                mode, n_drop, n_add = temperature_child_kick_sizes(
                    pop_rng,
                    active_lines=active,
                    line_budget=reference_lines,
                    temperature=temperature,
                    child_rank=child_rank,
                    children_per_parent=children_per_parent,
                )
                lns_moves[mode] += 1
                children.append(
                    guided_kick_portfolio(
                        parent,
                        pop_rng,
                        n_drop=n_drop,
                        n_add=n_add,
                        standalone_scores=scores,
                        correlation=search_corr,
                        guidance_weight=float(Config.STARR_LNS_GUIDANCE_WEIGHT),
                        eligible_mask=reconstruction_eligible,
                    )
                )
        random_candidates = build_random_sparse_population(
            n_inv, random_target, pop_rng
        ).T if random_target else np.empty((n_inv, 0))
        candidate_columns = children + [
            random_candidates[:, index]
            for index in range(random_candidates.shape[1])
        ]
        if not candidate_columns:
            return ({
                "parents": len(parents), "children": 0, "random": 0,
                "feasible": 0, "survivors": 0,
            }, None, float("-inf"))
        # Une réparation contre les seuls parents rabattait tous les enfants
        # infaisables sur le même `best_x` (notamment avec le plancher défensif).
        # Le filtre d'unicité les supprimait ensuite tous comme clones et le
        # réchauffage annonçait « 0 individu réinjecté ». Utiliser un éventail
        # d'ancres admissibles déjà évaluées conserve plusieurs bassins distincts
        # au lieu de transformer la réparation en projection vers un point unique.
        repair_anchor_pool = select_unique_support_candidates(
            pool,
            count=min(48, len(pool)),
            min_position=min_position,
            min_distance=0.0,
        )
        repair_anchors = np.column_stack(
            [vector for _energy, vector in repair_anchor_pool]
            or [global_parent]
        )
        candidate_matrix = _repair_evolution_matrix(
            np.column_stack(candidate_columns),
            repair_anchors,
        )
        candidate_energies = np.asarray(
            neg_obj_batch(candidate_matrix), dtype=float
        ).reshape(-1)
        viable = np.isfinite(candidate_energies) & (
            candidate_energies < INVALID_OBJECTIVE_ENERGY
        )
        child_pool = [
            (float(candidate_energies[index]), candidate_matrix[:, index])
            for index in np.flatnonzero(viable[:len(children)])
        ]
        random_pool = [
            (
                float(candidate_energies[index]),
                candidate_matrix[:, index],
            )
            for index in range(len(children), len(candidate_energies))
            if viable[index]
        ]
        nonrandom_pool = list(other_parents) + child_pool
        survivors: list[tuple[float, np.ndarray]] = []
        survivor_signatures = {global_signature}

        def append_unique(items: list[tuple[float, np.ndarray]]) -> None:
            for energy, vector in items:
                if len(survivors) >= parent_target:
                    break
                signature = support_signature(vector, min_position)
                if not signature or signature in survivor_signatures:
                    continue
                survivors.append((float(energy), vector.copy()))
                survivor_signatures.add(signature)

        # 1) Quatre élites de score : l'exploitation reste forte sans occuper
        # les douze lignées.
        append_unique(select_unique_support_candidates(
            nonrandom_pool,
            count=int(Config.STARR_EVOLUTION_SCORE_ELITES),
            min_position=min_position,
            min_distance=min_parent_distance,
            excluded_signatures=survivor_signatures,
        ))

        # 2) Continuité familiale : un enfant affronte son propre parent. À
        # chaud, Metropolis peut conserver un enfant légèrement moins bon et
        # traverser ainsi une vallée que l'élitisme global interdit.
        lineage_pool: list[tuple[float, np.ndarray]] = []
        for parent_index, parent_item in enumerate(other_parents):
            parent_energy, parent_vector = parent_item
            start = global_local_children + parent_index * children_per_parent
            stop = min(start + children_per_parent, len(children))
            family_indices = [
                index for index in range(start, stop) if viable[index]
            ]
            chosen = (float(parent_energy), parent_vector)
            if family_indices:
                child_index = min(
                    family_indices,
                    key=lambda index: candidate_energies[index],
                )
                child_energy = float(candidate_energies[child_index])
                child_vector = candidate_matrix[:, child_index]
                if accept_new_anchor(
                    -float(parent_energy),
                    -child_energy,
                    temperature,
                    float(pop_rng.random()),
                ):
                    chosen = (child_energy, child_vector)
            lineage_pool.append(chosen)
        append_unique(select_unique_support_candidates(
            lineage_pool,
            count=int(Config.STARR_EVOLUTION_LINEAGE_SURVIVORS),
            min_position=min_position,
            min_distance=0.0,
            excluded_signatures=survivor_signatures,
        ))

        # 3) Nouveauté explicite puis immigrants : ces places ne peuvent pas
        # être reprises par douze variantes proches du même optimum.
        append_unique(select_novel_support_candidates(
            nonrandom_pool,
            count=int(Config.STARR_EVOLUTION_NOVELTY_SURVIVORS),
            min_position=min_position,
            anchors=[global_parent, *[vector for _energy, vector in survivors]],
            excluded_signatures=survivor_signatures,
        ))
        append_unique(select_novel_support_candidates(
            random_pool,
            count=int(Config.STARR_EVOLUTION_RANDOM_SURVIVORS),
            min_position=min_position,
            anchors=[global_parent, *[vector for _energy, vector in survivors]],
            excluded_signatures=survivor_signatures,
        ))
        append_unique(select_unique_support_candidates(
            nonrandom_pool + random_pool,
            count=parent_target - len(survivors),
            min_position=min_position,
            min_distance=0.0,
            excluded_signatures=survivor_signatures,
        ))

        reset_every = max(0, int(Config.STARR_EVOLUTION_RESET_STAGNATION))
        reset_count = min(
            parent_target,
            max(0, int(Config.STARR_EVOLUTION_RESET_PARENT_COUNT)),
        )
        reset_due = (
            reset_every > 0
            and stagnation >= reset_every
            and stagnation % reset_every == 0
        )
        if reset_due and random_pool:
            kept = select_unique_support_candidates(
                survivors,
                count=max(0, parent_target - reset_count),
                min_position=min_position,
                min_distance=min_parent_distance,
                excluded_signatures={global_signature},
            )
            kept_signatures = {
                global_signature,
                *(support_signature(vector, min_position) for _energy, vector in kept),
            }
            restarted = select_novel_support_candidates(
                random_pool,
                count=reset_count,
                min_position=min_position,
                anchors=[global_parent, *[vector for _energy, vector in kept]],
                excluded_signatures=kept_signatures,
            )
            survivors = kept + restarted
            survivor_signatures = {
                global_signature,
                *(support_signature(vector, min_position) for _energy, vector in survivors),
            }
            append_unique(select_novel_support_candidates(
                child_pool + random_pool,
                count=parent_target - len(survivors),
                min_position=min_position,
                anchors=[global_parent, *[vector for _energy, vector in survivors]],
                excluded_signatures=survivor_signatures,
            ))
            evolution_resets += 1

        evolution_parent_pool = [
            (float(energy), vector.copy()) for energy, vector in survivors
        ]

        # Le meilleur global reste explicitement à l'index élite. À T=1 on
        # injecte jusqu'à 64 candidats distincts, au lieu de seulement 12/515.
        hot_injection = max(
            parent_target,
            int(Config.STARR_EVOLUTION_HOT_INJECTION_COUNT),
        )
        injection_target = min(
            len(candidate_energies),
            max(
                parent_target,
                int(round(parent_target + temperature * (hot_injection - parent_target))),
            ),
        )
        injections = list(survivors)
        injection_signatures = {
            global_signature,
            *(support_signature(vector, min_position) for _energy, vector in injections),
        }
        remaining_target = max(0, injection_target - len(injections))
        append_best = select_unique_support_candidates(
            child_pool + random_pool,
            count=remaining_target // 2,
            min_position=min_position,
            min_distance=0.0,
            excluded_signatures=injection_signatures,
        )
        injections.extend(append_best)
        injection_signatures.update(
            support_signature(vector, min_position) for _energy, vector in append_best
        )
        injections.extend(select_novel_support_candidates(
            child_pool + random_pool,
            count=injection_target - len(injections),
            min_position=min_position,
            anchors=[global_parent, *[vector for _energy, vector in injections]],
            excluded_signatures=injection_signatures,
        ))
        # Dernier filet de sécurité : un candidat valide reste utile même si
        # son support est momentanément identique au meilleur global (les poids
        # continus peuvent encore être différents). Cela évite un réchauffage
        # stérile quand la réparation a temporairement convergé les supports.
        if not injections and viable.any():
            fallback_index = int(np.flatnonzero(viable)[
                int(np.argmin(candidate_energies[viable]))
            ])
            injections.append(
                (
                    float(candidate_energies[fallback_index]),
                    candidate_matrix[:, fallback_index].copy(),
                )
            )
        solver.population[0] = best_x.copy()
        solver.population_energies[0] = best_energy
        worst_indices = [
            int(index)
            for index in np.argsort(solver.population_energies)[::-1]
            if int(index) != 0
        ]
        for target, (energy, vector) in zip(worst_indices, injections, strict=False):
            solver.population[target] = vector
            solver.population_energies[target] = energy
            support_archive[:] = update_diverse_support_archive(
                support_archive,
                vector,
                energy,
                min_position=min_position,
                max_size=int(Config.STARR_LNS_ARCHIVE_SIZE),
                min_distance=float(Config.STARR_LNS_ARCHIVE_MIN_DISTANCE),
            )
        if hasattr(solver, "_promote_lowest_energy"):
            solver._promote_lowest_energy()

        best_candidate, best_candidate_score = None, float("-inf")
        if viable.any():
            best_index = int(np.flatnonzero(viable)[
                np.argmin(candidate_energies[viable])
            ])
            best_candidate = candidate_matrix[:, best_index].copy()
            best_candidate_score = -float(candidate_energies[best_index])
        return ({
            "parents": len(parents),
            "unique_other_parents": len(other_parents),
            "children": len(children),
            "random": random_target,
            "feasible": int(np.sum(viable)),
            "rejected": int(len(candidate_energies) - np.sum(viable)),
            "survivors": len(survivors),
            "injected": len(injections),
            "distinct_injected": len({
                support_signature(vector, min_position)
                for _energy, vector in injections
            }),
            "resets": int(reset_due),
        }, best_candidate, best_candidate_score)

    from collections import deque

    tabou: deque = deque(maxlen=int(Config.STARR_DE_TABU_SIZE))
    nonlocal_rejets = [0]
    temperature = float(Config.STARR_DE_T0)
    anchor_x = solver.x.copy()
    anchor_score = -float(solver.population_energies[0])
    best_x = anchor_x.copy()
    best_energy = float(solver.population_energies[0])
    support_archive: list[tuple[float, np.ndarray]] = [(best_energy, best_x.copy())]
    lns_moves = {"local": 0, "medium": 0, "large": 0, "global": 0}
    evolution_totals = {
        "generations": 0,
        "parents": 0,
        "unique_other_parents": 0,
        "children": 0,
        "random": 0,
        "feasible": 0,
        "rejected": 0,
        "survivors": 0,
        "injected": 0,
        "resets": 0,
    }
    nit = 0
    seed_iteration = 0
    seeds_completed = 0
    reported_iteration = 0
    best_energy_seen = float("inf")
    # Ancienneté de la stagnation, en générations CONSÉCUTIVES sans progrès réel.
    # Aucun délai de carence : dès la première génération qui n'améliore pas, on
    # stagne, et la température monte — de plus en plus vite tant que ça dure.
    stagnation_streak = 0
    hot_plateau_streak = 0
    rechauffages = 0
    rechauffages_steriles = 0
    rechauffages_renforces = 0
    exploration_epochs = 0
    forced_searches_completed = 0
    hot_cycles_completed = 0
    # Nombre de fois où l'ancre a QUITTÉ l'incumbent pour un autre bassin. Resté
    # structurellement nul tant que Metropolis comparait l'incumbent à lui-même.
    anchor_drifts = 0
    termination_reason = "max_generations"
    weight_refinement_passes = 0
    weight_refinement_improvements = 0

    def _polish_current_support(candidate: np.ndarray) -> tuple[np.ndarray, float, int]:
        """Affine uniquement les poids des lignes présentes dans la seed."""
        vector = np.asarray(candidate, dtype=float).reshape(-1)
        deployed, _counts, _costs = _deploy_batch(vector[:, None])
        active = np.flatnonzero(deployed[:, 0] > 1e-12)
        initial_energy = float(neg_obj_batch(vector[:, None])[0])
        if active.size <= 1:
            return vector.copy(), initial_energy, int(active.size)

        # Une descente en lots teste des transferts entre lignes avant le
        # simplex scalaire. Elle franchit aussi les paliers dus aux plafonds
        # et aux seuils d'exécution, que les petits pas initiaux de Nelder-Mead
        # prenaient souvent pour une convergence.
        refined, refined_energy = refine_portfolio_weights(
            vector,
            neg_obj_batch,
            active_indices=active,
            max_rounds=min(12, max(0, int(Config.STARR_DE_POLISH_MAXITER))),
        )
        if refined_energy < initial_energy:
            vector, initial_energy = refined, refined_energy
        reduced0 = np.maximum(vector[active], 1e-6)

        def _reduced_objective(values: np.ndarray) -> float:
            full = np.zeros(n_inv, dtype=float)
            full[active] = np.maximum(np.asarray(values, dtype=float), 0.0)
            return float(neg_obj_batch(full[:, None])[0])

        result = minimize(
            _reduced_objective,
            reduced0,
            method="Nelder-Mead",
            bounds=[(0.0, 1.0)] * len(active),
            options={
                "maxiter": max(
                    1,
                    min(
                        int(Config.STARR_SEED_SUPPORT_POLISH_MAXITER),
                        int(Config.STARR_DE_POLISH_MAXITER),
                    ),
                ),
                "xatol": 1e-5,
                "fatol": 1e-6,
                "adaptive": True,
            },
        )
        polished = np.zeros(n_inv, dtype=float)
        polished[active] = np.maximum(np.asarray(result.x, dtype=float), 0.0)
        energy = float(neg_obj_batch(polished[:, None])[0])
        if not np.isfinite(energy) or energy >= initial_energy:
            return vector.copy(), initial_energy, int(active.size)
        return polished, energy, int(active.size)

    def _run_forced_search(
        index: int,
        target_preference: float,
        target_global: float,
    ) -> tuple[np.ndarray, float, int, str]:
        """Amorce un bassin sous contrainte, puis l'optimise librement."""
        nonlocal reported_iteration, best_energy, best_x, global_best_energy, global_best_x, stop_requested
        kind = "ETF" if bool(is_etf_inv[index]) else "action"
        label = (
            f"{inv_tickers[index]} >= {target_global:.1%}"
            + (" (max broker)" if target_global < forced_floor - 1e-9 else "")
        )

        def forced_objective(X: np.ndarray) -> np.ndarray:
            return neg_obj_batch(apply_forced_floor_batch(X, index, target_preference))

        forced_anchor = apply_forced_floor_batch(
            anchor_x[:, None], index, target_preference
        )[:, 0]
        forced_population = build_init_population(
            n_inv,
            int(Config.STARR_DE_POPSIZE),
            pop_rng,
            scores,
            index,
            [forced_anchor],
            jitter=0.02,
            is_etf=is_etf_inv,
        )
        constrained_budget = max(
            1, int(Config.STARR_DE_FUNNEL_CONSTRAINED_GENERATIONS)
        )
        free_budget = max(1, int(Config.STARR_DE_FUNNEL_FREE_GENERATIONS))
        free_min = min(
            free_budget,
            max(1, int(Config.STARR_DE_FUNNEL_FREE_MIN_GENERATIONS)),
        )
        prune_margin = max(0.0, float(Config.STARR_DE_FUNNEL_PRUNE_MARGIN))
        forced_solver = DifferentialEvolutionSolver(
            forced_objective,
            bounds=bounds,
            rng=de_seed + 10_000 + index,
            maxiter=constrained_budget,
            tol=de_tol,
            mutation=(f_lo, f_hi),
            recombination=0.9,
            init=forced_population,
            polish=False,
            vectorized=True,
            updating="deferred",
        )
        local_generations = 0
        local_best_energy = float("inf")
        local_best_x = forced_anchor.copy()
        local_temperature = float(Config.STARR_DE_T0)
        local_stagnation_streak = 0
        for _ in forced_solver:
            time.sleep(max(0.0, float(Config.STARR_COOPERATIVE_YIELD_SECONDS)))
            local_generations += 1
            reported_iteration += 1
            energy = float(forced_solver.population_energies[0])
            candidate = apply_forced_floor_batch(
                forced_solver.x[:, None], index, target_preference
            )[:, 0]
            local_improved = is_real_improvement(
                energy, local_best_energy, absolute=min_improvement
            )
            local_gain = (
                relative_gain(energy, local_best_energy) if local_improved else 0.0
            )
            if local_improved:
                local_best_energy = energy
                local_best_x = candidate.copy()
                local_stagnation_streak = 0
            else:
                local_stagnation_streak += 1
            local_temperature = next_temperature(
                local_temperature,
                gain=local_gain,
                stagnation_streak=local_stagnation_streak,
                stop_requested=stop_requested,
            )
            # La recherche contrainte utilise la meme echelle de mutation que la
            # recherche principale. Elle commence donc vraiment a T=1, au lieu
            # d'afficher T=0 tout en gardant implicitement un dithering maximal.
            forced_solver.dither = [
                f_lo,
                f_lo + local_temperature * (f_hi - f_lo),
            ]
            if energy < best_energy:
                best_energy = energy
                best_x = candidate.copy()
            if energy < global_best_energy:
                global_best_energy = energy
                global_best_x = candidate.copy()
                _maybe_emit_progress(candidate)
            _maybe_emit_candidate(candidate)
            _report(
                seed_label,
                reported_iteration,
                forced_solver.convergence,
                -energy,
                -global_best_energy,
                local_temperature,
                [label] if local_generations == 1 else None,
                1 if kind == "action" and local_generations == 1 else 0,
                1 if kind == "ETF" and local_generations == 1 else 0,
                candidate,
                global_best_x,
            )
            if should_stop is not None and should_stop():
                stop_requested = True
                return local_best_x, local_best_energy, local_generations, "user_stop"
            if local_generations >= constrained_budget:
                break

        # La contrainte a seulement servi à franchir la frontière du bassin.
        # Elle est maintenant retirée : le ticker peut tomber à 5 %, 2 % ou 0 %.
        free_population = build_init_population(
            n_inv,
            int(Config.STARR_DE_POPSIZE),
            pop_rng,
            scores,
            index,
            [local_best_x, anchor_x],
            jitter=0.02,
            is_etf=is_etf_inv,
        )
        free_solver = DifferentialEvolutionSolver(
            neg_obj_batch,
            bounds=bounds,
            rng=de_seed + 20_000 + index,
            maxiter=free_budget,
            tol=de_tol,
            mutation=(f_lo, f_hi),
            recombination=0.9,
            init=free_population,
            polish=False,
            vectorized=True,
            updating="deferred",
        )
        free_temperature = float(Config.STARR_DE_T0)
        free_stagnation = 0
        free_reference = float("inf")
        free_generations = 0
        for _ in free_solver:
            time.sleep(max(0.0, float(Config.STARR_COOPERATIVE_YIELD_SECONDS)))
            free_generations += 1
            local_generations += 1
            reported_iteration += 1
            energy = float(free_solver.population_energies[0])
            candidate = free_solver.x.copy()
            improved_free = is_real_improvement(
                energy, free_reference, absolute=min_improvement
            )
            free_gain = (
                relative_gain(energy, free_reference) if improved_free else 0.0
            )
            if improved_free:
                free_reference = energy
                free_stagnation = 0
            else:
                free_stagnation += 1
            free_temperature = next_temperature(
                free_temperature,
                gain=free_gain,
                stagnation_streak=free_stagnation,
                stop_requested=stop_requested,
            )
            free_solver.dither = [
                f_lo, f_lo + free_temperature * (f_hi - f_lo)
            ]
            if energy < local_best_energy:
                local_best_energy = energy
                local_best_x = candidate.copy()
            if energy < best_energy:
                best_energy = energy
                best_x = candidate.copy()
            if energy < global_best_energy:
                global_best_energy = energy
                global_best_x = candidate.copy()
                _maybe_emit_progress(candidate)
            _maybe_emit_candidate(candidate)
            _report(
                seed_label,
                reported_iteration,
                free_solver.convergence,
                -energy,
                -global_best_energy,
                free_temperature,
                seed_vector=candidate,
                global_vector=global_best_x,
            )
            if should_stop is not None and should_stop():
                stop_requested = True
                return local_best_x, local_best_energy, local_generations, "user_stop"
            if (
                free_generations >= free_min
                and local_best_energy > global_best_energy + prune_margin
            ):
                return local_best_x, local_best_energy, local_generations, "elagage"
            if free_generations >= free_budget:
                return local_best_x, local_best_energy, local_generations, "budget"
        return local_best_x, local_best_energy, local_generations, "fin_solver"

    _repair_infeasible_previous_champion()

    while True:
        try:
            next(solver)
        except StopIteration:
            termination_reason = "fin_solver"
            break
        time.sleep(max(0.0, float(Config.STARR_COOPERATIVE_YIELD_SECONDS)))
        nit += 1
        seed_iteration += 1
        reported_iteration += 1
        stop_just_requested = False
        forced_labels_for_report: list[str] = []
        forced_action_count_for_report = 0
        forced_etf_count_for_report = 0
        ran_forced_search = False
        current_energy = float(solver.population_energies[0])
        if nit == 1:
            # Après la première itération, scipy a évalué toute la population
            # stratifiée. On capture son meilleur portefeuille avec action avant
            # que les réchauffages ne puissent remplacer les individus faibles.
            _scan_action_population(
                np.asarray(solver.population, dtype=float).T,
                np.asarray(solver.population_energies, dtype=float),
            )
        improved = is_real_improvement(
            current_energy, best_energy_seen, absolute=min_improvement
        )
        # Le refroidissement est proportionnel à ce que le progrès RAPPORTE, il
        # doit donc être mesuré AVANT que la référence ne soit déplacée.
        gain = relative_gain(current_energy, best_energy_seen) if improved else 0.0
        if improved:
            best_energy_seen = current_energy
            stagnation_streak = 0
            rechauffages_steriles = 0
        else:
            stagnation_streak += 1
        if current_energy < best_energy:
            best_energy = current_energy
            best_x = solver.x.copy()
        if bool(Config.STARR_LNS_ENABLED):
            archive_deployed, _archive_counts, _archive_costs = _deploy_batch(
                np.asarray(solver.x, dtype=float)[:, None]
            )
            archive_candidate = project_preferences_to_deployed_support(
                solver.x, archive_deployed[:, 0]
            )
            archive_energy = float(neg_obj_batch(archive_candidate[:, None])[0])
            if not np.isfinite(archive_energy) or (
                archive_energy >= INVALID_OBJECTIVE_ENERGY
            ):
                # Le vecteur brut reste la référence validée par cette
                # génération si la projection change exceptionnellement ses
                # contraintes. Il vaut mieux archiver ce point que perdre le
                # bassin à cause d'un score sentinelle.
                archive_candidate = solver.x.copy()
                archive_energy = current_energy
            _record_action_candidate(
                solver.x,
                current_energy,
                deployed=archive_deployed[:, 0],
            )
            support_archive = update_diverse_support_archive(
                support_archive,
                archive_candidate,
                archive_energy,
                min_position=min_position,
                max_size=int(Config.STARR_LNS_ARCHIVE_SIZE),
                min_distance=float(Config.STARR_LNS_ARCHIVE_MIN_DISTANCE),
            )
        if current_energy < global_best_energy:
            global_best_energy = current_energy
            global_best_x = solver.x.copy()
            _maybe_emit_progress(solver.x)
        _maybe_emit_candidate(solver.x)

        if not stop_requested and should_stop is not None and should_stop():
            # Le clic ne coupe pas à chaud. Il ouvre une phase de validation à
            # T=1 et remet son compteur à zéro : il faudra maintenant 30
            # générations consécutives sans progrès réel pour rendre le résultat.
            stop_requested = True
            stop_just_requested = True
            hot_plateau_streak = 0
            print(
                f"    * Arrêt demandé à la génération {nit} : validation à "
                f"T=1 jusqu'à {int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)} "
                "générations consécutives sans amélioration."
            )
        if stop_requested:
            temperature = float(Config.STARR_DE_T_MAX)
        else:
            temperature = next_temperature(
                temperature,
                gain=gain,
                stagnation_streak=stagnation_streak,
                stop_requested=False,
            )
        (
            evolution_stats,
            evolution_variant_x,
            evolution_variant_score,
        ) = _evolutionary_generation(temperature, stagnation_streak)
        # Affiner les pondérations PENDANT la recherche : sans ce passage,
        # chaque voisin changeait les titres et le support ne recevait une
        # optimisation locale qu'à la fin d'une seed, parfois des heures après.
        if stagnation_streak >= 5 and stagnation_streak % 5 == 0:
            refinement_deployed, _counts, _costs = _deploy_batch(best_x[:, None])
            refined_x, refined_energy = refine_portfolio_weights(
                best_x,
                neg_obj_batch,
                active_indices=np.flatnonzero(refinement_deployed[:, 0] > 1e-12),
                max_rounds=min(2, max(0, int(Config.STARR_DE_POLISH_MAXITER))),
            )
            weight_refinement_passes += 1
            if refined_energy < best_energy - 1e-10:
                weight_refinement_improvements += 1
                if evolution_variant_x is None or -refined_energy > evolution_variant_score:
                    evolution_variant_x = refined_x
                    evolution_variant_score = -refined_energy
        evolution_totals["generations"] += 1
        for key in (
            "parents",
            "unique_other_parents",
            "children",
            "random",
            "feasible",
            "rejected",
            "survivors",
            "injected",
            "resets",
        ):
            evolution_totals[key] += int(evolution_stats.get(key, 0))
        # La génération évolutive/LNS fait partie de la génération courante.
        # Elle peut découvrir un candidat meilleur après que le meilleur individu
        # du solveur DE a été lu ci-dessus. Dans ce cas, ce progrès doit aussi
        # réarmer la stagnation et le plateau chaud ; sinon on enregistrait bien
        # le nouveau score global, mais on déclenchait quand même un réchauffage
        # puis un changement de seed comme si rien n'avait progressé.
        generation_improved = improved
        evolution_improved = False
        if evolution_variant_x is not None:
            evolution_energy = -float(evolution_variant_score)
            evolution_improved = is_real_improvement(
                evolution_energy,
                best_energy_seen,
                absolute=min_improvement,
            )
            evolution_gain = (
                relative_gain(evolution_energy, best_energy_seen)
                if evolution_improved
                else 0.0
            )
            _record_action_candidate(
                evolution_variant_x,
                evolution_energy,
                verify_feasible=True,
            )
            if evolution_energy < best_energy:
                best_energy = evolution_energy
                best_x = evolution_variant_x.copy()
            if evolution_energy < global_best_energy:
                global_best_energy = evolution_energy
                global_best_x = evolution_variant_x.copy()
                _maybe_emit_progress(evolution_variant_x)
            if evolution_improved:
                generation_improved = True
                best_energy_seen = evolution_energy
                stagnation_streak = 0
                rechauffages_steriles = 0
                if not stop_requested:
                    # Le candidat évolutif a été découvert après le calcul de
                    # température de la génération. Refroidir maintenant afin
                    # que la génération suivante affine ce nouveau bassin.
                    temperature = next_temperature(
                        temperature,
                        gain=evolution_gain,
                        stagnation_streak=0,
                        stop_requested=False,
                    )
        # `_evolutionary_generation` protège l'élite avant de connaître le
        # meilleur enfant. Le remettre ici garantit que le candidat LNS retenu
        # participe immédiatement au prochain croisement DE, même s'il n'a pas
        # été sélectionné dans la liste d'injections à cause d'un support clone.
        if np.isfinite(best_energy):
            solver.population[0] = best_x.copy()
            solver.population_energies[0] = float(best_energy)
            if hasattr(solver, "_promote_lowest_energy"):
                solver._promote_lowest_energy()
        if not stop_just_requested:
            hot_plateau_streak = next_hot_plateau_streak(
                hot_plateau_streak,
                improved=generation_improved,
                # Les appels programmatiques sont bornés par le plafond de
                # réchauffages et doivent aussi pouvoir terminer sur un
                # plateau. Le mode continu conserve la définition stricte :
                # plateau uniquement après avoir atteint T_MAX.
                temperature=(
                    temperature
                    if continuous_until_stopped
                    else float(Config.STARR_DE_T_MAX)
                ),
            )

        if (
            stagnation_streak >= 1
            and not stop_requested
        ):
            # Le remaniement suit la température, il n'attend aucun compteur :
            # à T_MIN il ne touche qu'une poignée des pires individus, à T_MAX
            # un quart de la population. L'intensité de la réaction est donc
            # portée par la seule température, qui s'emballe avec la durée de la
            # stagnation — pas par un seuil « N générations avant d'agir ».
            signature = _support_of(solver.x)
            deja_vu = signature in tabou
            if deja_vu:
                # Reconvergence sur un optimum DÉJÀ visité. On le compte, mais on
                # ne touche PLUS à la température : elle est déjà en train de
                # s'emballer avec l'ancienneté de la stagnation, et le doublement
                # d'autrefois — conçu pour un réchauffage rare, un par fenêtre de
                # 40 générations — la propulsait au plafond en deux générations.
                # Une seule loi gouverne la température. Le tabou continue, lui,
                # d'écarter les variantes déjà explorées.
                rechauffages_renforces += 1
            else:
                tabou.append(signature)
            rechauffages += 1
            rechauffages_steriles += 1
            exploration_epochs += 1
            # `survivors` est le nombre fixe de lignées parentes (12 par
            # défaut), pas le nombre de candidats effectivement remplacés dans
            # la population. Afficher cette valeur donnait l'impression que le
            # réchauffage réinjectait toujours les mêmes 12 tickers.
            injectes = int(evolution_stats.get("injected", 0))
            supports_injectes = int(evolution_stats.get("distinct_injected", 0))
            variante_x = evolution_variant_x
            variante_score = evolution_variant_score
            forced_selected = np.empty(0, dtype=int)
            forced_preference_targets = np.empty(0)
            forced_deployed_targets = np.empty(0)
            if not bool(Config.STARR_LNS_ENABLED):
                # Le chemin sans LNS utilise le réchauffage explicite et son
                # entonnoir de probes. Il était devenu du code mort : `_reheat`
                # existait, mais n'était plus jamais appelé.
                (
                    injectes,
                    variante_x,
                    variante_score,
                    _forced_assignments,
                    forced_selected,
                    forced_preference_targets,
                    forced_deployed_targets,
                ) = _reheat(anchor_x, temperature)
                if len(forced_selected):
                    forced_labels_for_report = [
                        f"{inv_tickers[int(index)]} >= {float(target):.1%}"
                        for index, target in zip(
                            forced_selected,
                            forced_deployed_targets,
                            strict=True,
                        )
                    ]
                    forced_action_count_for_report = int(
                        np.sum(~is_etf_inv[forced_selected])
                    )
                    forced_etf_count_for_report = int(
                        np.sum(is_etf_inv[forced_selected])
                    )
            forced_count = len(forced_selected)
            forced_probes_injected += forced_count
            # T=1 déclenche l'entonnoir : court amorçage contraint, puis
            # optimisation libre bornée et élagage des bassins faibles.
            if forced_count and temperature >= float(Config.STARR_DE_T_MAX) - 1e-9:
                for forced_index, preference_target, deployed_target in zip(
                    forced_selected,
                    forced_preference_targets,
                    forced_deployed_targets,
                    strict=True,
                ):
                    ran_forced_search = True
                    explored_forced.add(int(forced_index))
                    forced_x, forced_energy, forced_generations, forced_reason = (
                        _run_forced_search(
                            int(forced_index),
                            float(preference_target),
                            float(deployed_target),
                        )
                    )
                    forced_searches_completed += 1
                    worst = int(np.argmax(solver.population_energies))
                    solver.population[worst] = forced_x
                    solver.population_energies[worst] = forced_energy
                    _record_action_candidate(
                        forced_x,
                        forced_energy,
                        verify_feasible=True,
                    )
                    print(
                        f"    * Bassin {inv_tickers[int(forced_index)]} "
                        f"terminée après {forced_generations} générations "
                        f"({forced_reason}), score={-forced_energy:.5f}"
                    )
                    if stop_requested:
                        break
                if hasattr(solver, "_promote_lowest_energy"):
                    solver._promote_lowest_energy()
                # La campagne bornée remplace le réchauffage de cette génération.
                temperature = float(Config.STARR_DE_T0)
                stagnation_streak = 0
                if stop_requested:
                    # Le clic a été capté dans un sous-solveur de l'entonnoir.
                    # Ses générations ne comptent pas dans les 20 générations
                    # de validation de la recherche principale.
                    hot_plateau_streak = 0
                    temperature = float(Config.STARR_DE_T_MAX)
                    print(
                        f"    * Arrêt demandé pendant l'entonnoir : validation "
                        f"à T=1 sur {int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)} "
                        "générations sans amélioration."
                    )
            # Acceptation de Metropolis ENTRE BASSINS. Le candidat est la
            # meilleure VARIANTE fraîchement tirée — un point au support neuf —
            # et non l'incumbent.
            #
            # C'est ici que se jouait l'immobilité des tickers : on proposait
            # auparavant `solver.x`, c'est-à-dire le meilleur individu, alors que
            # l'ancre valait déjà son score. Metropolis comparait donc un point à
            # LUI-MÊME : exp(0) = 1, acceptation systématique à toute température.
            # L'ancre recollait à l'incumbent à chaque tour, toutes les
            # perturbations repartaient du même portefeuille, et l'on revisitait
            # sans fin les mêmes supports (43 réchauffages sur 53 tombaient sur un
            # support déjà vu). Le basin hopping décrit ici n'avait jamais eu lieu.
            #
            # Avec un candidat réellement distinct, la règle retrouve son sens :
            # à froid on ne bouge que pour mieux, à chaud l'ancre accepte de
            # descendre et part explorer un autre bassin — donc d'autres titres.
            if variante_x is not None and accept_new_anchor(
                anchor_score, variante_score, temperature, float(pop_rng.random())
            ):
                anchor_x = np.asarray(variante_x, dtype=float).copy()
                anchor_score = float(variante_score)
                anchor_drifts += 1
            if rechauffages_steriles % 25 == 1:
                # Un réchauffage par génération de stagnation : on ne trace que
                # les jalons, sinon le journal du run devient illisible. Un
                # support déjà visité n'est plus un évènement rare non plus —
                # sur un plateau, c'est le cas ordinaire.
                print(
                    f"    * Réchauffage #{rechauffages} à la génération {nit} : "
                    f"stagnation depuis {stagnation_streak} gén., "
                    f"T={temperature:.3f}, {injectes} individus réinjectés "
                    f"({supports_injectes} supports distincts), "
                    f"{forced_count} bassins explorés par entonnoir"
                    f"{', support déjà visité' if deja_vu else ''}"
                )
        # Aucune remise à zéro de la température ici : SEUL un progrès réel la
        # fait redescendre, et proportionnellement à ce qu'il rapporte. Tant que
        # rien ne s'améliore, elle reste haute et la population continue d'être
        # tirée au hasard — la plupart de ces portefeuilles seront moins bons,
        # mais `best_x` est archivé HORS de la population et ne peut jamais être
        # dégradé. Si un tirage tombe sur mieux, le refroidissement ramène
        # aussitôt le solveur en exploitation.

        # F suit la température : à T=1 on retrouve le (0.5, 1.5) d'origine, à
        # T=0 la bande se referme sur f_lo (exploitation pure). `solver.scale`
        # est réécrit à chaque génération par le dithering : c'est `dither`,
        # et lui seul, qu'il faut piloter.
        solver.dither = [f_lo, f_lo + temperature * (f_hi - f_lo)]

        # Rapporter AVANT toute sortie de boucle : une génération effectuée doit
        # apparaître dans la courbe, même si un rafraîchissement ETF l'interrompt
        # juste après. Après le réchauffage, aussi : la température affichée est
        # celle qui a réellement piloté la génération, doublement anti-cyclage
        # compris.
        # Les DE contraints ont eux aussi publié leurs générations. Réserver un
        # nouvel index au point de la recherche principale évite de dupliquer le
        # dernier index contraint dans l'historique du graphe.
        if ran_forced_search:
            reported_iteration += 1
        _report(seed_label, seed_iteration, solver.convergence, -best_energy,
                -global_best_energy, temperature, forced_labels_for_report,
                forced_action_count_for_report, forced_etf_count_for_report,
                seed_vector=best_x, global_vector=global_best_x)

        if not stop_requested and should_restart is not None and should_restart():
            # La composition d'un ETF a été enrichie : l'objectif ne doit jamais
            # changer au milieu d'une population DE. On rend le meilleur point
            # courant au runner, qui reconstruira les matrices.
            restart_requested = True
            termination_reason = "etf_composition_refresh"
            print(
                f"    * Interrompu à la génération {nit} : nouvelle "
                "composition ETF disponible."
            )
            break

        if (
            not stop_requested
            and (
                hot_plateau_streak
                >= int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)
                or (
                    not continuous_until_stopped
                    and stagnation_streak
                    >= int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)
                )
            )
        ):
            if continuous_until_stopped and should_stop is not None:
                # Fin de seed : vérifier d'abord l'optimum des pondérations sur
                # son support, puis repartir d'une population réellement
                # indépendante. Le meilleur global reste hors de la population
                # neuve et ne peut jamais être perdu.
                polished_x, polished_energy, polished_lines = (
                    _polish_current_support(best_x)
                )
                if polished_energy < best_energy:
                    best_energy, best_x = polished_energy, polished_x.copy()
                if polished_energy < global_best_energy:
                    global_best_energy = polished_energy
                    global_best_x = polished_x.copy()
                    _maybe_emit_progress(polished_x)
                hot_cycles_completed += 1
                seeds_completed += 1
                next_seed_value = de_seed + hot_cycles_completed * 100_003
                fresh_population, fresh_start, fresh_energy = (
                    _independent_seed_population(next_seed_value)
                )
                for archived_energy, archived_x in support_archive:
                    validation_archive = update_diverse_support_archive(
                        validation_archive,
                        archived_x,
                        archived_energy,
                        min_position=min_position,
                        max_size=int(Config.STARR_LNS_ARCHIVE_SIZE),
                        min_distance=float(Config.STARR_LNS_ARCHIVE_MIN_DISTANCE),
                    )
                seed_label += 1
                seed_iteration = 0
                pop_rng = np.random.default_rng(next_seed_value)
                solver = _make_solver(fresh_population, next_seed_value)
                best_x = fresh_start.copy()
                best_energy = float(fresh_energy)
                best_energy_seen = float("inf")
                anchor_x = fresh_start.copy()
                anchor_score = -float(fresh_energy)
                support_archive = [(float(fresh_energy), fresh_start.copy())]
                evolution_parent_pool = []
                tabou.clear()
                hot_plateau_streak = 0
                stagnation_streak = 0
                rechauffages_steriles = 0
                temperature = float(Config.STARR_DE_T0)
                print(
                    f"    * Seed {seed_label - 1} terminée : polish de "
                    f"{polished_lines} lignes, score={-polished_energy:.5f}. "
                    f"Seed {seed_label} indépendante lancée à T={temperature:.2f}; "
                    f"meilleur global={-global_best_energy:.5f}."
                )
                continue
            else:
                termination_reason = "convergence_plateau_chaud"
                break
        if (
            stop_requested
            and hot_plateau_streak
            >= int(Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS)
        ):
            polished_x, polished_energy, polished_lines = _polish_current_support(best_x)
            if polished_energy < global_best_energy:
                global_best_energy = polished_energy
                global_best_x = polished_x.copy()
                _maybe_emit_progress(polished_x)
            print(
                f"    * Validation finale du support : {polished_lines} lignes, "
                f"score={-polished_energy:.5f}."
            )
            termination_reason = "convergence_apres_arret"
            break
        if not continuous_until_stopped:
            # Mode BORNÉ (tests, appels programmatiques) : la seed doit finir.
            if rechauffages_steriles >= int(Config.STARR_DE_MAX_REHEATS):
                termination_reason = "epuisement"
                break
        if (
            nit >= max_gen
            and not (continuous_until_stopped and should_stop is not None)
        ):
            break

    best_reason = termination_reason
    print(
        f"    * Recuit adaptatif : {nit} générations, {rechauffages} réchauffages "
        f"(dont {rechauffages_renforces} renforcés), {anchor_drifts} dérives "
        f"d'ancre, {nonlocal_rejets[0]} variantes rejetées par tabou, "
        f"T finale={temperature:.3f}, arrêt={best_reason}"
    )
    if best_reason == "max_generations":
        print(
            f"    * ATTENTION : le meilleur run a atteint le plafond de securite "
            f"({max_gen} generations) sans converger naturellement -> resultat "
            "potentiellement encore ameliorable (augmenter STARR_DE_MAX_GENERATIONS)."
        )

    # Dernière vérification du meilleur GLOBAL sur son seul support. Le polish en
    # dimension de tout l'univers dépensait son budget sur des milliers de zéros.
    best_x = global_best_x.copy()
    best_energy = float(global_best_energy)
    if not restart_requested:
        polished_x, polished_energy, polished_lines = _polish_current_support(best_x)
        if polished_energy < best_energy:
            print(
                f"    * Polish final ({polished_lines} lignes) : amelioration "
                f"{best_energy:.5f} -> {polished_energy:.5f}"
            )
            best_x, best_energy = polished_x, polished_energy
        else:
            print(
                f"    * Polish final ({polished_lines} lignes) : aucune amelioration."
            )
    else:
        print("    * Polish ignoré : reconstruction imminente des expositions ETF.")

    selected_execution = None
    executable_elites_validated = 0
    validation_details = {
        "elite_count": 0,
        "selected_rank": 1,
        "search_objective_score": float(-best_energy),
        "validation_objective_score": float(-best_energy),
        "validation_gap": 0.0,
        "stability": "stable",
    }
    if not restart_requested:
        # Le classement DE n'est qu'un classement d'entraînement. Réévaluer une
        # archive diverse sur l'intégralité des scénarios empêche un support
        # ayant sur-appris le sous-échantillon de devenir le portefeuille final.
        for archived_energy, archived_x in [
            *support_archive,
            (best_energy, best_x.copy()),
            (global_best_energy, global_best_x.copy()),
        ]:
            validation_archive = update_diverse_support_archive(
                validation_archive,
                archived_x,
                archived_energy,
                min_position=min_position,
                max_size=int(Config.STARR_LNS_ARCHIVE_SIZE),
                min_distance=float(Config.STARR_LNS_ARCHIVE_MIN_DISTANCE),
            )
        elite_vectors = [vector.copy() for _energy, vector in validation_archive]
        search_sim = sim_search
        search_bench = bench
        search_energies = np.asarray(
            neg_obj_batch(np.column_stack(elite_vectors)), dtype=float
        )
        sim_search = np.ascontiguousarray(sim_rets, dtype=np.float64)
        bench = bench_full
        validation_energies = np.asarray(
            neg_obj_batch(np.column_stack(elite_vectors)), dtype=float
        )
        selected_index = int(np.argmin(validation_energies))
        best_x = elite_vectors[selected_index].copy()
        best_energy = float(validation_energies[selected_index])
        # Rang qu'avait, pendant la recherche, le support finalement choisi par
        # la validation. Un rang > 1 rend visible le changement de classement.
        validation_rank = int(
            np.argsort(
                np.argsort(search_energies, kind="stable"), kind="stable"
            )[selected_index]
        ) + 1
        full_polished_x, full_polished_energy, full_polished_lines = (
            _polish_current_support(best_x)
        )
        if full_polished_energy < best_energy:
            best_x = full_polished_x
            best_energy = float(full_polished_energy)
            print(
                f"    * Polish validation complète ({full_polished_lines} lignes) : "
                f"score objectif {-best_energy:+.5f}."
            )
        if discretize_cb is not None:
            # L'arrondi peut inverser l'ordre des candidats. Choisir le gagnant
            # sur le portefeuille réellement achetable, avec LE MÊME objectif
            # (coûts, risque, diversification et cash) que pendant la recherche.
            execution_candidates = [best_x.copy(), *elite_vectors]
            seen_execution_weights: set[bytes] = set()
            for candidate in execution_candidates:
                _candidate_deployed, candidate_matrix = _to_broker_matrix(candidate)
                key = candidate_matrix.tobytes()
                if key in seen_execution_weights:
                    continue
                seen_execution_weights.add(key)
                result = _evaluate_executable_matrix(candidate_matrix)
                if result is None or result["objective_score"] is None:
                    continue
                executable_elites_validated += 1
                if (
                    selected_execution is None
                    or result["objective_score"] > selected_execution["objective_score"]
                ):
                    selected_execution = result
                    best_x = candidate.copy()
            if selected_execution is not None:
                best_energy = float(neg_obj_batch(best_x[:, None])[0])
        # Mesurer le même portefeuille final sur l'échantillon de recherche.
        full_sim = sim_search
        full_bench = bench
        sim_search = search_sim
        bench = search_bench
        selected_search_energy = float(neg_obj_batch(best_x[:, None])[0])
        sim_search = full_sim
        bench = full_bench
        search_objective_score = float(-selected_search_energy)
        validation_objective_score = float(-best_energy)
        validation_gap = validation_objective_score - search_objective_score
        absolute_gap = abs(validation_gap)
        stability = (
            "stable" if absolute_gap <= 1.0
            else "attention" if absolute_gap <= 3.0
            else "instable"
        )
        validation_details = {
            "elite_count": int(len(elite_vectors)),
            "selected_rank": validation_rank,
            "search_objective_score": search_objective_score,
            "validation_objective_score": validation_objective_score,
            "validation_gap": validation_gap,
            "stability": stability,
            "executable_elites_validated": int(executable_elites_validated),
            "selection_uses_executable_objective": bool(selected_execution is not None),
        }
        print(
            "    * Validation archive complète : "
            f"{len(elite_vectors)} élites, objectif recherche "
            f"{search_objective_score:+.4f}, validation "
            f"{validation_objective_score:+.4f}, écart {validation_gap:+.4f} "
            f"({stability})."
        )

    deployed_inv, W = _to_broker_matrix(best_x)
    if restart_requested:
        restart_diagnostics = {
            "schema_version": 4,
            "seed": int(seed),
            "termination": {
                "reason": "etf_composition_refresh",
                "continuous": bool(continuous_until_stopped),
                "generations": int(nit),
                "reheats": int(rechauffages),
                "temperature": float(temperature),
            },
        }
        if on_new_best is not None:
            try:
                on_new_best(W)
            except Exception:
                pass
        if return_diagnostics:
            return W, float(-best_energy), restart_diagnostics
        return W, float(-best_energy)
    transaction_cost_details = _portfolio_cost_details(W[inv_idx, :])

    # SCORE PUR (sans les pénalités, qui servent à orienter la recherche) — mesuré
    # sur le portefeuille sparse réellement déployé et validé par les contraintes
    # hard, sur les n_sim scénarios COMPLETS en float64 (la recherche DE
    # n'utilisait qu'un sous-échantillon float32, cf. STARR_N_SIM_SEARCH).
    starr = -neg_benchmark_relative(
        deployed_inv,
        sim_rets,
        mean_daily,
        bench,
        alpha,
        downside_weight,
        annual_cost=transaction_cost_details["first_year_cost_pct"],
        normalize_weights=False,
    )
    if not np.isfinite(starr):
        starr = 0.0
    print(
        f"    * Score final vs {Config.STARR_BENCHMARK_TICKER} : {starr:+.2f} points/an"
    )

    best_action_candidate = {
        "found": False,
        "unit": "points de % annuels vs benchmark",
    }
    if best_action_x is not None:
        action_deployed, action_W = _to_broker_matrix(best_action_x)
        action_costs = _portfolio_cost_details(action_W[inv_idx, :])
        action_score = -neg_benchmark_relative(
            action_deployed,
            sim_rets,
            mean_daily,
            bench,
            alpha,
            downside_weight,
            annual_cost=action_costs["first_year_cost_pct"],
            normalize_weights=False,
        )
        if np.isfinite(action_score):
            action_positions = np.flatnonzero(
                (~is_etf_inv) & (action_deployed > 1e-12)
            )
            best_action_candidate = {
                "found": True,
                "unit": "points de % annuels vs benchmark",
                "score": float(action_score),
                # Positif = le meilleur portefeuille libre reste supérieur.
                "score_gap_to_unrestricted": float(starr - action_score),
                "action_weight": float(action_deployed[~is_etf_inv].sum()),
                "action_count": int(action_positions.size),
                "action_tickers": [
                    inv_tickers[int(index)] for index in action_positions
                ],
                "search_objective_score": float(-best_action_energy),
                "selection_is_constrained": False,
            }
            print(
                "    * Meilleur candidat avec action : "
                f"{action_score:+.2f} points/an "
                f"(écart libre {starr - action_score:+.2f}, "
                f"{action_deployed[~is_etf_inv].sum():.1%} en actions)"
            )

    # ── Score du portefeuille RÉELLEMENT ACHETÉ ────────────────────────────────
    # `starr` ci-dessus porte sur des poids CONTINUS. L'appelant discrétise
    # ensuite en actions entières (et en pies Trading212), et jusqu'ici plus rien
    # ne rescorait le résultat : seule la conformité sectorielle était revérifiée.
    # L'écart d'arrondi, sur des lignes à forte valeur unitaire, restait invisible.
    # On rend donc la main à l'appelant pour qu'il produise la version exécutable,
    # et on la note avec EXACTEMENT le même estimateur (`neg_benchmark_relative`,
    # scénarios complets float64) : les deux scores sont ainsi comparables.
    previous_executed_score = None
    previous_execution = None
    if has_previous_champion and discretize_cb is not None:
        _previous_deployed, previous_W = _to_broker_matrix(champion_inv)
        previous_execution = _evaluate_executable_matrix(previous_W)
        if previous_execution is not None:
            previous_executed_score = previous_execution["score"]

    executed_portfolio = None
    if discretize_cb is not None:
        selected_execution = selected_execution or _evaluate_executable_matrix(W)
        executed_weights = (
            selected_execution["weights"] if selected_execution is not None else None
        )
        if executed_weights is not None:
            W_exec = np.asarray(executed_weights, dtype=float)
            if W_exec.shape != W.shape:
                print(
                    "    * Score du portefeuille exécuté ignoré : forme "
                    f"{W_exec.shape} != {W.shape}"
                )
            else:
                exec_broker = W_exec[inv_idx, :]
                exec_inv = exec_broker.sum(axis=1)
                exec_costs = _portfolio_cost_details(exec_broker)
                exec_score = selected_execution["score"]
                if exec_score is None:
                    exec_score = 0.0
                if not np.isfinite(exec_score):
                    exec_score = 0.0
                exec_counts = (exec_broker > 1e-12).sum(axis=0).reshape(-1, 1)
                exec_terms = _penalty_breakdown(exec_inv[:, None], exec_counts)
                exec_direct_weights = exec_inv[direct_action_mask]
                exec_direct_weight = float(exec_direct_weights.sum())
                exec_direct_lines = int(np.sum(exec_direct_weights > 1e-12))
                executed_portfolio = {
                    "unit": "points de % annuels vs benchmark",
                    "score": float(exec_score),
                    "objective_score": selected_execution["objective_score"],
                    "feasible_under_current_constraints": selected_execution[
                        "feasible_under_current_constraints"
                    ],
                    "score_continuous": float(starr),
                    # Négatif = la discrétisation a dégradé le portefeuille.
                    "drift": float(exec_score - starr),
                    "terms": {
                        key: float(value)
                        for key, value in sorted(
                            exec_terms.items(), key=lambda kv: -abs(kv[1])
                        )
                        if key != "cash_non_deploye_pct"
                    },
                    # Le callback contrôle la discrétisation réellement achetable
                    # (réserve de frais et routes secondaires incluses lorsqu'il
                    # les fournit). Le score ci-dessus porte exactement sur la
                    # matrice qu'il retourne.
                    "approximation": (
                        "dépend de la discrétisation fournie par l'appelant"
                    ),
                    "invested_weight": float(exec_inv.sum()),
                    "cash_weight": float(max(0.0, 1.0 - exec_inv.sum())),
                    "lines_by_broker": {
                        broker: int(exec_counts[index, 0])
                        for index, broker in enumerate(active_brokers)
                    },
                    "direct_action_weight": exec_direct_weight,
                    "direct_action_lines": exec_direct_lines,
                    "direct_action_policy_respected": bool(
                        (
                            direct_action_min_weight <= 0
                            or exec_direct_weight >= direct_action_min_weight - 1e-9
                        )
                        and (
                            direct_action_min_lines <= 0
                            or exec_direct_lines >= direct_action_min_lines
                        )
                    ),
                }
                print(
                    f"    * Score du portefeuille EXÉCUTÉ : {exec_score:+.2f} "
                    f"points/an (écart d'arrondi {exec_score - starr:+.2f})"
                )

    # Benchmarks déterministes et broker-aware : mêmes scénarios, mêmes budgets,
    # même matrice d'accès. Ils permettent de vérifier que la complexité du DE
    # apporte réellement quelque chose face à des règles triviales.
    def _full_starr(preferences: np.ndarray) -> float:
        actual, broker_matrix = _to_broker_matrix(preferences)
        costs = _portfolio_cost_details(broker_matrix[inv_idx, :])
        value = -neg_benchmark_relative(
            actual,
            sim_rets,
            mean_daily,
            bench,
            alpha,
            downside_weight,
            annual_cost=costs["first_year_cost_pct"],
            normalize_weights=False,
        )
        return float(value) if np.isfinite(value) else 0.0

    equal_weight_score = _full_starr(np.ones(n_inv, dtype=float))
    benchmark_indices = list(np.argsort(scores)[::-1][: min(20, n_inv)])
    for benchmark_ticker in ("CW8.PA", "SGOV"):
        if benchmark_ticker in inv_tickers:
            idx = inv_tickers.index(benchmark_ticker)
            if idx not in benchmark_indices:
                benchmark_indices.append(idx)

    best_single_ticker = None
    best_single_score = float("-inf")
    named_benchmarks: dict[str, float] = {}
    for idx in benchmark_indices:
        one_hot = np.zeros(n_inv, dtype=float)
        one_hot[idx] = 1.0
        value = _full_starr(one_hot)
        ticker = inv_tickers[idx]
        if ticker in {"CW8.PA", "SGOV"}:
            named_benchmarks[ticker] = value
        if value > best_single_score:
            best_single_score = value
            best_single_ticker = ticker

    sector_values = {
        sector: float(value)
        for sector, value in zip(
            sector_names, sector_mat.T @ deployed_inv, strict=True
        )
        if float(value) > 1e-12
    }
    sector_country_values = sector_country_exposures(
        deployed_inv,
        sector_labels,
        C_mat,
        all_countries,
        sector_matrix=sector_mat,
        sector_names=sector_names,
        joint_matrix=joint_mat,
    )
    sector_country_score = sector_country_diversification_score(
        deployed_inv,
        sector_labels,
        C_mat,
        sector_matrix=sector_mat,
        joint_matrix=joint_mat,
        country_names=all_countries,
        significant_exposure=sector_country_significant_exposure,
        significant_weight=sector_country_significant_weight,
    )
    _, final_risk_context = benchmark_relative_batch_details(
        deployed_inv[:, None],
        sim_rets,
        mean_daily,
        bench,
        alpha,
        downside_weight,
        annual_costs=transaction_cost_details["first_year_cost_pct"],
        normalize_weights=False,
    )
    final_sector_risk = sector_downside_risk_from_context(
        sim_rets,
        sector_labels,
        final_risk_context,
        downside_weight=downside_weight,
        sector_matrix=sector_mat,
        sector_names=sector_names,
    )
    final_risk_penalties, final_risk_exceeded = sector_downside_risk_penalty(
        final_sector_risk,
        max_risk_share=sector_risk_caps,
        coefficient=sector_risk_penalties,
    )
    annualization = float(np.sqrt(252.0))
    sector_risk_values = {
        sector: {
            "weight": float(sector_values.get(sector, 0.0)),
            "cvar_contribution": float(
                final_sector_risk["cvar_contributions"][index, 0] * annualization
            ),
            "downside_deviation_contribution": float(
                final_sector_risk["downside_contributions"][index, 0] * annualization
            ),
            "composite_risk_contribution": float(
                final_sector_risk["composite_contributions"][index, 0] * annualization
            ),
            "risk_share": float(final_sector_risk["risk_shares"][index, 0]),
            "risk_budget": float(sector_risk_caps[index]),
            "risk_budget_excess": max(
                0.0,
                float(final_sector_risk["risk_shares"][index, 0])
                - float(sector_risk_caps[index]),
            ),
        }
        for index, sector in enumerate(final_sector_risk["sectors"])
    }
    sector_risk_is_exceeded = bool(
        final_risk_exceeded[0] if len(final_risk_exceeded) else False
    )
    # Même attribution d'Euler, appliquée à l'axe géographique. `country_weights`
    # est l'exposition look-through réelle (un ETF monde est ventilé entre ses
    # pays), à ne pas confondre avec le poids du titre.
    final_country_risk = sector_downside_risk_from_context(
        sim_rets,
        [None] * len(inv_tickers),
        final_risk_context,
        downside_weight=downside_weight,
        sector_matrix=C_mat_risk,
        sector_names=risk_countries,
    ) if C_mat_risk.shape[1] else None
    country_weights_by_name = (
        {
            country: float(C_mat[:, index] @ deployed_inv)
            for index, country in enumerate(all_countries)
        }
        if C_mat.shape[1]
        else {}
    )
    country_risk_values = {
        country: {
            "weight": country_weights_by_name.get(country, 0.0),
            "cvar_contribution": float(
                final_country_risk["cvar_contributions"][index, 0] * annualization
            ),
            "downside_deviation_contribution": float(
                final_country_risk["downside_contributions"][index, 0] * annualization
            ),
            "composite_risk_contribution": float(
                final_country_risk["composite_contributions"][index, 0] * annualization
            ),
            "risk_share": float(final_country_risk["risk_shares"][index, 0]),
            "risk_budget_excess": max(
                0.0,
                float(final_country_risk["risk_shares"][index, 0])
                - max_country_risk_share,
            ),
        }
        for index, country in enumerate(final_country_risk["sectors"])
    } if final_country_risk is not None else {}
    country_risk_is_exceeded = any(
        values["risk_budget_excess"] > 1e-12 for values in country_risk_values.values()
    )
    final_region_risk = sector_downside_risk_from_context(
        sim_rets,
        [None] * len(inv_tickers),
        final_risk_context,
        downside_weight=downside_weight,
        sector_matrix=R_mat,
        sector_names=all_regions,
    ) if R_mat.shape[1] else None
    region_weights_by_name = {
        region: float(R_mat[:, index] @ deployed_inv)
        for index, region in enumerate(all_regions)
    }
    region_risk_values = {
        region: {
            "weight": region_weights_by_name.get(region, 0.0),
            "cvar_contribution": float(
                final_region_risk["cvar_contributions"][index, 0] * annualization
            ),
            "downside_deviation_contribution": float(
                final_region_risk["downside_contributions"][index, 0] * annualization
            ),
            "composite_risk_contribution": float(
                final_region_risk["composite_contributions"][index, 0] * annualization
            ),
            "risk_share": float(final_region_risk["risk_shares"][index, 0]),
            "risk_budget_excess": max(
                0.0,
                float(final_region_risk["risk_shares"][index, 0]) - max_region_risk_share,
            ),
        }
        for index, region in enumerate(final_region_risk["sectors"])
    } if final_region_risk is not None else {}
    final_action_weights = E_mat.T @ deployed_inv if E_mat.shape[1] else np.zeros(0)
    action_penalty_points = 0.0
    known_action_weight = float(final_action_weights.sum())
    final_unknown_equity_weight = float(unknown_equity_vec @ deployed_inv)
    action_hhi = float(
        np.sum((final_action_weights / known_action_weight) ** 2)
    ) if known_action_weight > 1e-12 else 0.0
    action_weights_by_name = {
        action: float(final_action_weights[index])
        for index, action in enumerate(economic_actions)
        if final_action_weights[index] > 1e-10
    }
    country_bonus_components = sector_country_diversification_components(
        deployed_inv,
        C_mat,
        sector_mat,
        joint_matrix=joint_mat,
        country_names=all_countries,
        significant_exposure=sector_country_significant_exposure,
        significant_weight=sector_country_significant_weight,
    )
    for index in range(min(len(sector_names), len(country_bonus_components))):
        if float(final_sector_risk["risk_shares"][index, 0]) > sector_risk_caps[index]:
            country_bonus_components[index] = 0.0
    country_bonus_points = sector_country_bonus * float(np.sum(country_bonus_components))
    geographic_factors = geographic_diversification_factors(
        C_mat.T @ deployed_inv[:, None],
        R_mat.T @ deployed_inv[:, None],
        country_names=all_countries,
        region_names=all_regions,
        significant_exposure=sector_country_significant_exposure,
        country_std_exponent=geographic_country_std_exponent,
        region_std_exponent=geographic_region_std_exponent,
    )
    geographic_bonus_points = geographic_bonus * float(
        geographic_factors["combined"][0]
    )
    country_deficit_points = sector_country_deficit_penalty(
        deployed_inv,
        C_mat,
        sector_mat,
        coefficient=sector_country_deficit_penalty_coefficient,
        medium_exposure=float(Config.STARR_SECTOR_COUNTRY_MEDIUM_EXPOSURE),
        large_exposure=float(Config.STARR_SECTOR_COUNTRY_LARGE_EXPOSURE),
        joint_matrix=joint_mat,
        country_names=all_countries,
    )
    final_broker_weights = W[inv_idx, :]
    final_line_counts = (final_broker_weights > 1e-12).sum(axis=0)
    # Ventilation du score du portefeuille RETENU : quel terme lui coûte quoi.
    _final_counts = (final_broker_weights > 1e-12).sum(axis=0).reshape(-1, 1)
    score_breakdown = _penalty_breakdown(deployed_inv[:, None], _final_counts)
    score_breakdown["risque_sectoriel"] = float(
        final_risk_penalties[0] if len(final_risk_penalties) else 0.0
    )
    score_breakdown["risque_pays"] = (
        float(
            sector_downside_risk_penalty(
                final_country_risk,
                max_risk_share=max_country_risk_share,
                coefficient=country_risk_penalty_coefficient,
            )[0][0]
        )
        if final_country_risk is not None and max_country_risk_share > 0
        else 0.0
    )
    score_breakdown["risque_region"] = (
        float(
            sector_downside_risk_penalty(
                final_region_risk,
                max_risk_share=max_region_risk_share,
                coefficient=region_risk_penalty_coefficient,
            )[0][0]
        )
        if final_region_risk is not None and max_region_risk_share > 0
        else 0.0
    )
    score_breakdown["concentration_action_economique"] = action_penalty_points
    # Seul terme FAVORABLE : il se retranche du score, d'où le signe négatif.
    score_breakdown["bonus_diversification"] = -float(country_bonus_points)
    score_breakdown["bonus_diversification_geographique"] = -float(
        geographic_bonus_points
    )
    score_breakdown["deficit_pays_par_secteur"] = float(country_deficit_points)
    final_broker_hhi: list[float] = []
    for broker_index in range(num_b):
        values = final_broker_weights[:, broker_index]
        invested = float(values.sum())
        final_broker_hhi.append(
            float(np.sum((values / invested) ** 2)) if invested > 1e-12 else 0.0
        )

    diagnostics = {
        "schema_version": 5,
        "seed": int(seed),
        "n_sim": int(n_sim),
        "n_search": int(n_search),
        "constraints_relaxed": not use_lookthrough_constraints,
        "world_constraint": {
            "index": "MSCI World",
            "minimum_weight": world_floor,
            "eligible_tickers": sorted(world_names & set(inv_tickers)),
            "actual_weight": float(deployed_inv[world_mask].sum()) if world_mask.any() else 0.0,
            "compliant": bool(
                world_floor <= 0
                or (world_mask.any() and float(deployed_inv[world_mask].sum()) >= world_floor - 1e-9)
            ),
        },
        "exploration_strategy": {
            "incumbent": "champion précédent réévalué avec les données courantes",
            "candidate_universe": "univers éligible courant actions + ETF",
            "stagnation_move": (
                "ajouts guidés par la corrélation au portefeuille global, "
                "avec une sonde déterministe d'un ticker à la fois, "
                "sans retester un ticker déjà sondé, puis le score standalone "
                "et les contraintes"
            ),
            "correlation_basis": "rendements convertis en EUR",
            "mixed_assets": bool(is_etf_inv.any() and (~is_etf_inv).any()),
            "replacement_requires_executable_improvement": True,
        },
        "asset_universe": {
            "actions_only": bool(actions_only_universe),
            "geographic_hard_constraints_disabled": bool(actions_only_universe),
            "geographic_soft_penalty_factor": float(geographic_soft_penalty_factor),
            "defensive_floor_enabled": bool(use_lookthrough_constraints),
            "defensive_floor_requested_pct": float(requested_min_defensive),
            "defensive_floor_effective_pct": float(min_def),
            "defensive_floor_relaxed_for_feasibility": bool(
                defensive_floor_relaxed
            ),
            "maximum_achievable_defensive_pct": (
                float(max_achievable_defensive)
                if max_achievable_defensive is not None
                else None
            ),
        },
        "best_action_candidate": best_action_candidate,
        # Score du portefeuille RÉELLEMENT ACHETÉ (actions entières / pies), à
        # comparer au score continu. `None` si l'appelant n'a pas fourni de
        # `discretize_cb`. `drift` négatif = l'arrondi a coûté.
        "executed_portfolio": executed_portfolio,
        # Décomposition du score retenu, en POINTS d'objectif. Positif = malus.
        # Permet de voir d'un coup d'œil quel terme pilote réellement
        # l'allocation, au lieu de constater un score global sans explication.
        "score_breakdown": {
            "unit": "points d'objectif (positif = pénalité)",
            "terms": {
                key: value
                for key, value in sorted(
                    score_breakdown.items(), key=lambda kv: -abs(kv[1])
                )
                if key != "cash_non_deploye_pct"
            },
            "total_penalty": float(
                sum(
                    value
                    for key, value in score_breakdown.items()
                    if key != "cash_non_deploye_pct"
                )
            ),
            "idle_cash_weight": float(score_breakdown.get("cash_non_deploye_pct", 0.0)),
            "dominant_term": max(
                (
                    (key, value)
                    for key, value in score_breakdown.items()
                    if key != "cash_non_deploye_pct"
                ),
                key=lambda kv: abs(kv[1]),
                default=("aucun", 0.0),
            )[0],
        },
        "sector_constraints": {
            "max_sector_pct": max_sector,
            "max_sector_pct_overrides": sector_caps.as_dict(),
            "exempt_diversified_etfs": False,
            "exposures": sector_values,
            "hhi": float(sum(value * value for value in sector_values.values())),
            "effective_sectors": (
                1.0 / float(sum(value * value for value in sector_values.values()))
                if sum(value * value for value in sector_values.values()) > 1e-12 else 0.0
            ),
            "cash_weight": max(0.0, 1.0 - float(np.sum(deployed_inv))),
            "compliant": all(
                value <= sector_caps.for_label(label) + 1e-9
                for label, value in sector_values.items()
            ),
            "downside_risk": {
                "method": "euler_cvar_plus_downside_deviation",
                "max_risk_share": max_sector_risk_share,
                "max_risk_share_overrides": sector_risk_cap_overrides,
                "penalty_coefficient": sector_risk_penalty_coefficient,
                "penalty_coefficient_overrides": sector_risk_penalty_overrides,
                "objective_penalty_points": float(
                    final_risk_penalties[0] if len(final_risk_penalties) else 0.0
                ),
                "budget_exceeded": sector_risk_is_exceeded,
                "sectors": sector_risk_values,
                "unclassified_assets_in_total_risk": True,
            },
            "country_diversification": {
                "method": "log_effective_countries_plus_significant_countries",
                "exposures": sector_country_values,
                "score": sector_country_score,
                "objective_bonus_points": country_bonus_points,
                "bonus_coefficient": float(sector_country_bonus),
                "significant_country_exposure": sector_country_significant_exposure,
                "significant_country_bonus_weight": sector_country_significant_weight,
                "applied_after_hard_caps": True,
                "disabled_by_sector_risk": False,
                "disabled_sectors_by_risk": [
                    sector_names[index]
                    for index in range(len(sector_names))
                    if float(final_sector_risk["risk_shares"][index, 0])
                    > sector_risk_caps[index]
                ],
                "deficit_penalty_points": country_deficit_points,
                "effective_country_targets": {
                    "5_to_10_pct": 2,
                    "above_10_pct": 3,
                },
                "global_bonus": {
                    "method": "exp(-k*std_pays) * exp(-k*std_regions) * log(1+n_pays_significatifs)",
                    "objective_bonus_points": geographic_bonus_points,
                    "bonus_coefficient": float(geographic_bonus),
                    "country_std": float(geographic_factors["country_std"][0]),
                    "region_std": float(geographic_factors["region_std"][0]),
                    "country_equality_factor": float(geographic_factors["country_equality"][0]),
                    "region_equality_factor": float(geographic_factors["region_equality"][0]),
                    "country_count_bonus": float(geographic_factors["country_count_bonus"][0]),
                    "significant_country_count": int(geographic_factors["country_count"][0]),
                    "country_coverage": float(geographic_factors["country_coverage"][0]),
                    "region_coverage": float(geographic_factors["region_coverage"][0]),
                    "country_std_exponent": geographic_country_std_exponent,
                    "region_std_exponent": geographic_region_std_exponent,
                    "multiplicative": True,
                },
            },
        },
        # Axe géographique, symétrique de `sector_constraints` : exposition
        # look-through par pays ET budget de risque baissier par pays.
        "country_constraints": {
            "hard_cap_enabled": country_hard_cap_enabled,
            "disabled_for_actions_only": bool(actions_only_universe),
            "max_country_pct": (max_country if country_hard_cap_enabled else None),
            "exposures": {
                country: country_weights_by_name.get(country, 0.0)
                for country in sorted(country_weights_by_name)
            },
            "hhi": float(sum(value * value for value in country_weights_by_name.values())),
            "effective_countries": (
                1.0 / float(sum(value * value for value in country_weights_by_name.values()))
                if sum(value * value for value in country_weights_by_name.values()) > 1e-12 else 0.0
            ),
            "compliant": all(
                value <= max_country + 1e-9
                for value in country_weights_by_name.values()
            ),
            "downside_risk": {
                "method": "euler_cvar_plus_downside_deviation",
                "max_risk_share": max_country_risk_share,
                "penalty_coefficient": country_risk_penalty_coefficient,
                "budget_exceeded": country_risk_is_exceeded,
                "countries": country_risk_values,
                "unclassified_assets_in_total_risk": True,
            },
        },
        "region_constraints": {
            "hard_cap_enabled": region_hard_cap_enabled,
            "disabled_for_actions_only": bool(actions_only_universe),
            "max_region_pct": max_region if region_hard_cap_enabled else None,
            "exposures": region_weights_by_name,
            "compliant": (not region_hard_cap_enabled) or all(
                value <= max_region + 1e-9
                for value in region_weights_by_name.values()
            ),
            "hhi": float(sum(value * value for value in region_weights_by_name.values())),
            "effective_regions": (
                1.0 / float(sum(value * value for value in region_weights_by_name.values()))
                if sum(value * value for value in region_weights_by_name.values()) > 1e-12 else 0.0
            ),
            "downside_risk": {
                "method": "euler_cvar_plus_downside_deviation",
                "max_risk_share": max_region_risk_share,
                "penalty_coefficient": region_risk_penalty_coefficient,
                "budget_exceeded": any(
                    value["risk_budget_excess"] > 1e-12
                    for value in region_risk_values.values()
                ),
                "regions": region_risk_values,
                "unclassified_assets_in_total_risk": True,
            },
        },
        "economic_action_concentration": {
            "descriptive_only": True,
            "coverage_weight": known_action_weight,
            "threshold": max_economic_action,
            "penalty_coefficient": 0.0,
            "objective_penalty_points": action_penalty_points,
            "hhi": action_hhi,
            "effective_actions": (1.0 / action_hhi if action_hhi > 1e-12 else 0.0),
            "largest_action": (
                max(action_weights_by_name, key=action_weights_by_name.get)
                if action_weights_by_name else None
            ),
            "largest_action_weight": max(action_weights_by_name.values(), default=0.0),
            "actions": dict(
                sorted(action_weights_by_name.items(), key=lambda item: -item[1])
            ),
        },
        "unknown_equity_composition": {
            "method": "descriptive_weighted_residual",
            "descriptive_only": True,
            "actual_weight": final_unknown_equity_weight,
            "by_ticker": {
                ticker: {
                    "portfolio_weight": float(deployed_inv[index]),
                    "unknown_fraction": float(unknown_equity_vec[index]),
                    "unknown_contribution": float(
                        deployed_inv[index] * unknown_equity_vec[index]
                    ),
                }
                for index, ticker in enumerate(inv_tickers)
                if deployed_inv[index] * unknown_equity_vec[index] > 1e-10
            },
        },
        "selected_etf_exposures": {
            ticker: {
                "portfolio_weight": float(deployed_inv[index]),
                "countries": dict(paysmap.get(ticker, {})),
                "source": "official_constituents_or_exact_physical_proxy",
            }
            for index, ticker in enumerate(inv_tickers)
            if is_etf_inv[index] and deployed_inv[index] > 1e-10
        },
        "line_diversification": {
            "minimum_per_broker": None,
            "broker_concentration_penalty_enabled": False,
            "hard_max_per_broker": max_per_broker,
            "effective_max_by_broker": {
                broker: int(broker_line_caps[index])
                for index, broker in enumerate(active_brokers)
            },
            "lines_by_broker": {
                broker: int(final_line_counts[index])
                for index, broker in enumerate(active_brokers)
            },
            "hhi_by_broker": {
                broker: final_broker_hhi[index]
                for index, broker in enumerate(active_brokers)
            },
            "effective_lines_by_broker": {
                broker: (
                    1.0 / final_broker_hhi[index]
                    if final_broker_hhi[index] > 1e-12
                    else 0.0
                )
                for index, broker in enumerate(active_brokers)
            },
        },
        "direct_action_policy": {
            "enabled": direct_action_policy_enabled,
            "mandatory": False,
            "minimum_weight": direct_action_min_weight,
            "minimum_lines": direct_action_min_lines,
            "eligible_action_candidates": direct_action_candidates,
            "actual_weight": float(deployed_inv[direct_action_mask].sum()),
            "actual_lines": int(np.sum(deployed_inv[direct_action_mask] >= max(min_position, 1e-12))),
            "executed_weight": (
                executed_portfolio.get("direct_action_weight")
                if executed_portfolio is not None
                else None
            ),
            "executed_lines": (
                executed_portfolio.get("direct_action_lines")
                if executed_portfolio is not None
                else None
            ),
            "executed_policy_respected": (
                executed_portfolio.get("direct_action_policy_respected")
                if executed_portfolio is not None
                else None
            ),
            "quality_bonus_max_points": direct_action_quality_bonus,
            "quality_bonus_points": float(
                direct_action_quality_bonus * (direct_action_quality @ deployed_inv)
            ),
        },
        "base_currency": "EUR",
        "estimation": {
            "mean_window_observations": int(len(R_mean)),
            "mean_signal_weight": float(mean_signal_weight),
            "mean_prior": "per_asset_class_median",
            "class_priors": {
                name: {
                    "n": int(sum(1 for c in ticker_classes if c == name)),
                    "annual_pct": float(
                        np.median([
                            raw_mean_daily[i]
                            for i, c in enumerate(ticker_classes)
                            if c == name and np.isfinite(raw_mean_daily[i])
                        ]) * 252.0 * 100.0
                    ),
                }
                for name in sorted({c for c in ticker_classes if c is not None})
                if any(
                    c == name and np.isfinite(raw_mean_daily[i])
                    for i, c in enumerate(ticker_classes)
                )
            },
            "correlation_shrinkage": float(Config.STARR_CORRELATION_SHRINKAGE),
        },
        "benchmark_relative": {
            "ticker": str(Config.STARR_BENCHMARK_TICKER),
            "in_universe": bool(bench_pos is not None),
            "annual_return_pct": float(bench["annual_return"] * 100.0),
            "cvar_pct": float(bench["cvar"] * 100.0),
            "downside_deviation_pct": float(bench["downside_deviation"] * 100.0),
            "score_unit": "points de rendement annuel vs benchmark",
            **validation_details,
        },
        "previous_run_champion": {
            "available": bool(has_previous_champion),
            "accepted_as_initial_incumbent": bool(previous_champion_accepted),
            "feasible_under_current_constraints": bool(previous_champion_feasible),
            "repaired_before_optimization": bool(previous_champion_repaired),
            "repaired_score": (
                float(previous_champion_repair_score)
                if previous_champion_repair_score is not None
                else None
            ),
            "rejection_reason": previous_champion_rejection_reason,
            "input_weight": float(champion_input_total),
            "retained_in_current_universe_weight": float(champion_retained_total),
            "recomputed_score": (
                float(previous_champion_display_score)
                if previous_champion_display_score is not None
                else None
            ),
            "recomputed_executed_score": (
                float(previous_executed_score)
                if previous_executed_score is not None
                else None
            ),
            "recomputed_executed_objective_score": (
                previous_execution["objective_score"]
                if previous_execution is not None else None
            ),
            "executed_feasible_under_current_constraints": (
                previous_execution["feasible_under_current_constraints"]
                if previous_execution is not None else None
            ),
            "defensive_floor_requested_pct": float(requested_min_defensive),
            "defensive_floor_effective_pct": float(min_def),
            "score_recomputed_with_current_run_inputs": bool(previous_champion_accepted),
            "score_recomputed_after_discretization": bool(
                previous_executed_score is not None
            ),
        },
        "current_weights_available": bool(has_current_weights),
        "transaction_costs": {
            **transaction_cost_details,
            "base_currency": "EUR",
            "bourse_direct_tariff_effective": "2026-01-06",
            "ttf_tickers_recognized": int(transaction_cost_model.ttf_mask.sum()),
            "notes": [
                "Bourse Direct : barème PEA en ligne et plafond UE/EEE de 0,5 %.",
                "Trading 212 : courtage/garde à 0 et change à 0,15 %.",
                "Taxes UK : stamp duty à l'achat et PTM au-delà de £10 000.",
                "FINRA omise faute de quantité d'actions ; SEC actuellement à 0 %.",
            ],
        },
        "regimes": {
            **regime_diagnostics,
            "mean_window_observations": int(len(R_mean)),
            "correlation_stability": correlation_diagnostics,
        },
        # Recuit lent à l'intérieur de chaque seed, puis redémarrages indépendants.
        "termination": {
            "reason": (
                "user_stop" if stop_requested
                else "etf_composition_refresh" if restart_requested
                else best_reason
            ),
            # `reason` dit QUI a arrêté ; `detail` dit COMMENT la boucle a
            # effectivement conclu. Depuis l'ajout de la sortie par stagnation,
            # un arrêt demandé peut se terminer de deux façons — par convergence
            # de la population ou par absence d'amélioration à froid — et seule
            # cette clé permet de savoir laquelle, donc de régler la fenêtre.
            "detail": best_reason,
            "continuous": bool(continuous_until_stopped),
            "generations": int(nit),
            "generation_budget": int(max_gen),
            # Générations consécutives sans progrès réel à la fin du run. Il n'y
            # a plus de fenêtre de stagnation à exposer : la stagnation se compte
            # génération par génération, sans délai de carence.
            "stagnation_streak": int(stagnation_streak),
            "hot_plateau_streak": int(hot_plateau_streak),
            "hot_convergence_generations": int(
                Config.STARR_DE_HOT_CONVERGENCE_GENERATIONS
            ),
            "hot_cycles_completed": int(hot_cycles_completed),
            "independent_seeds_completed": int(seeds_completed),
            "current_seed_number": int(seed_label),
            "persistent_until_stopped": bool(
                continuous_until_stopped and should_stop is not None
            ),
            "min_improvement": min_improvement,
            "weight_refinement": {
                "passes_during_search": int(weight_refinement_passes),
                "improvements_during_search": int(weight_refinement_improvements),
                "method": "batched_budget_transfers_then_adaptive_nelder_mead",
            },
            "annealing": {
                "temperature_final": float(temperature),
                "temperature_initial": float(Config.STARR_DE_T0),
                "linear_heating_step": float(Config.STARR_DE_HEATING),
                "reheats": int(rechauffages),
                "reheats_reinforced": int(rechauffages_renforces),
                "anchor_drifts": int(anchor_drifts),
                "sterile_reheats": int(rechauffages_steriles),
                "tabu_rejections": int(nonlocal_rejets[0]),
                "visited_supports": int(len(tabou)),
                "exploration_epochs": int(exploration_epochs),
                "forced_searches_completed": int(forced_searches_completed),
                "forced_floor": float(Config.STARR_DE_FORCED_FLOOR),
                "probe_floors": [float(value) for value in probe_floors],
                "funnel_constrained_generations": int(
                    Config.STARR_DE_FUNNEL_CONSTRAINED_GENERATIONS
                ),
                "funnel_free_generations": int(
                    Config.STARR_DE_FUNNEL_FREE_GENERATIONS
                ),
                "funnel_free_min_generations": int(
                    Config.STARR_DE_FUNNEL_FREE_MIN_GENERATIONS
                ),
                "funnel_prune_margin": float(Config.STARR_DE_FUNNEL_PRUNE_MARGIN),
                "forced_probes_tested": int(forced_probes_tested),
                "forced_probes_injected": int(forced_probes_injected),
        "large_neighborhood_search": {
            "enabled": bool(Config.STARR_LNS_ENABLED),
            "archive_size": int(len(support_archive)),
                    "archive_capacity": int(Config.STARR_LNS_ARCHIVE_SIZE),
                    "minimum_support_distance": float(
                        Config.STARR_LNS_ARCHIVE_MIN_DISTANCE
                    ),
            "moves": dict(lns_moves),
            "correlation_singleton_probed": int(len(singleton_probed_indices)),
        },
                "evolutionary_generation": {
                    "global_best_protected": True,
                    "other_parent_target": int(Config.STARR_EVOLUTION_PARENT_COUNT),
                    "children_per_parent": int(
                        Config.STARR_EVOLUTION_CHILDREN_PER_PARENT
                    ),
                    "geography_children_per_parent": int(
                        Config.STARR_EVOLUTION_GEOGRAPHY_CHILDREN
                    ),
                    "random_candidates_per_generation": int(
                        Config.STARR_EVOLUTION_RANDOM_CANDIDATES
                    ),
                    "minimum_parent_distance": float(
                        Config.STARR_EVOLUTION_MIN_PARENT_DISTANCE
                    ),
                    **{key: int(value) for key, value in evolution_totals.items()},
                },
            },
        },
        "benchmarks": {
            "optimized": float(starr),
            "equal_weight": float(equal_weight_score),
            "equal_weight_max_lines_per_broker": max_per_broker,
            "equal_weight_effective_max_by_broker": {
                broker: int(broker_line_caps[index])
                for index, broker in enumerate(active_brokers)
            },
            "best_single_ticker": best_single_ticker,
            "best_single": float(best_single_score),
            "best_single_candidates_tested": len(benchmark_indices),
            **named_benchmarks,
        },
    }
    print(f"    * Benchmarks reproductibles (seed={seed}) : {diagnostics['benchmarks']}")

    if on_new_best is not None:
        try:
            on_new_best(W)
        except Exception:
            pass  # la progression ne doit jamais casser le retour du résultat final

    if return_diagnostics:
        return W, starr, diagnostics
    return W, starr
