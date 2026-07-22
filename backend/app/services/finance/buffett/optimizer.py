"""Optimiseur de portefeuille STARR via Monte Carlo + copule de Vine."""

from __future__ import annotations

import time

import numpy as np
from scipy import stats
from scipy.optimize import LinearConstraint, minimize

from .config import Config


def _get_active_brokers() -> list[str]:
    return [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]


def _is_true(val) -> bool:
    import pandas as pd

    if pd.isna(val) or str(val).strip() == "":
        return True
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
    }
    broker_cols = [c for c in df.columns if c not in base_cols]
    active = _get_active_brokers()
    matrix = []
    for t in tickers:
        rows = df[df[ticker_col] == t]
        row_acc = []
        for b in active:
            col = _get_broker_col(b, broker_cols)
            access = True
            if col and not rows.empty:
                v = rows.iloc[0][col]
                if not pd.isna(v):
                    access = _is_true(v)
            row_acc.append(access)
        matrix.append(row_acc)
    return matrix, active


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


def project_lookthrough_hard(
    w0,
    d_vec,
    C_mat,
    min_def: float,
    max_country: float,
    is_etf,
    max_position: float,
) -> np.ndarray:
    """Projette ``w0`` (poids DE, simplexe) sur le portefeuille le plus proche
    (moindres carrés) qui respecte STRICTEMENT, simultanément :
    - Σw = 1, 0 ≤ wᵢ (ETF non plafonnés, actions ≤ ``max_position``) ;
    - défensif : Σ wᵢ·défensifᵢ ≥ ``min_def`` ;
    - pays : Σ wᵢ·paysᵢ,X ≤ ``max_country`` pour chaque pays X.

    Remplace ``cap_stock_weights`` + la pénalité douce de ``constraint_penalty``
    comme mécanisme d'application final : contrairement à un malus quadratique
    dans l'objectif DE (que l'optimiseur peut « payer » si le gain STARR le
    justifie), ici la contrainte est vérifiée exactement sur le résultat retenu.

    Si le polytope est infaisable (ex. bornes par action incompatibles avec
    Σw=1, ou pays trop stricts) on relâche d'abord la contrainte pays, puis
    en dernier recours on retombe sur ``cap_stock_weights`` (comportement
    précédent, sans garantie défensif/pays — même repli que l'ancien code
    quand aucun actif défensif n'est disponible).
    """
    w0 = np.asarray(w0, dtype=float)
    n = len(w0)
    s0 = float(w0.sum())
    w0 = w0 / s0 if s0 > 0 else np.full(n, 1.0 / n)

    caps = np.where(np.asarray(is_etf, dtype=bool), 1.0, float(max_position))
    caps = np.maximum(caps, 1e-6)
    bounds = [(0.0, float(c)) for c in caps]

    has_def = d_vec is not None and len(d_vec) and float(np.max(d_vec)) > 0
    has_country = C_mat is not None and getattr(C_mat, "size", 0)

    def _solve(with_country: bool) -> np.ndarray | None:
        cons = [LinearConstraint(np.ones(n), 1.0, 1.0)]
        if has_def:
            cons.append(LinearConstraint(np.asarray(d_vec, dtype=float), min_def, np.inf))
        if with_country and has_country:
            cons.append(LinearConstraint(np.asarray(C_mat, dtype=float).T, -np.inf, max_country))
        res = minimize(
            lambda w: float(np.sum((w - w0) ** 2)),
            w0,
            jac=lambda w: 2.0 * (w - w0),
            bounds=bounds,
            constraints=cons,
            method="SLSQP",
            options={"maxiter": 200, "ftol": 1e-10},
        )
        if not res.success:
            return None
        w = np.clip(np.asarray(res.x, dtype=float), 0.0, None)
        s = float(w.sum())
        return w / s if s > 0 else None

    if not has_def and not has_country:
        return cap_stock_weights(w0, is_etf, max_position)

    w = _solve(with_country=True)
    if w is None and has_country:
        w = _solve(with_country=False)  # relâche pays, garde le défensif (prioritaire)
    if w is None:
        return cap_stock_weights(w0, is_etf, max_position)  # infaisable -> repli
    return w


