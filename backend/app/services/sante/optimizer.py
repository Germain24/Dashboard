"""Optimiseur SLSQP du plan nutrition (port du legacy `optimize_nutrition`).

Différences avec le legacy :
- Lit les aliments depuis la DB (DataFrame fourni par `aliments.load_aliments_dataframe`)
  au lieu de relire le CSV à chaque appel.
- `budget_max_daily` est explicite (paramètre) au lieu d'être lu dans `targets['Prix_Max']`.
  Si None, on utilise `targets.get('Prix_Max', 18.0)`.
- Toute la logique métier (poids des nutriments, contraintes, bounds) est
  conservée à l'identique pour ne pas régresser la qualité des plans.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.services.sante.constants import (
    DEFAULT_PRIX_MAX_DAILY,
    NUTRIENT_KEY_TO_CSV,
    STAPLE_KEYWORDS,
    TRACKED_MAX_NUTRIENTS,
)
from app.services.sante.pantry_fenetre import normalize_stock_lots

# Mapping (clé métier → colonne CSV) pour les nutriments utilisés par l'optimiseur.
# On garde uniquement ceux du legacy.
_OPT_NUTRIENT_MAP: list[tuple[str, str]] = [
    ("Calories", "Energie"),
    ("Protéines", "Proteines"),
    ("Lipides", "Lipides"),
    ("Glucides", "Glucides"),
    ("Fibres", "Fibres"),
    ("Magnésium", "Magnesium"),
    ("Sodium_Max", "Sodium"),
    ("Cholesterol_Max", "Cholesterol"),
    ("Omega3", "Omega 3"),
    ("VitA", "VitA"),
    ("VitB1", "VitB1"),
    ("VitB2", "VitB2"),
    ("VitB3", "VitB3"),
    ("VitB5", "VitB5"),
    ("VitB6", "VitB6"),
    ("VitB9", "VitB9"),
    ("VitB12", "VitB12"),
    ("VitC", "VitC"),
    ("VitD", "VitD"),
    ("VitE", "VitE"),
    ("VitK", "VitK"),
    ("Calcium", "Calcium"),
    ("Fer", "Fer"),
    ("Zinc", "Zinc"),
    ("Potassium", "Potassium"),
    ("Iode", "Iode"),
    ("Sélénium", "Selenium"),
    ("Phosphore", "Phosphore"),
    ("Sucres_Max", "TotalSugars"),
    ("AGSatures_Max", "AG satures"),
]

_WEIGHTS: dict[str, float] = {
    "Energie": 1000.0,
    "Proteines": 1000.0,
    "Lipides": 1000.0,
    "Glucides": 1000.0,
    "TotalSugars": 500.0,
    "Sodium": 500.0,
    "Cholesterol": 500.0,
    "AG satures": 500.0,
}

# Au carré, un écart de 23 % pouvait encore être échangé contre quelques
# dollars. Le terme quartique rend les gros écarts rapidement coûteux tout en
# restant doux autour de 100 %.
MACRO_TAIL_MULTIPLIER = 4.0

# Poids par défaut des nutriments non listés ci-dessus = TOUS les micronutriments
# (Mg, Fer, Zinc, Ca, K, Iode, Sélénium, Phosphore, vitamines…) + Fibres + Oméga-3.
# Historiquement à 1.0, ils pesaient 100 à 1000× moins que les macros : l'optimiseur
# atteignait le plancher calorique au moindre coût (riz/pâtes) en ignorant les micros.
# Relevé à 25 pour qu'il poursuive réellement les cibles micro tout en laissant les
# macros (100-1000) et le coût rester dominants. Les contraintes dures (calories,
# protéines, budget) restent prioritaires.
MICRO_WEIGHT = 25.0

# ── Objectif « couverture équilibrée » (no nutrient left behind) ──────────────
# Les MACROS (calories/prot/lip/gluc) se visent des DEUX côtés (erreur²). Les
# nutriments de COUVERTURE (fibres + tous les micros) ne sont pénalisés que sur
# le MANQUE, élevé à une puissance haute : le coût marginal de secourir un
# nutriment proche de 0 % écrase celui de peaufiner un nutriment déjà correct,
# donc l'optimiseur cesse de sacrifier un micro pour économiser ailleurs.
CORE_MACRO_COLS: set[str] = {"Energie", "Proteines", "Lipides", "Glucides"}
COVERAGE_WEIGHT = 60.0   # A/B 2026-06-15 : meilleur compromis couverture/budget
COVERAGE_POWER = 4
# Terme linéaire jusqu'à 100 % : contrairement à shortfall^4, sa pente ne
# disparaît pas à 95-99 %. Il pousse donc à TERMINER une cible plutôt qu'à
# s'arrêter juste dessous pour économiser quelques cents.
COVERAGE_COMPLETION_WEIGHT = 10.0
USE_COVERAGE = True

# Nutriments "max" — clés CSV
_MAX_CSV_COLS: set[str] = {NUTRIENT_KEY_TO_CSV[k] for k in TRACKED_MAX_NUTRIENTS}

MAX_DAILY_UNITS = 12.0  # 1 unité = 100g → 1,2 kg/jour, multiplié par la fenêtre
SUPPLEMENT_MAX = 0.05   # 5g max pour suppléments / vitamines
MIN_FOOD_GRAMS = 1.0    # en dessous : résidu numérique, pas un achat réel

# ── Malus de diversité (#bug rapporté : « 5g de courgette » recommandé — un
# aliment inclus pour un gain de couverture marginal minuscule, que le
# snap MinQty (post-traitement) remonte ensuite à une quantité "réelle" mais
# dérisoire). COVERAGE_POWER=4 rend déjà le MANQUE marginal petit une fois un
# nutriment bien couvert, mais laisse SLSQP s'arrêter (ftol) sur un x résiduel
# proche de 0 plutôt que pile 0 — le snap-up (x >= MinQty/2) en fait alors un
# "aliment" visible. Un coût fixe par aliment ACTIF (même minime) pousse
# franchement ces x résiduels vers 0 : chaque aliment inclus doit justifier
# son coût, pas seulement le dernier gramme de couverture.
DIVERSITY_EPS = 0.02     # 2g : quantité à partir de laquelle un aliment "compte" pleinement
DIVERSITY_WEIGHT = 0.08  # léger coût fixe; les formats entiers départagent ensuite


def _build_cost_functions(
    prix_arr: np.ndarray,
    *,
    package_price_arr: np.ndarray | None = None,
    package_units_arr: np.ndarray | None = None,
    pantry_tiers: list[list[tuple[float, float]]] | None = None,
):
    """Return smooth economic and cash costs for quantities in 100 g units.

    Existing stock is valued at its configured replacement-cost factor, but
    only up to the quantity actually available. Any excess uses the ordinary
    purchase cost; package activation applies only to that excess.
    """
    prices = np.asarray(prix_arr, dtype=float)
    package_aware = package_price_arr is not None and package_units_arr is not None
    package_prices = np.asarray(package_price_arr, dtype=float) if package_aware else None
    package_units = np.asarray(package_units_arr, dtype=float) if package_aware else None
    tiers = pantry_tiers or [[] for _ in range(len(prices))]
    if len(tiers) != len(prices):
        raise ValueError("Le profil de stock doit suivre l'ordre des aliments du catalogue.")
    stock_units = np.array([sum(units for units, _factor in row) for row in tiers])
    def cash_purchase_cost(x: np.ndarray) -> float:
        deficit = np.maximum(np.asarray(x, dtype=float) - stock_units, 0.0)
        if not package_aware:
            return float(np.dot(deficit, prices))
        valid = (package_prices > 0.0) & (package_units > 0.0)
        cost = float(np.dot(deficit[~valid], prices[~valid]))
        if np.any(valid):
            ratio = deficit[valid] / package_units[valid]
            activation = 1.0 - np.exp(-deficit[valid] / 0.05)
            smooth_packages = ratio + activation * np.clip(1.0 - ratio, 0.0, 1.0)
            cost += float(np.dot(package_prices[valid], smooth_packages))
        return cost

    def economic_cost(x: np.ndarray) -> float:
        quantities = np.maximum(np.asarray(x, dtype=float), 0.0)
        # Coût imputé au plan : le stock est valorisé au prix catalogue réduit,
        # tandis que tout ce qui dépasse le stock reste au plein tarif. Le coût
        # d'emballage payé en caisse est calculé séparément par cash_purchase_cost.
        cost = float(np.dot(quantities, prices))
        for index, lots in enumerate(tiers):
            remaining = quantities[index]
            for units, factor in lots:
                used = min(remaining, units)
                cost -= used * prices[index] * (1.0 - factor)
                remaining -= used
                if remaining <= 1e-12:
                    break
        return float(cost)

    return economic_cost, cash_purchase_cost


def build_objective(
    *,
    nutrient_targets: list[tuple[str, float, float]],
    nutrient_arrays: dict[str, np.ndarray],
    mult_by_col: dict[str, float],
    body_weight: float,
    price_weight: float,
    prix_arr: np.ndarray,
    taste_arr: np.ndarray,
    pantry_tiers: list[list[tuple[float, float]]] | None = None,
    cost_function=None,
    package_price_arr: np.ndarray | None = None,
    package_units_arr: np.ndarray | None = None,
):
    """Construit la fonction objectif SLSQP, vectorisée sur les nutriments.

    SLSQP dérive par différences finies : l'objectif est évalué ~(n_aliments+1)
    fois PAR itération, soit des dizaines de milliers d'appels par plan. Une
    boucle Python par nutriment (~30 `np.dot` de 110 éléments chacun) y coûtait
    ~60 s par fenêtre — au-delà du timeout client. Ici les nutriments sont
    empilés en une matrice et évalués en un seul produit matriciel + des
    opérations par masque. La formule est identique terme à terme (cf.
    `tests/test_sante/test_optimizer_objective.py`).
    """
    # Partition des nutriments selon les branches de la formule (fixe → hors boucle).
    zero_rows, max_rows, macro_rows, cov_rows = [], [], [], []
    for csv_col, target_val, weight in nutrient_targets:
        row = (nutrient_arrays[csv_col], max(0.0, target_val), weight, csv_col)
        if max(0.0, target_val) == 0.0:
            zero_rows.append(row)
        elif csv_col in _MAX_CSV_COLS:
            max_rows.append(row)
        elif csv_col in CORE_MACRO_COLS or not USE_COVERAGE:
            macro_rows.append(row)
        else:
            cov_rows.append(row)

    def _stack(rows):
        if not rows:
            empty = np.zeros((0, len(prix_arr)))
            return empty, np.zeros(0), np.zeros(0)
        return (
            np.vstack([r[0] for r in rows]),
            np.array([r[1] for r in rows], dtype=float),
            np.array([r[2] for r in rows], dtype=float),
        )

    zero_a, _zero_t, zero_w = _stack(zero_rows)
    max_a, max_t, max_w = _stack(max_rows)
    macro_a, macro_t, macro_w = _stack(macro_rows)
    cov_a, cov_t, _cov_w = _stack(cov_rows)
    # Poids de couverture : COVERAGE_WEIGHT × multiplicateur de dette éventuel.
    cov_weights = np.array(
        [COVERAGE_WEIGHT * mult_by_col.get(r[3], 1.0) for r in cov_rows], dtype=float
    )
    completion_weights = np.array(
        [
            COVERAGE_COMPLETION_WEIGHT * mult_by_col.get(r[3], 1.0)
            for r in cov_rows
        ],
        dtype=float,
    )

    threshold_grams = body_weight * 0.05 * 1000.0

    if cost_function is None:
        cost_function, _cash_cost = _build_cost_functions(
            prix_arr, package_price_arr=package_price_arr,
            package_units_arr=package_units_arr, pantry_tiers=pantry_tiers,
        )

    def objective(x: np.ndarray) -> float:
        error = 0.0

        # Cible nulle (dette J-1 déjà absorbée) : tout dépassement est pénalisé.
        if zero_a.shape[0]:
            current = zero_a @ x
            error += float(np.sum(zero_w * np.where(current > 0.0, current ** 2, 0.0)))

        # Nutriments « max » : pénalité au-dessus de la cible seulement.
        if max_a.shape[0]:
            current = max_a @ x
            rel = (current - max_t) / max_t
            error += float(np.sum(max_w * 5.0 * np.where(current > max_t, rel ** 2, 0.0)))

        # Macros : visées des deux côtés (erreur relative au carré).
        if macro_a.shape[0]:
            rel = (macro_a @ x - macro_t) / macro_t
            error += float(np.sum(
                macro_w * (rel ** 2 + MACRO_TAIL_MULTIPLIER * rel ** 4)
            ))

        # Micros à couvrir : distance symétrique à 100 %. Un apport à 80 % et
        # un apport à 125 % ont la même distance multiplicative à la cible.
        # Contrairement à l'ancienne formule, l'excès est pénalisé dès 100 %,
        # pas seulement au-delà de 200 %.
        if cov_a.shape[0]:
            rel = (cov_a @ x - cov_t) / cov_t
            distance = np.abs(rel)
            error += float(np.sum(cov_weights * distance ** 2))
            error += float(np.sum(completion_weights * distance))

        # Pénalité poids total > 5 % du poids corporel
        total_grams = float(np.sum(x)) * 100.0
        if total_grams > threshold_grams and threshold_grams > 0:
            excess_ratio = (total_grams - threshold_grams) / threshold_grams
            error += 5000.0 * (excess_ratio ** 2)

        # Pénalité prix pilotée par price_weight (balayage du ratio, cf. ratio_optimizer)
        error += price_weight * cost_function(x)
        # Malus de diversité : chaque aliment actif a un coût fixe (cf. constante).
        error += DIVERSITY_WEIGHT * diversity_penalty(x, DIVERSITY_EPS)
        # Préférence aléatoire (variété) — nulle si seed=None.
        error += float(np.dot(x, taste_arr))
        return error

    return objective


def diversity_penalty(x: np.ndarray, eps: float = DIVERSITY_EPS) -> float:
    """Approximation lisse du NOMBRE d'aliments actifs (x > 0), différentiable
    pour SLSQP. Chaque aliment contribue x/(x+eps) : ~0 si quasi-nul, ~1 dès
    que la quantité dépasse `eps` de quelques multiples (sature vite). Pur."""
    return float(np.sum(x / (x + eps)))


def _food_group(name: str) -> str | None:
    """Groupes dont la quantité totale doit rester réaliste par jour."""
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", str(name).lower())
        if not unicodedata.combining(char)
    )
    if any(word in normalized for word in ("jus", "nectar", "smoothie")):
        return "jus_fruits"
    if "kefir" in normalized:
        return "kefir"
    if "tomate" in normalized and any(
        marker in normalized for marker in ("sechee", "sechees")
    ):
        return "tomates_sechees"
    return None


GROUP_MAX_GRAMS_PER_DAY: dict[str, float] = {
    "jus_fruits": 250.0,
    "kefir": 400.0,
    "tomates_sechees": 30.0,
}


def optimize_nutrition(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
    seed: Optional[int] = None,
    price_weight: float = 0.001,
    micro_weight_mult: Optional[dict[str, float]] = None,
    pantry_stock: Optional[dict[str, list[dict[str, float]]]] = None,
    quantity_days: int = 1,
    initial_seed: Optional[int] = None,
    initial_quantities: Optional[dict[str, float]] = None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Optimise le plan alimentaire pour atteindre les cibles données.

    Args:
        df: DataFrame issu de `aliments.load_aliments_dataframe`. Index = nom.
        targets: dict de cibles avec au moins Calories, Protéines, Lipides,
                 Glucides, Poids_Corps + les micronutriments.
        budget_max_daily: budget CAD/jour. Si None, prend `targets["Prix_Max"]`
                          ou DEFAULT_PRIX_MAX_DAILY.
        seed: si fourni, perturbe le point de départ SLSQP (jitter aléatoire
              reproductible) pour obtenir un plan DIFFÉRENT à chaque « Re-générer »
              sans changer les contraintes ni l'objectif. None = déterministe.
        price_weight: coefficient de la pénalité prix (défaut 0.001).
        micro_weight_mult: dict optionnel mappant une clé métier micro (ex. "VitD")
                          à un facteur multipliant sa pénalité de couverture.
        pantry_stock: lots de stock réellement disponibles par aliment, avec leur
                      facteur de coût (0 périssable, 0,5 durable).

    Returns:
        (plan, warning) :
            plan = liste de dicts {Aliment, Quantité, Calories, Protéines, ...}
                   ou None si l'optimisation échoue avec contraintes dures
            warning = message d'avertissement (peut être vide)
    """
    if df.empty:
        return None, "Catalogue aliments vide — impossible d'optimiser."

    if budget_max_daily is None:
        budget_max_daily = float(targets.get("Prix_Max", DEFAULT_PRIX_MAX_DAILY))

    food_names = df.index.tolist()
    num_foods = len(food_names)
    body_weight = float(targets.get("Poids_Corps", 70.0))

    # Liste des (col_csv, target_value, weight) pour l'objective
    nutrient_targets: list[tuple[str, float, float]] = []
    for key, csv_col in _OPT_NUTRIENT_MAP:
        if key not in targets:
            continue
        val = float(targets[key])
        w = _WEIGHTS.get(csv_col, MICRO_WEIGHT)
        nutrient_targets.append((csv_col, val, w))

    # Construire le multiplicateur par colonne CSV pour les micronutriments prioritaires
    mult_by_col: dict[str, float] = {}
    for key, factor in (micro_weight_mult or {}).items():
        col = NUTRIENT_KEY_TO_CSV.get(key)
        if col is not None:
            mult_by_col[col] = float(factor)

    # Pré-calcul des arrays (perf : on évite df[col].values dans la closure)
    nutrient_arrays: dict[str, np.ndarray] = {
        col: df[col].values for col, _, _ in nutrient_targets
    }
    prix_arr = df["Prix"].values
    cal_arr = df["Energie"].values
    prot_arr = df["Proteines"].values
    package_price_arr = None
    package_units_arr = None
    if {"PackagePrice", "PackageWeightG"}.issubset(df.columns):
        package_price_arr = df["PackagePrice"].fillna(0.0).to_numpy(dtype=float)
        # x est exprimé en unités de 100 g.
        package_units_arr = (
            df["PackageWeightG"].fillna(0.0).to_numpy(dtype=float) / 100.0
        )

    # Vecteur de « préférence » aléatoire (variété du Re-générer) : un petit coût
    # linéaire par aliment, seedé. Assez grand pour départager différemment les
    # aliments nutritionnellement ≈ équivalents, assez petit pour ne pas dégrader
    # l'atteinte des cibles. seed=None -> vecteur nul -> résultat déterministe.
    taste_arr = np.zeros(num_foods)
    if seed is not None:
        taste_arr = np.random.default_rng(seed).uniform(0.0, 0.5, num_foods)

    pantry_tiers = [
        normalize_stock_lots((pantry_stock or {}).get(name))
        for name in food_names
    ]
    economic_cost, cash_purchase_cost = _build_cost_functions(
        prix_arr, package_price_arr=package_price_arr,
        package_units_arr=package_units_arr, pantry_tiers=pantry_tiers,
    )

    objective = build_objective(
        nutrient_targets=nutrient_targets, nutrient_arrays=nutrient_arrays,
        # La pénalité de poids (5 % du poids corporel) est elle aussi
        # quotidienne. Une fenêtre de 3/4 jours doit disposer de 3/4 fois ce
        # volume, sinon le solveur combat ses propres cibles cumulées.
        mult_by_col=mult_by_col,
        body_weight=body_weight * max(1, int(quantity_days)),
        price_weight=price_weight,
        prix_arr=prix_arr, taste_arr=taste_arr, pantry_tiers=pantry_tiers,
        cost_function=economic_cost,
        package_price_arr=package_price_arr,
        package_units_arr=package_units_arr,
    )

    # Contraintes dures : budget, calories min, protéines min
    constraints = [
        {"type": "ineq", "fun": lambda x: budget_max_daily - cash_purchase_cost(x)},
        {"type": "ineq", "fun": lambda x: float(np.dot(x, cal_arr)) - float(targets["Calories"])},
        {"type": "ineq", "fun": lambda x: float(np.dot(x, prot_arr)) - float(targets["Protéines"])},
    ]
    # Les plafonds individuels restent très larges, comme demandé, mais ils ne
    # doivent pas permettre de cumuler cinq marques de jus ou plusieurs litres
    # de kéfir pour contourner un plafond par aliment.
    for group, max_g_daily in GROUP_MAX_GRAMS_PER_DAY.items():
        mask = np.array([1.0 if _food_group(name) == group else 0.0 for name in food_names])
        if np.any(mask):
            max_units = max_g_daily * max(1, int(quantity_days)) / 100.0
            constraints.append({
                "type": "ineq",
                "fun": lambda x, m=mask, cap=max_units: cap - float(np.dot(x, m)),
            })

    # Bounds : (0, MaxQty). MinQty est traité comme une "quantité d'achat
    # minimale" (semi-continuous) : soit l'aliment n'est pas dans le plan
    # (x=0), soit il y est avec au moins MinQty. Le post-traitement après
    # SLSQP "snappe" les valeurs intermédiaires (0 < x < MinQty) soit à 0,
    # soit à MinQty (selon la plus proche).
    #
    # Convention pour la valeur CSV : si >= 1.0, elle est en grammes (divisée
    # par 100 pour obtenir l'unité interne) ; sinon elle est déjà en unités
    # (1 = 100 g).
    def _csv_qty_to_units(v: float) -> float:
        v = float(v or 0)
        if v <= 0:
            return 0.0
        return v / 100.0 if v >= 1.0 else v

    bounds: list[tuple[float, float]] = []
    minqtys: list[float] = []
    for name in food_names:
        row = df.loc[name]

        # Les cibles d'une fenêtre sont la somme de plusieurs jours : les
        # plafonds CSV sont eux aussi des plafonds PAR JOUR, pas par fenêtre.
        max_val = MAX_DAILY_UNITS * max(1, int(quantity_days))
        max_qty_csv = _csv_qty_to_units(row.get("MaxQty", 0))
        if max_qty_csv > 0:
            max_val = min(max_val, max_qty_csv * max(1, int(quantity_days)))
        elif "Supplement" in name or "Vitamine" in name:
            max_val = SUPPLEMENT_MAX

        bounds.append((0.0, max_val))
        # MinQty = seuil d'achat ; si > max_val, on l'aligne (pas de seuil
        # plus grand que la borne max possible).
        m = _csv_qty_to_units(row.get("MinQty", 0))
        if m > max_val:
            m = max_val
        minqtys.append(m)

    # Initial guess (clampé dans les bounds pour ne pas démarrer infaisable)
    x0 = np.zeros(num_foods)
    window_scale = max(1, int(quantity_days))
    for i, name in enumerate(food_names):
        if initial_quantities is not None:
            x0[i] = max(0.0, float(initial_quantities.get(name, 0.0))) / 100.0
        elif any(s in name for s in STAPLE_KEYWORDS):
            x0[i] = 1.0 * window_scale
        else:
            x0[i] = 0.05 * window_scale
        lo, hi = bounds[i]
        x0[i] = max(lo, min(x0[i], hi))

    # Variété (« Re-générer ») : un jitter aléatoire du point de départ amène
    # SLSQP vers un autre optimum local ≈ équivalent -> un plan différent (autres
    # aliments) mais tout aussi valide. Contraintes et objectif inchangés.
    start_seed = initial_seed if initial_seed is not None else seed
    if start_seed is not None and initial_quantities is None:
        rng = np.random.default_rng(start_seed)
        for i in range(num_foods):
            lo, hi = bounds[i]
            # Jitter MULTIPLICATIF uniquement. Un ancien terme additif (+0,2 unité
            # = +20 g) injectait du poids dans CHAQUE aliment : sur un grand
            # catalogue, des dizaines démarraient juste sous MinQty et le snap les
            # remontait à MinQty -> plans sur-approvisionnés (60+ aliments à 30 g).
            x0[i] = max(lo, min(x0[i] * rng.uniform(0.3, 1.7), hi))

    res = minimize(
        objective, x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-8, "maxiter": 1000},
    )

    # Fallback : si SLSQP échoue, on relâche les MINIMUMS (calories, protéines)
    # mais on GARDE le budget — un plan best-effort ne doit jamais exploser le
    # budget (l'ancien fallback relâchait tout -> plans à 46 CAD pour 18 de budget).
    fallback_warning: Optional[str] = None
    if not res.success:
        res_soft = minimize(
            objective, x0,
            method="SLSQP",
            bounds=bounds,
            # Budget + garde-fous de catégories; calories/protéines seulement
            # deviennent souples lors du fallback.
            constraints=[constraints[0], *constraints[3:]],
            options={"ftol": 1e-8, "maxiter": 1000},
        )
        if res_soft.success:
            res = res_soft
            fallback_warning = (
                "Contraintes dures non satisfaisables — plan en best-effort. "
                "Ajuste tes cibles ou ton budget pour un résultat strict."
            )
        else:
            return None, (
                f"Erreur d'optimisation : {res.message}. Essaie d'élargir le budget "
                f"ou de baisser les cibles macro."
            )

    # ── Post-traitement : sémantique d'achat minimum ────────────────────────
    # MinQty = quantité d'achat minimale, pas obligatoire. Si la solution
    # continue donne 0 < x < MinQty pour un aliment, on doit choisir entre :
    #   - x = 0 (ne pas inclure l'aliment du tout — "pas la peine d'acheter
    #     un paquet pour si peu")
    #   - x = MinQty (l'inclure à la quantité d'achat minimale)
    # Heuristique simple : si la solution continue est plus proche de 0 que
    # de MinQty (i.e. x < MinQty/2), on snappe à 0 ; sinon à MinQty.
    snapped: list[str] = []
    for i, m in enumerate(minqtys):
        if m <= 0:
            continue
        xi = float(res.x[i])
        if xi <= 1e-9:
            continue  # déjà à 0
        if xi >= m:
            continue  # déjà au-dessus du seuil
        # 0 < xi < m → snap
        if xi < m / 2.0:
            res.x[i] = 0.0
            snapped.append(f"{food_names[i]}→0")
        else:
            res.x[i] = m
            snapped.append(f"{food_names[i]}→{m * 100:.0f}g")

    # Warnings post-hoc
    final_price = cash_purchase_cost(res.x)
    final_proteins = float(np.dot(res.x, prot_arr))
    final_calories = float(np.dot(res.x, cal_arr))
    warnings: list[str] = []
    if final_price > budget_max_daily * 1.01:
        warnings.append(f"Budget dépassé de {(final_price - budget_max_daily):.2f} CAD")
    if final_proteins < float(targets["Protéines"]) * 0.98:
        warnings.append(f"Protéines à {final_proteins:.0f}g/{float(targets['Protéines']):.0f}g")
    if final_calories < float(targets["Calories"]) * 0.98:
        warnings.append(f"Calories à {final_calories:.0f}kcal/{float(targets['Calories']):.0f}kcal")
    warning_msg = ("Note : Budget trop serré. " + " | ".join(warnings)) if warnings else ""
    if fallback_warning:
        # Concatène le warning de fallback en premier (plus important pour l'utilisateur)
        warning_msg = fallback_warning + (" | " + warning_msg if warning_msg else "")

    plan: list[dict[str, Any]] = []
    for i, x in enumerate(res.x):
        # Garde tous les items dont la quantité dépasse leur MinQty (ou ~0 si pas
        # de MinQty). Évite de masquer un supplément à très petite dose dont le
        # MinQty est légitime.
        lo = bounds[i][0]
        is_supplement = "Supplement" in food_names[i] or "Vitamine" in food_names[i]
        visible_threshold = 1e-9 if is_supplement else MIN_FOOD_GRAMS / 100.0
        keep_threshold = max(lo - 1e-9, visible_threshold if lo == 0 else 0.0)
        if x < keep_threshold:
            continue
        name = food_names[i]
        name = food_names[i]
        row = df.loc[name]
        qty_val = float(x) * 100.0
        qty_str = f"{qty_val:.0f}g" if qty_val >= 1.0 else f"{qty_val:.2f}g"
        plan.append({
            "Aliment": name,
            "Quantité": qty_str,
            "Quantite_g": qty_val,
            "Calories": float(row["Energie"]) * float(x),
            "Protéines": float(row["Proteines"]) * float(x),
            "Lipides": float(row["Lipides"]) * float(x),
            "Glucides": float(row["Glucides"]) * float(x),
            "Prix": float(row["Prix"]) * float(x),
        })

    return plan, warning_msg
