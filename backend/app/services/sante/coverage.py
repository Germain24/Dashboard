"""Score d'équilibre nutritionnel = numérateur du ratio (spec §2).

Pour chaque cible à atteindre, 100 % est l'optimum. Le score individuel est
``min(apport/cible, cible/apport)`` : 80 % et 125 % valent donc tous deux 80 %.
Un excès ne peut jamais compenser un manque et reçoit désormais son propre
malus. Les nutriments de sécurité (sodium, sucres...) ne sont pas dans cette
liste : ils restent des plafonds dans l'optimiseur.
"""
from __future__ import annotations

import math

MICRO_KEYS: list[str] = [
    "Fibres", "Magnésium", "Omega3",
    "VitA", "VitB1", "VitB2", "VitB3", "VitB5", "VitB6", "VitB9", "VitB12",
    "VitC", "VitD", "VitE", "VitK",
    "Calcium", "Fer", "Zinc", "Potassium", "Iode", "Sélénium", "Phosphore",
]
MACRO_KEYS: list[str] = ["Calories", "Protéines", "Lipides", "Glucides"]


def _balance(got: float, target: float) -> float:
    """Proximité multiplicativement symétrique de la cible, entre 0 et 1."""
    if got <= 0.0 or target <= 0.0:
        return 0.0
    ratio = got / target
    return min(ratio, 1.0 / ratio)


def coverage_score(totals: dict[str, float], targets: dict[str, float]) -> dict:
    """Équilibre moyen des micros/macros et liste des micros sous-couverts."""
    covs: list[tuple[str, float]] = []
    for k in MICRO_KEYS:
        tgt = targets.get(k)
        if not tgt or float(tgt) <= 0:
            continue
        got = float(totals.get(k, 0.0) or 0.0)
        cov = _balance(got, float(tgt))
        covs.append((k, cov))
    macro_balances = [
        _balance(float(totals.get(k, 0.0) or 0.0), float(targets[k]))
        for k in MACRO_KEYS if float(targets.get(k, 0.0) or 0.0) > 0.0
    ]
    n = len(covs)
    if n == 0:
        return {"coverage_mean": 0.0, "pct_micros_atteints": 0.0,
                "macro_balance_mean": 0.0, "nutrition_balance_mean": 0.0,
                "n_micros": 0, "sous_couverts": []}
    coverage_mean = sum(c for _, c in covs) / n
    # Agrégation quadratique et exponentielle : un gros écart ne se dilue plus
    # dans trois macros parfaites. `exp(-RMS(log(apport/cible)))` conserve la
    # symétrie multiplicative (80 % == 125 %) et vaut exactement 1 à la cible.
    macro_log_errors = []
    for k in MACRO_KEYS:
        target = float(targets.get(k, 0.0) or 0.0)
        got = float(totals.get(k, 0.0) or 0.0)
        if target <= 0.0:
            continue
        if got <= 0.0:
            macro_log_errors = [float("inf")]
            break
        macro_log_errors.append(math.log(got / target))
    macro_mean = (
        math.exp(-math.sqrt(sum(e * e for e in macro_log_errors) / len(macro_log_errors)))
        if macro_log_errors else 0.0
    )
    # Micros et macros pèsent chacun 50 % : les 22 micros ne doivent pas diluer
    # complètement un gros écart de glucides ou de lipides.
    nutrition_mean = (
        (coverage_mean + macro_mean) / 2.0 if macro_balances else coverage_mean
    )
    sous = [
        k for k in MICRO_KEYS
        if float(targets.get(k, 0.0) or 0.0) > 0.0
        and float(totals.get(k, 0.0) or 0.0) < float(targets[k])
    ]
    sous.sort(key=lambda k: float(totals.get(k, 0.0) or 0.0) / float(targets[k]))
    return {
        "coverage_mean": coverage_mean,
        # Nom conservé dans l'API pour compatibilité; sa sémantique est désormais
        # la moyenne demandée, et non le compte des cibles exactement franchies.
        "pct_micros_atteints": coverage_mean * 100.0,
        "macro_balance_mean": macro_mean,
        "nutrition_balance_mean": nutrition_mean,
        "n_micros": n,
        "sous_couverts": sous,
    }