def split_budget_to_brokers(
    w, access, b_ratios, min_position: float = 0.0, fallback_max_lines: int | None = None
) -> np.ndarray:
    """Déploie le budget de chaque broker sur ses titres AFFECTÉS, au prorata du poids
    optimiseur ``w`` (somme 1). Retourne W [n_tickers × n_brokers, fraction du capital
    total].

    Cantonnement strict : chaque titre pondéré est acheté chez UN SEUL broker
    (cf. ``assign_tickers_to_brokers``, heuristique min-dérive) — un titre partagé
    n'apparaît donc plus chez les deux.
    - ``min_position`` : les titres dont le poids < seuil ne sont PAS achetés (micro-
      lignes) ; leur part est redéployée sur les titres gardés du même broker via la
      normalisation prorata (l'argent reste investi).
    - Débordement : si le poids cible cumulé des titres affectés à un broker dépasse
      son budget, la normalisation prorata plafonne et redéploie l'excédent sur ces
      mêmes titres (dérive de poids, jamais un 2e broker).
    - Fallback anti-cash-oisif : un broker sans titre affecté mais avec du budget et
      des titres disponibles replie sur ses dispos, PLAFONNÉ à ``fallback_max_lines``
      lignes (défaut : ``Config.STARR_MAX_LINES_PER_BROKER``), top-poids d'abord
      (seule entorse au strict 1-titre-1-broker, pour ne pas laisser de budget oisif).
    """
    w = np.asarray(w, dtype=float)
    num_t = len(w)
    num_b = len(b_ratios)
    if fallback_max_lines is None:
        fallback_max_lines = int(Config.STARR_MAX_LINES_PER_BROKER)
    W = np.zeros((num_t, num_b))
    assign = assign_tickers_to_brokers(w, access, b_ratios, min_position)
    for j in range(num_b):
        if b_ratios[j] <= 0:
            continue
        kept = [i for i in range(num_t) if assign[i] == j]
        tot = sum(w[i] for i in kept)
        if tot <= 0:
            # Broker « affamé » : le cantonnement min-dérive a affecté tous les titres
            # pondérés ailleurs (budgets inégaux), ou aucun de ses titres dispo n'est
            # pondéré (candidat DE concentré, ex. mono-ETF chez T212 — #bug run 39).
            # Repli sur ses dispos >= seuil, sinon tous ses dispos, TOUJOURS plafonné
            # à fallback_max_lines lignes (top-poids d'abord) : jamais de pulvérisation
            # équipondérée sur tout l'univers (~2000 micro-lignes « 1 action », que le
            # malus — qui ne compte que les lignes AFFECTÉES — ne voit pas).
            cand = [i for i in range(num_t) if access[i][j] and w[i] >= min_position]
            if not cand:
                cand = [i for i in range(num_t) if access[i][j]]
            cand.sort(key=lambda i: w[i], reverse=True)
            cand = cand[: max(1, fallback_max_lines)]
            tot_av = sum(w[i] for i in cand)
            if tot_av > 0:
                for i in cand:
                    W[i, j] = b_ratios[j] * w[i] / tot_av
            elif cand:
                share = b_ratios[j] / len(cand)  # poids tous nuls -> équipondéré
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
) -> np.ndarray:
    """Population initiale SPARSE pour le DE, [max(pop_size, lignes requises) × n].

    Le latin hypercube par défaut démarre avec ~n titres pondérés à la fois
    (STARR médiocre, malus de cardinalité dès que ça se concentre) et laisse
    scipy créer popsize×n individus. Ici la population est concentrée d'emblée :
    - 1 individu mono-titre ``seed_idx`` (ETF monde / meilleur standalone) ;
    - one-hots des 5 meilleurs scores standalone + top-20/top-40 équipondérés ;
    - ``warm_starts`` (meilleurs x des seeds précédents) + une copie bruitée ;
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
    for x in warm_starts or []:
        x = np.clip(np.asarray(x, dtype=float), 0.0, 1.0)
        rows.append(x)
        rows.append(np.clip(x + rng.normal(0.0, 0.02, n), 0.0, 1.0))
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


class PositiveSeedNotFound(RuntimeError):
    """Aucun point de depart positif trouve dans le budget d'essais imparti."""


def find_positive_random_seed(
    n: int,
    rng: np.random.Generator,
    objective,
    *,
    batch_size: int,
    max_batches: int,
    progress_cb=None,
    should_stop=None,
) -> tuple[np.ndarray, float, int]:
    """Cherche un portefeuille aléatoire dont l'objectif pénalisé est positif.

    ``objective`` suit la convention de scipy et retourne une énergie à minimiser;
    le score affiché est donc ``-énergie``. Une absence de solution positive est
    signalée avant le DE afin de ne pas gaspiller des milliers de générations.
    """
    maximum = max(1, int(max_batches))
    best_score = float("-inf")
    best_vector: np.ndarray | None = None
    for batch_num in range(1, maximum + 1):
        candidates = build_random_sparse_population(n, batch_size, rng)
        energies = np.asarray(objective(candidates.T), dtype=float).reshape(-1)
        finite = np.flatnonzero(np.isfinite(energies))
        if finite.size:
            idx = int(finite[np.argmin(energies[finite])])
            score = -float(energies[idx])
            if score > best_score:
                best_score = score
                best_vector = candidates[idx].copy()
        if progress_cb is not None:
            progress_cb(batch_num, maximum, best_score if np.isfinite(best_score) else None)
        if best_vector is not None and best_score > 0:
            return best_vector, best_score, batch_num
        if should_stop is not None and should_stop():
            raise RuntimeError("Optimisation arrêtée pendant la recherche initiale positive.")

    tested = maximum * max(1, int(batch_size))
    raise PositiveSeedNotFound(
        "Aucun portefeuille à score positif trouvé après "
        f"{tested:,} essais aléatoires. Vérifiez les rendements et les contraintes."
    )


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
    progress_cb=None,  # callable(seed_num:int, iteration:int, convergence:float, best_score:float) | None
    initialization_cb=None,  # callable(batch_num:int, max_batches:int, best_score:float|None)
    on_new_best=None,  # callable(W: np.ndarray[n_tickers x n_brokers]) | None
    should_stop=None,  # callable() -> bool | None -- verifie entre deux GENERATIONS
    # (jamais au milieu d'une) et entre deux seeds : l'arret
    # demande prend effet en ~1 generation, plus en ~1 seed
    # (un seed sur ~2900 titres peut durer des jours).
    # Sans callback : s'arrete apres exactement 1 seed (defaut sur).
    n_sim: int | None = None,
    alpha: float | None = None,
    downside_weight: float | None = None,
    min_position: float | None = None,
    current_weights: dict[str, float] | None = None,
    ttf_tickers: set[str] | None = None,
    benchmark_returns=None,   # pd.Series de rendements EUR du benchmark
    return_diagnostics: bool = False,
):
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
    # Classe semi-privée mais stable de scipy : nécessaire pour piloter le DE
    # génération par génération (arrêt sur convergence naturelle avec un minimum
    # de générations), ce que la fonction publique differential_evolution() ne
    # permet pas (elle n'expose qu'un maxiter dur + un callback qui ne peut
    # qu'arrêter plus tôt, jamais empêcher un arrêt prématuré).
    from scipy.optimize._differentialevolution import DifferentialEvolutionSolver

    from .starr import (
        benchmark_stats,
        correlation_stability_diagnostics,
        neg_benchmark_relative,
        neg_benchmark_relative_batch,
        simulate_regime_scenarios,
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
    mean_window_days = max(1, int(Config.STARR_MEAN_WINDOW_DAYS))
    R_mean = R[-min(len(R), mean_window_days):]
    raw_mean_daily = R_mean.mean(axis=0)
    mean_signal_weight = min(max(float(Config.STARR_MEAN_SIGNAL_WEIGHT), 0.0), 1.0)
    # Prior par CLASSE d'actif et non mediane globale : tirer une obligation vers la
    # mediane de tout l'univers (15,79 %/an mesure) lui offrait ~9 points de
    # rendement fictif tout en lui laissant son risque quasi nul -- c'est ce qui
    # faisait allouer 96 % du portefeuille a un ETF monetaire.
    from .broker_availability import load_asset_classes

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
    bench = benchmark_stats(bench_sim, bench_mean_daily, alpha, 0.0)
    print(
        f"    * Benchmark : rendement {bench['annual_return'] * 100:.2f} %, "
        f"CVaR {bench['cvar'] * 100:.2f} %, "
        f"baisse {bench['downside_deviation'] * 100:.2f} %"
    )
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
            f"{correlation_diagnostics['n_pairs']} paires instables (Δ≥0,25), "
            f"{correlation_diagnostics['major_shift_pairs']} changements majeurs (Δ≥0,40)"
        )

    current_full = np.array(
        [max(float((current_weights or {}).get(str(t), 0.0) or 0.0), 0.0) for t in tickers],
        dtype=float,
    )
    current_inv = current_full[inv_idx]
    current_total = float(current_inv.sum())
    has_current_weights = current_total > 1e-12
    if has_current_weights:
        current_inv /= current_total
    # Plus de penalite de turnover : elle faisait DOUBLON avec les frais de
    # transaction, qui modelisent deja le cout en euros des ordres (x
    # REBALANCES_PER_YEAR). `current_inv` reste necessaire pour ces frais et pour
    # amorcer la population avec le portefeuille reellement detenu.

    # ── Contraintes look-through (défensif min, pays max) ────────────────────
    from .lookthrough import fill_unknown_countries, load_lookthrough

    min_def = float(Config.MIN_DEFENSIVE_PCT)
    max_country = float(Config.MAX_COUNTRY_PCT)
    pen_k = float(Config.CONSTRAINT_PENALTY)
    inv_tickers = [str(tickers[i]).upper() for i in inv_idx]
    try:
        defmap, paysmap = load_lookthrough()
    except Exception:
        defmap, paysmap = {}, {}
    # Un ticker sans pays connu (ex. ETC or/argent physiques) compterait pour 0%
    # dans CHAQUE pays -> invisible au plafond MAX_COUNTRY_PCT. Réparti au prorata
    # de la répartition moyenne des tickers connus (décision utilisateur #buffett).
    paysmap = fill_unknown_countries(paysmap, inv_tickers)
    d_vec = np.array([defmap.get(t, 0.0) for t in inv_tickers], dtype=float)
    all_countries = sorted({c for t in inv_tickers for c in (paysmap.get(t) or {})})
    cidx = {c: j for j, c in enumerate(all_countries)}
    C_mat = np.zeros((len(inv_tickers), len(all_countries)))
    for i, t in enumerate(inv_tickers):
        for c, v in (paysmap.get(t) or {}).items():
            C_mat[i, cidx[c]] = v
    print(
        f"    * Contraintes : defensif>={min_def:.0%} (dispo {float(d_vec.max() if len(d_vec) else 0):.0%} max), "
        f"pays<={max_country:.0%} ({len(all_countries)} pays)"
    )

    # ── Optimisation niveau TICKER (simplexe sum=1) sur l'objectif STARR ─────
    n_inv = len(inv_idx)
    bounds = [(0.0, 1.0)] * n_inv
    is_etf_inv = is_etf_full[inv_idx]
    from app.services.finance import fx

    from .transaction_costs import TransactionCostModel

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
    trade_cost_multiplier = (
        float(Config.REBALANCES_PER_YEAR) if has_current_weights else 1.0
    )

    # Recherche DE sur un SOUS-ÉCHANTILLON de scénarios en float32 : le coût est
    # dominé par le produit sim @ W (bande passante mémoire), et cette précision
    # suffit largement pour COMPARER des candidats entre eux. Le STARR final est
    # recalculé sur les n_sim scénarios complets en float64 (cf. fin).
    n_search = max(1, min(n_sim, int(Config.STARR_N_SIM_SEARCH)))
    sim_search = np.ascontiguousarray(sim_rets[:n_search], dtype=np.float32)

    use_lookthrough_constraints = True
    # Initialisé uniformément puis remplacé, avant la première évaluation, par
    # un classement déterministe des scores standalone. Sert uniquement si un
    # candidat ne donne aucun titre à un broker ayant pourtant du budget.
    fallback_preferences = np.ones(n_inv, dtype=float)

    def _broker_allocation_batch(preferences: np.ndarray, broker_index: int) -> np.ndarray:
        """Allocation normalisée d'un broker, vectorisée sur tous les candidats."""
        available = access_inv[:, broker_index, None]
        offered = np.where(available, preferences, 0.0)
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

        # Le plafond de lignes est appliqué avant normalisation, de façon
        # identique dans l'objectif et dans l'allocation finale.
        if selected.shape[0] > max_per_broker:
            top_idx = np.argpartition(selected, -max_per_broker, axis=0)[-max_per_broker:]
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

    # La provenance broker des positions existantes n'est pas persistée. On la
    # reconstruit avec la même matrice d'accès et les mêmes budgets que la cible.
    current_broker_weights = np.zeros((n_inv, num_b), dtype=float)
    if has_current_weights:
        for j in range(num_b):
            current_broker_weights[:, j] = (
                b_ratios[j] * _broker_allocation_batch(current_inv[:, None], j)[:, 0]
            )

    def _deploy_batch(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
        for j in range(num_b):
            allocation = _broker_allocation_batch(preferences, j)
            broker_weights = b_ratios[j] * allocation
            deployed += broker_weights
            counts[j] = (allocation > 1e-12).sum(axis=0)
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

    def _deploy_one(preferences: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Version unitaire retournant aussi la matrice ticker × broker."""
        raw = np.maximum(np.asarray(preferences, dtype=float), 0.0)
        total = float(raw.sum())
        normalized = raw / total if total > 1e-12 else raw
        broker_weights = np.zeros((n_inv, num_b), dtype=float)
        for j in range(num_b):
            allocation = _broker_allocation_batch(normalized[:, None], j)[:, 0]
            broker_weights[:, j] = b_ratios[j] * allocation
        deployed = broker_weights.sum(axis=1)
        deployed_total = float(deployed.sum())
        if deployed_total > 1e-12:
            deployed /= deployed_total
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
        annualized_total = (
            trade_total * trade_cost_multiplier + holding_total
        )
        return {
            "enabled": transaction_costs_enabled,
            "trade_cost_eur": trade_total,
            "trade_cost_pct": trade_total / total_cap,
            "annual_custody_eur": holding_total,
            "annualized_cost_eur": annualized_total,
            "annualized_cost_pct": annualized_total / total_cap,
            "rebalances_per_year": int(Config.REBALANCES_PER_YEAR),
            "trade_cost_multiplier": trade_cost_multiplier,
            "brokers": per_broker,
        }

    def neg_obj_batch(X: np.ndarray) -> np.ndarray:
        """Objectif STARR pénalisé, vectorisé sur la population entière.

        ``X`` : [n_inv × S] (convention scipy ``vectorized=True``) ; retourne [S].
        Une seule passe BLAS pour toute la population (remplace l'ancien pool de
        threads qui évaluait individu par individu). Mêmes formules que
        ``per_broker_cardinality_penalty`` / ``constraint_penalty``, en batch.
        """
        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X[:, None]
        Xp = np.maximum(X, 0.0)
        s = Xp.sum(axis=0)
        ok = s > 1e-12
        deployed, counts, annual_costs = _deploy_batch(Xp)
        base = neg_benchmark_relative_batch(
            deployed, sim_search, mean_daily, bench, alpha, downside_weight,
            annual_costs=annual_costs,
        )
        if ok.any():
            W = deployed[:, ok]
            pen = np.zeros(W.shape[1])
            if card_beta > 0:
                excess = counts[:, ok] - max_per_broker
                pen += np.where(
                    excess > 0, np.exp(np.minimum(card_beta * excess, 700.0)) - 1.0, 0.0
                ).sum(axis=0)
            # Contraintes look-through (défensif / pays). Si elles empêchent
            # toute initialisation positive (notamment un PEA concentré sur un
            # ETF monde), la seconde passe les désactive, mais conserve les
            # autres règles telles que la cardinalité par broker.
            if use_lookthrough_constraints:
                if len(d_vec) and float(np.max(d_vec)) > 0:
                    short = np.maximum(min_def - (d_vec @ W), 0.0)
                    pen += pen_k * short * short
                if C_mat.size:
                    over = np.maximum((C_mat.T @ W) - max_country, 0.0)
                    pen += pen_k * np.sum(over * over, axis=0)
            base[ok] += pen
        return base

    def neg_obj(x: np.ndarray) -> float:
        """Version scalaire (polish Nelder-Mead) — mêmes numériques que le batch."""
        return float(neg_obj_batch(np.asarray(x, dtype=float)[:, None])[0])

    # ── Population initiale SPARSE : partir de portefeuilles concentrés déjà
    # bons — dont « 1 seul ETF monde » — plutôt que du latin hypercube qui
    # pondère tout l'univers à la fois (STARR de départ médiocre + malus de
    # cardinalité, et population scipy de popsize×n individus).
    scores = ticker_standalone_scores(sim_search, mean_daily, alpha, downside_weight)
    standalone_order = np.argsort(scores)[::-1]
    fallback_preferences = np.zeros(n_inv, dtype=float)
    fallback_preferences[standalone_order] = np.arange(n_inv, 0, -1, dtype=float)
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

    def _find_positive_seed(search_seed: int):
        return find_positive_random_seed(
            n_inv,
            np.random.default_rng(search_seed),
            neg_obj_batch,
            batch_size=init_batch_size,
            max_batches=init_max_batches,
            progress_cb=initialization_cb,
            should_stop=should_stop,
        )

    try:
        positive_seed, positive_score, positive_batch = _find_positive_seed(seed)
    except PositiveSeedNotFound:
        use_lookthrough_constraints = False
        print(
            "    * Aucun portefeuille positif avec les contraintes look-through; "
            "nouvelle tentative sans minimum defensif ni plafond par pays."
        )
        try:
            positive_seed, positive_score, positive_batch = _find_positive_seed(seed + 1)
        except PositiveSeedNotFound as exc:
            tested = init_batch_size * init_max_batches
            raise PositiveSeedNotFound(
                "Aucun portefeuille à score positif trouvé, même sans minimum "
                f"défensif ni plafond par pays, après {tested:,} nouveaux essais aléatoires."
            ) from exc
    print(
        "    * Initialisation positive : "
        f"score={positive_score:.5f}, trouvé au lot aléatoire #{positive_batch}"
    )

    def _report(seed_num: int, iteration: int, convergence: float, best_score: float) -> None:
        if progress_cb is not None:
            try:
                progress_cb(seed_num, iteration, float(convergence), float(best_score))
            except Exception:
                pass  # la progression ne doit jamais casser l'optimisation

    min_gen = int(Config.STARR_DE_MIN_GENERATIONS)
    max_gen = int(Config.STARR_DE_MAX_GENERATIONS)  # garde-fou, pas l'arrêt normal
    de_tol = float(Config.STARR_DE_TOL)
    stagnation_generations = max(1, int(Config.STARR_DE_STAGNATION_GENERATIONS))
    min_improvement = max(0.0, float(Config.STARR_DE_MIN_IMPROVEMENT))
    max_seeds = max(1, int(Config.STARR_DE_MAX_SEEDS))

    # ── Conversion vecteur DE brut -> allocation par broker, réutilisée pour le
    # résultat final ET les mises à jour progressives (on_new_best). Applique la
    # contrainte DURE (projette sur le portefeuille faisable le plus proche qui
    # respecte exactement défensif/pays/plafond par action -- remplace le plafond
    # + la pénalité douce, qui ne servaient qu'à guider la recherche DE).
    def _to_broker_matrix(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        raw = np.maximum(x, 0.0)
        s = raw.sum()
        w_inv = raw / s if s > 0 else raw
        if use_lookthrough_constraints:
            w_inv = project_lookthrough_hard(
                w_inv,
                d_vec,
                C_mat,
                min_def,
                max_country,
                is_etf_inv,
                max_position,
            )
        else:
            # Le plafond par action reste actif; les ETF comme CW8.PA en sont
            # déjà exemptés car ils sont diversifiés en look-through.
            w_inv = cap_stock_weights(w_inv, is_etf_inv, max_position)
        deployed_inv, W_inv = _deploy_one(w_inv)
        W = np.zeros((num_t, num_b), dtype=float)
        W[inv_idx, :] = W_inv
        return deployed_inv, W

    _last_emit_t = 0.0

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

    # Le DE part obligatoirement d'un portefeuille positif. Cette énergie est
    # partagée entre tous les seeds et ne peut donc jamais régresser sous zéro.
    global_best_energy = -positive_score

    # ── Seeds illimités : chaque nouveau départ (rng=seed+k, toujours distinct)
    # explore le paysage différemment. On garde le meilleur de tous les seeds
    # faits et on logge l'écart entre eux (mesure de robustesse : si les
    # scores divergent fort d'un seed à l'autre, le paysage a plusieurs optima
    # locaux comparables). S'arrête quand should_stop() renvoie True, vérifié
    # entre deux GENERATIONS (jamais au milieu d'une) : avant, l'arrêt n'était
    # pris en compte qu'entre deux seeds -- intenable depuis que l'univers fait
    # ~2900 titres (un seed = des jours). Un seed interrompu reste un candidat
    # valide (meilleur individu trouvé jusqu'ici) mais est marqué comme tel
    # dans les stats de robustesse. Sans should_stop : 1 seul seed
    # (comportement par défaut sûr, jamais de boucle infinie).
    # Les seeds suivants sont WARM-STARTÉS : le meilleur x de chaque seed fini
    # est réinjecté dans la population initiale des suivants (+ copie bruitée).
    runs = []  # (energie, x, nit, raison_arret)
    k = 0
    stop_requested = False
    # Une seule seed (STARR_DE_MAX_SEEDS = 1) amorcee par le portefeuille
    # REELLEMENT detenu : le DE part de l'existant au lieu d'un tirage arbitraire.
    # Le reste de la population conserve la couverture de l'univers (chaque titre
    # apparait dans au moins un individu), sans quoi le DE n'aurait aucune
    # diversite genetique et les coordonnees nulles le resteraient a jamais.
    warm_starts: list[np.ndarray] = [positive_seed]
    if has_current_weights:
        warm_starts.insert(0, current_inv.copy())
    while True:
        init_pop = build_init_population(
            n_inv,
            int(Config.STARR_DE_POPSIZE),
            np.random.default_rng(seed + k),
            scores,
            seed_pos,
            warm_starts,
        )
        if k == 0:
            print(
                f"    * DE vectorise : population {init_pop.shape[0]} individus "
                f"(init sparse, depart mono-titre "
                f"{inv_tickers[seed_pos] if seed_pos is not None else 'aucun'}), "
                f"recherche sur {n_search} scenarios float32"
            )
        solver = DifferentialEvolutionSolver(
            neg_obj_batch,  # vectorized=True : toute la population en 1 matmul BLAS
            bounds=bounds,
            rng=seed + k,
            maxiter=max_gen,
            tol=de_tol,
            mutation=(0.5, 1.5),
            recombination=0.9,
            init=init_pop,  # fixe AUSSI la taille de population (vs popsize×n de scipy)
            polish=False,  # CVaR non lisse -> pas de polish gradient ici (fait après, cf. plus bas)
            vectorized=True,
            updating="deferred",
        )
        nit = 0
        seed_best_energy = float("inf")
        last_improvement_iteration = 0
        termination_reason = "max_generations"
        for _ in solver:
            nit += 1
            current_energy = float(solver.population_energies[0])
            if current_energy < seed_best_energy - min_improvement:
                seed_best_energy = current_energy
                last_improvement_iteration = nit
            if solver.population_energies[0] < global_best_energy:
                global_best_energy = float(solver.population_energies[0])
                _maybe_emit_progress(solver.x)
            # -energie : objectif STARR pénalisé (pas un STARR pur, cf. neg_obj)
            # à MAXIMISER -- croissant au fil des générations pour le graphe
            # d'évolution en direct côté front.
            _report(k + 1, nit, solver.convergence, -global_best_energy)
            if nit >= min_gen and solver.converged():
                termination_reason = "convergence"
                break
            if (
                nit >= min_gen
                and nit - last_improvement_iteration >= stagnation_generations
            ):
                termination_reason = "stagnation"
                print(
                    f"    * Seed #{k + 1} arrêté pour stagnation : aucune amélioration "
                    f"> {min_improvement:g} depuis {stagnation_generations} générations."
                )
                break
            if nit >= max_gen:
                break
            if should_stop is not None and should_stop():
                stop_requested = True
                termination_reason = "user_stop"
                print(
                    f"    * Arret demande -> seed #{k} interrompu apres {nit} generation(s) "
                    "(meilleur portefeuille conserve)"
                )
                break
        runs.append(
            (float(solver.population_energies[0]), solver.x.copy(), nit, termination_reason)
        )
        warm_starts.append(solver.x.copy())
        k += 1
        if stop_requested or should_stop is None or should_stop() or k >= max_seeds:
            break

    energies = [r[0] for r in runs]
    best_idx = int(np.argmin(energies))
    best_energy, best_x, best_nit, best_reason = runs[best_idx]
    spread = float(np.std(energies))
    print(
        f"    * DE multi-seed ({len(runs)} depart(s)) : energies={[round(e, 4) for e in energies]}, "
        f"retenu=seed#{best_idx} (nit={best_nit}/{max_gen}, "
        f"arrêt={best_reason}), "
        f"ecart-type inter-seeds={spread:.4f}"
    )
    if best_reason == "max_generations":
        print(
            f"    * ATTENTION : le meilleur run a atteint le plafond de securite "
            f"({max_gen} generations) sans converger naturellement -> resultat "
            "potentiellement encore ameliorable (augmenter STARR_DE_MAX_GENERATIONS)."
        )

    # ── Polish local gradient-free (CVaR non lisse -> pas de gradient exploitable,
    # Nelder-Mead n'en a pas besoin) autour du meilleur point trouvé.
    polish = minimize(
        neg_obj,
        best_x,
        method="Nelder-Mead",
        bounds=bounds,
        options={"maxiter": int(Config.STARR_DE_POLISH_MAXITER), "xatol": 1e-6, "fatol": 1e-9},
    )
    # On accepte l'amélioration dès que le score est meilleur, même sans
    # polish.success : Nelder-Mead ne « converge » jamais en ~1000+ dimensions
    # avec un budget d'itérations borné, mais son meilleur point reste valide.
    if np.isfinite(polish.fun) and float(polish.fun) < best_energy:
        print(
            f"    * Polish (Nelder-Mead) : amelioration {best_energy:.5f} -> {float(polish.fun):.5f}"
        )
        best_x = np.asarray(polish.x, dtype=float)
    else:
        print(
            f"    * Polish (Nelder-Mead) : aucune amelioration "
            f"({float(polish.fun):.5f} >= {best_energy:.5f})"
        )

    deployed_inv, W = _to_broker_matrix(best_x)
    transaction_cost_details = _portfolio_cost_details(W[inv_idx, :])

    # SCORE PUR (sans le malus de cardinalité, qui ne sert qu'à orienter
    # l'optimiseur) — mesuré sur le portefeuille final déjà projeté (contraintes
    # garanties), sur les n_sim scénarios COMPLETS en float64 (la recherche DE
    # n'utilisait qu'un sous-échantillon float32, cf. STARR_N_SIM_SEARCH).
    starr = -neg_benchmark_relative(
        deployed_inv,
        sim_rets,
        mean_daily,
        bench,
        alpha,
        downside_weight,
        annual_cost=transaction_cost_details["annualized_cost_pct"],
    )
    if not np.isfinite(starr):
        starr = 0.0
    print(
        f"    * Score final vs {Config.STARR_BENCHMARK_TICKER} : {starr:+.2f} points/an"
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
            annual_cost=costs["annualized_cost_pct"],
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

    diagnostics = {
        "schema_version": 3,
        "seed": int(seed),
        "n_sim": int(n_sim),
        "n_search": int(n_search),
        "constraints_relaxed": not use_lookthrough_constraints,
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
        "termination": {
            "reason": "user_stop" if stop_requested else "bounded_multi_seed",
            "max_seeds": max_seeds,
            "seeds_run": len(runs),
            "stagnation_generations": stagnation_generations,
            "min_improvement": min_improvement,
            "runs": [
                {"seed": int(seed + i), "generations": int(run[2]), "reason": run[3]}
                for i, run in enumerate(runs)
            ],
        },
        "benchmarks": {
            "optimized": float(starr),
            "equal_weight": float(equal_weight_score),
            "equal_weight_max_lines_per_broker": max_per_broker,
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
