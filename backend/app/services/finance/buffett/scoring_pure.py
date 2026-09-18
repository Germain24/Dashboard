"""Scoring MOAT pur Python — zéro dépendance pandas/scipy.

Toutes les fonctions acceptent des list[dict] (une entrée par année)
et retournent des scalaires. Testable sans DB en < 1 s.
"""

from __future__ import annotations

import math
from typing import Optional

# À incrémenter dès qu'une formule change. Les ETF restent N/A, tandis que les
# actions sont recalculées avec le nouveau modèle.
SCORING_MODEL_VERSION = 5


# ── Thresholds (issues de WarrenBuffetMensuel.py) ──────────────────────────
THRESHOLD_GPM = 0.60       # Gross Profit Margin idéale ≥ 60 %
THRESHOLD_SGA = 0.80       # SGA/Gross Profit idéale ≤ 80 %
THRESHOLD_RD = 0.30        # R&D/Gross Profit idéale ≤ 30 %
THRESHOLD_DEPR = 0.15      # Depreciation/Gross Profit idéale ≤ 15 %
THRESHOLD_INT = 0.15       # Interest/Operating Income idéale ≤ 15 %
THRESHOLD_NIM = 0.20       # Net Income Margin idéale ≥ 20 %
THRESHOLD_ROE = 0.20       # ROE idéale ≥ 20 %
THRESHOLD_ROIC = 0.10      # ROIC idéale ≥ 10 %
THRESHOLD_CAPEX = 0.25     # CapEx/Net Income idéale ≤ 25 %
THRESHOLD_DEBT_EQ = 0.80   # Debt/Equity idéale ≤ 80 %

# PEG : la croissance utilisée au dénominateur est bornée à ce plafond, sinon une
# croissance aberrante (base de départ minuscule -> CAGR explosif) écrase le PEG
# vers ~0 et valide à tort l'achat. 0.25 = 25 %/an, déjà très élevé pour un titre
# de qualité durable.
PEG_GROWTH_CAP = 0.25
# Au-delà de ce seuil, une croissance est jugée NON fiable (rebond de base, bruit).
GROWTH_EXTREME = 0.50
# Décote appliquée à la seule croissance PRÉVUE (consensus analystes), connue pour
# son biais optimiste. Défaut neutre ici ; la valeur réelle vient de Config.
#
# ATTENTION : il ne doit JAMAIS exister de PLANCHER de croissance. Une société en
# déclin sort aujourd'hui du filtre via `PEG = None`. Lui imposer un plancher
# (ex. g >= 5 %) lui fabriquerait un PEG flatteur et la rendrait éligible —
# exactement l'inverse de l'effet recherché.
GROWTH_FORWARD_HAIRCUT = 1.0


def exponential_weights(n: int) -> list[float]:
    """Poids exponentiels croissants pour une série ancien → récent."""
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    raw = [math.exp(0.1 * i) for i in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


_CRITERIA: dict[str, tuple[str, float | None]] = {
    "gpm": ("min", THRESHOLD_GPM),
    "sga": ("max", THRESHOLD_SGA),
    "rd": ("max", THRESHOLD_RD),
    "depr": ("max", THRESHOLD_DEPR),
    "interest_exp": ("max", THRESHOLD_INT),
    "pretax_growth": ("bool", None),
    "net_income_growth": ("bool", None),
    "net_income_positive": ("bool", None),
    "nim": ("min", THRESHOLD_NIM),
    "eps_growth": ("bool", None),
    "cash_growth": ("bool", None),
    "debt_ratio": ("max", 0.60),
    "liab_ratio": ("min", 1.0),
    "lt_debt_ratio": ("max", 0.25),
    "debt_eq": ("max", THRESHOLD_DEBT_EQ),
    "retained_growth": ("bool", None),
    "cap_stock_var": ("bool", None),
    "roe": ("min", THRESHOLD_ROE),
    "roic": ("min", THRESHOLD_ROIC),
    "capex": ("max", THRESHOLD_CAPEX),
    "buybacks": ("bool", None),
}

# Certains ratios industriels n'ont pas la même signification pour les sociétés
# financières, les REIT et les utilities. On retire uniquement les critères non
# comparables ; les critères restants gardent les mêmes seuils stricts.
_SECTOR_EXCLUDED: dict[str, set[str]] = {
    "financial services": {
        "gpm", "sga", "rd", "depr", "interest_exp", "debt_ratio",
        "liab_ratio", "lt_debt_ratio", "debt_eq", "roic", "capex",
    },
    "utilities": {"rd", "capex"},
}
_REIT_EXCLUDED = {
    "depr", "nim", "net_income_growth", "eps_growth", "roe", "roic", "capex",
    "lt_debt_ratio",
}
_GROWTH_KEYS = {
    "pretax_growth", "net_income_growth", "eps_growth", "cash_growth",
    "retained_growth",
}


def _applicable_criteria(secteur: str = "", industrie: str = "") -> set[str]:
    keys = set(_CRITERIA)
    keys -= _SECTOR_EXCLUDED.get(str(secteur or "").strip().lower(), set())
    if "reit" in str(industrie or "").lower():
        keys -= _REIT_EXCLUDED
    return keys


def _criterion_subscore(value: object, direction: str, threshold: float | None) -> float | None:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val):
        return None
    if direction == "bool":
        return 1.0 if bool(value) else 0.0
    if threshold is None or threshold <= 0:
        return None
    if direction == "min":
        return max(0.0, min(1.0, val / threshold))
    # Critère « max » : score plein jusqu'au seuil, puis décroissance linéaire
    # jusqu'à zéro à 2 × le seuil. Le seuil annoncé correspond ainsi réellement
    # à la frontière du score maximal.
    if val <= threshold:
        return 1.0 if val >= 0 else None
    return max(0.0, 2.0 - val / threshold)


def _score_year_components(
    ratios: dict,
    secteur: str = "",
    industrie: str = "",
) -> tuple[float, float]:
    applicable = _applicable_criteria(secteur, industrie)
    scores: list[float] = []
    first = bool(ratios.get("first_year", False))
    for key in applicable:
        if first and key in _GROWTH_KEYS:
            scores.append(1.0)
            continue
        direction, threshold = _CRITERIA[key]
        subscore = _criterion_subscore(ratios.get(key), direction, threshold)
        if subscore is not None:
            scores.append(subscore)
    if not scores or not applicable:
        return 0.0, 0.0
    coverage = len(scores) / len(applicable)
    # Une donnée absente n'est plus confondue avec un mauvais ratio, mais reste
    # pénalisée : impossible d'obtenir un excellent score sur quelques champs.
    confidence = math.sqrt(coverage)
    return sum(scores) / len(scores) * confidence, coverage


def score_year(ratios: dict, secteur: str = "", industrie: str = "") -> float:
    """Score MOAT pour une année donnée (0-1).

    ratios: dict avec clés optionnelles :
        gpm, sga, rd, depr, interest_exp,
        pretax_growth, net_income_growth, net_income_positive,
        nim, eps_growth, cash_growth,
        debt_ratio, liab_ratio, lt_debt_ratio, debt_eq,
        retained_growth, cap_stock_var, roe, roic, capex, buybacks,
        first_year (bool — pour les critères de croissance)
    """
    return _score_year_components(ratios, secteur, industrie)[0]


def compute_moat_score(
    yearly_ratios: list[dict], secteur: str = "", industrie: str = "",
) -> float:
    """Score MOAT global pondéré exponentiellement (0-100)."""
    n = len(yearly_ratios)
    if n == 0:
        return 0.0
    weights = exponential_weights(n)
    total = sum(
        score_year({**r, "first_year": i == 0}, secteur, industrie) * weights[i]
        for i, r in enumerate(yearly_ratios)
    )
    return round(total * 100.0, 2)


def compute_score_coverage(
    yearly_ratios: list[dict], secteur: str = "", industrie: str = "",
) -> float:
    """Couverture pondérée des critères applicables, en pourcentage."""
    if not yearly_ratios:
        return 0.0
    weights = exponential_weights(len(yearly_ratios))
    coverage = sum(
        _score_year_components({**r, "first_year": i == 0}, secteur, industrie)[1]
        * weights[i]
        for i, r in enumerate(yearly_ratios)
    )
    return round(coverage * 100.0, 2)


BUFFETT_QUALITY_MODEL_VERSION = 3
RANKING_PRIOR = 0.60


def financial_business_model(
    secteur: str = "",
    industrie: str = "",
    *,
    ticker: str = "",
    company_name: str = "",
) -> str:
    """Route l'entreprise vers le modèle économique qui décrit ses comptes.

    Les modèles ``*_pending`` restent analysés par la formule générique V3 mais
    sont explicitement signalés : leur proxy moat ne doit pas être interprété
    comme un modèle sectoriel déjà calibré.
    """
    symbol = str(ticker or "").strip().upper()
    name = str(company_name or "").strip().casefold()
    # Les exceptions d'entité précèdent les heuristiques Yahoo. Elles évitent
    # notamment qu'un secteur très large ("Financial Services", "Energy") ne
    # route un réseau ou un concédant de licences vers le mauvais modèle.
    entity_routes = {
        "V": "payment_network",
        "MA": "payment_network",
        "GTT.PA": "ip_licensing_engineering",
        "MCO": "credit_ratings_data",
        "AJB.L": "investment_platform_generic_pending",
        "AUTO.L": "marketplace_network",
        "HEMNF": "marketplace_network",
        "SEIC": "financial_platform_hybrid_generic_pending",
        "SOUU.F": "exchange",
        "PRU.TO": "commodity_generic_pending",
    }
    if symbol in entity_routes:
        return entity_routes[symbol]
    # Les cotations secondaires ne portent pas toujours le ticker principal.
    name_routes = (
        (("visa inc",), "payment_network"),
        (("mastercard",), "payment_network"),
        (("gaztransport", "technigaz"), "ip_licensing_engineering"),
        (("moody's", "moodys"), "credit_ratings_data"),
        (("aj bell",), "investment_platform_generic_pending"),
        (("auto trader", "autotrader"), "marketplace_network"),
        (("hemnet",), "marketplace_network"),
        (("sei investments",), "financial_platform_hybrid_generic_pending"),
        (("singapore exchange",), "exchange"),
    )
    for aliases, route in name_routes:
        if any(alias in name for alias in aliases):
            return route

    sector = str(secteur or "").strip().casefold()
    industry = str(industrie or "").strip().casefold()
    commodity_markers = (
        "mining", "miner", "copper", "gold", "silver", "iron ore", "steel",
        "aluminum", "aluminium", "coal", "uranium", "oil & gas", "oil and gas",
        "exploration", "production", "matières premières", "metaux", "métaux",
    )
    if any(marker in industry for marker in commodity_markers):
        return "commodity_generic_pending"
    if not any(marker in sector for marker in ("financial", "finance", "financ")):
        return "standard"
    if "insurance" in industry or "assur" in industry:
        return "insurer_partial"
    if any(marker in industry for marker in ("bank", "banque", "bancaire", "savings")):
        return "bank_partial"
    if any(marker in industry for marker in ("exchange", "financial data", "bourse")):
        return "exchange"
    if "asset management" in industry or "gestion d'actifs" in industry:
        return "asset_manager_generic_pending"
    if any(marker in industry for marker in ("capital markets", "broker", "courtage")):
        return "broker_trading_generic_pending"
    if any(marker in industry for marker in ("credit services", "payment", "paiement")):
        return "payments_lending"
    return "unknown_model"


def _model_metadata(model: str) -> dict[str, object]:
    """Statut analytique, sans transformer automatiquement l'incertitude en note."""
    if model in {"bank_partial", "insurer_partial"}:
        return {
            "model_fit": 0.65,
            "model_status": "partial",
            "model_complete": False,
            "comparison_group": model.removesuffix("_partial").upper(),
            "scoring_template": "PARTIAL_FINANCIAL_V3",
            "comparable_to_standard": False,
            "moat_proxy_version": "PARTIAL_V1",
        }
    if model.endswith("_generic_pending"):
        return {
            "model_fit": 0.85,
            "model_status": "generic_pending",
            "model_complete": False,
            "comparison_group": model.removesuffix("_generic_pending").upper(),
            "scoring_template": "GENERIC_PENDING_V3",
            "comparable_to_standard": True,
            "moat_proxy_version": "GENERIC_PENDING_V1",
        }
    if model == "unknown_model":
        return {
            "model_fit": 0.0,
            "model_status": "unknown",
            "model_complete": False,
            "comparison_group": "UNKNOWN",
            "scoring_template": "NONE",
            "comparable_to_standard": False,
            "moat_proxy_version": "UNKNOWN",
        }
    return {
        "model_fit": 1.0,
        "model_status": "complete",
        "model_complete": True,
        "comparison_group": model.upper(),
        "scoring_template": "STANDARD_V3",
        "comparable_to_standard": True,
        "moat_proxy_version": "STANDARD_V1",
    }


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _graded_up(value: object, low: float, good: float, exceptional: float) -> float | None:
    number = _finite_number(value)
    if number is None:
        return None
    if number <= low:
        return 0.0
    if number < good:
        return 0.8 * (number - low) / (good - low)
    if number < exceptional:
        return 0.8 + 0.2 * (number - good) / (exceptional - good)
    return 1.0


def _graded_down(value: object, bad: float, good: float, exceptional: float) -> float | None:
    number = _finite_number(value)
    if number is None or number < 0:
        return None
    if number <= exceptional:
        return 1.0
    if number <= good:
        return 0.8 + 0.2 * (good - number) / (good - exceptional)
    if number < bad:
        return 0.8 * (bad - number) / (bad - good)
    return 0.0


def _weighted_available(values: list[tuple[float | None, float]]) -> tuple[float | None, float]:
    available = [(value, weight) for value, weight in values if value is not None]
    expected = sum(weight for _, weight in values)
    if not available or expected <= 0:
        return None, 0.0
    denominator = sum(weight for _, weight in available)
    score = sum(float(value) * weight for value, weight in available) / denominator
    return score, denominator / expected


def _combine_covered_metrics(
    values: list[tuple[float | None, float]],
) -> tuple[float | None, float]:
    """Moyenne observée séparée de la couverture temporelle réelle des métriques."""
    if not values:
        return None, 0.0
    observed = [score for score, _ in values if score is not None]
    score = sum(float(value) for value in observed) / len(observed) if observed else None
    coverage = sum(max(0.0, min(float(value), 1.0)) for _, value in values) / len(values)
    return score, coverage


def _combine_covered_families(
    values: list[tuple[float | None, float, float]],
) -> tuple[float | None, float]:
    expected = sum(weight for _, _, weight in values)
    available = [(score, weight) for score, _, weight in values if score is not None]
    if not available or expected <= 0:
        return None, 0.0
    denominator = sum(weight for _, weight in available)
    score = sum(float(value) * weight for value, weight in available) / denominator
    coverage = sum(coverage * weight for _, coverage, weight in values) / expected
    return score, max(0.0, min(coverage, 1.0))


def _yearly_metric(
    yearly: list[dict], key: str, scorer,
) -> tuple[float | None, float]:
    weights = exponential_weights(len(yearly))
    scored: list[tuple[float, float]] = []
    evidence_weight = 0.0
    expected_weight = 0.0
    for index, row in enumerate(yearly):
        state = str((row.get("metric_states") or {}).get(key) or "").upper()
        if state == "NOT_APPLICABLE":
            continue
        weight = weights[index]
        expected_weight += weight
        value = scorer(row.get(key))
        if state in {"VALID", "ECONOMICALLY_INVALID"} or (not state and value is not None):
            evidence_weight += weight
        if value is not None:
            scored.append((float(value), weight))
    if not scored:
        return None, evidence_weight / expected_weight if expected_weight else 0.0
    denominator = sum(weight for _, weight in scored)
    return (
        sum(value * weight for value, weight in scored) / denominator,
        evidence_weight / expected_weight if expected_weight else 0.0,
    )


def _history_depth(observations: int, *, transitions: bool = False) -> float:
    """Profondeur à rendements décroissants, cible huit exercices."""
    usable = observations if transitions else max(observations - 1, 0)
    return math.sqrt(min(max(usable, 0) / 7.0, 1.0))


def _evidence_years(yearly: list[dict], keys: tuple[str, ...]) -> int:
    count = 0
    for row in yearly:
        states = row.get("metric_states") or {}
        if any(
            str(states.get(key) or "").upper() in {"VALID", "ECONOMICALLY_INVALID"}
            or (not states.get(key) and _finite_number(row.get(key)) is not None)
            for key in keys
        ):
            count += 1
    return count


def _positive_fraction(yearly: list[dict], key: str) -> tuple[float | None, float]:
    values = [row.get(key) for row in yearly if row.get(key) is not None]
    if not values:
        return None, 0.0
    return sum(bool(value) for value in values) / len(values), len(values) / len(yearly)


def _drawdown_resilience(values: list[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 3:
        return None
    peak = finite[0]
    worst = 0.0
    for value in finite[1:]:
        scale = max(abs(peak), 0.10)
        worst = max(worst, (peak - value) / scale)
        peak = max(peak, value)
    return max(0.0, min(1.0, 1.0 - worst / 1.5))


def _stability_score(values: list[float]) -> float | None:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 3:
        return None
    mean = sum(finite) / len(finite)
    variance = sum((value - mean) ** 2 for value in finite) / len(finite)
    scale = max(abs(mean), 0.10)
    coefficient = math.sqrt(variance) / scale
    return max(0.0, min(1.0, 1.0 - coefficient / 1.5))


def compute_buffett_score_v3(
    yearly_ratios: list[dict], secteur: str = "", industrie: str = "",
    *, ticker: str = "", company_name: str = "",
) -> dict[str, object]:
    """Score Buffett v3 : qualité, preuve et classement restent séparés.

    La note observée ne baisse jamais parce qu'une source est incomplète. La
    couverture, la profondeur historique (cible huit ans) et l'adéquation du
    sous-modèle déterminent séparément ``confidence_pct``. ``ranking_score`` est
    la variante conservatrice utilisée pour trier les candidats.
    """
    yearly = list(yearly_ratios)
    model = financial_business_model(
        secteur, industrie, ticker=ticker, company_name=company_name
    )
    model_metadata = _model_metadata(model)
    if not yearly:
        return {
            "model_version": BUFFETT_QUALITY_MODEL_VERSION,
            "business_model": model,
            "buffett_quality_score": 0.0,
            "financial_quality_score": 0.0,
            "durability_score": 0.0,
            "financial_moat_proxy_score": 0.0,
            "capital_allocation_score": 0.0,
            "dilution_discipline_score": 0.0,
            "resilience_score": 0.0,
            "confidence_pct": 0.0,
            "ranking_score": 0.0,
            **model_metadata,
            "quality_score_version": "V3.0",
            "durability_version": "V3.0",
            "history_years": 0,
            "family_scores": {},
        }

    partial_financial = model in {"bank_partial", "insurer_partial"}
    families: dict[str, tuple[float | None, float]] = {}

    margin_parts = [
        _yearly_metric(yearly, "nim", lambda value: _graded_up(value, 0.0, 0.12, 0.25)),
    ]
    if not partial_financial:
        margin_parts.extend([
            _yearly_metric(yearly, "gpm", lambda value: _graded_up(value, 0.10, 0.40, 0.65)),
            _yearly_metric(yearly, "sga", lambda value: _graded_down(value, 0.90, 0.50, 0.20)),
        ])
    families["margins_pricing"] = _combine_covered_metrics(margin_parts)

    profitability_parts = [
        _yearly_metric(yearly, "roe", lambda value: _graded_up(value, 0.03, 0.20, 0.35)),
    ]
    if not partial_financial:
        profitability_parts.append(
            _yearly_metric(yearly, "roic", lambda value: _graded_up(value, 0.03, 0.15, 0.25))
        )
    families["profitability"] = _combine_covered_metrics(profitability_parts)

    if not partial_financial:
        balance_parts = [
            _yearly_metric(yearly, "debt_ratio", lambda value: _graded_down(value, 0.70, 0.40, 0.15)),
            _yearly_metric(yearly, "liab_ratio", lambda value: _graded_up(value, 0.70, 1.50, 2.50)),
            # Dette LT remboursable en environ 3-4 ans : le 0,25x historique
            # était la règle CapEx/NI appliquée par erreur à la dette.
            _yearly_metric(yearly, "lt_debt_ratio", lambda value: _graded_down(value, 6.0, 3.5, 1.0)),
            _yearly_metric(yearly, "debt_eq", lambda value: _graded_down(value, 1.60, 0.80, 0.30)),
        ]
        families["balance_sheet"] = _combine_covered_metrics(balance_parts)

        efficiency_parts = [
            _yearly_metric(yearly, "interest_exp", lambda value: _graded_down(value, 0.60, 0.25, 0.10)),
            _yearly_metric(yearly, "capex", lambda value: _graded_down(value, 1.00, 0.50, 0.25)),
        ]
        families["operating_efficiency"] = _combine_covered_metrics(efficiency_parts)

        cash_parts = [
            _yearly_metric(yearly, "fcf_to_net_income", lambda value: _graded_up(value, 0.20, 0.80, 1.20)),
            _yearly_metric(yearly, "fcf_margin", lambda value: _graded_up(value, 0.0, 0.12, 0.25)),
        ]
        families["cash_conversion"] = _combine_covered_metrics(cash_parts)

    share_count = _yearly_metric(
        yearly,
        "share_count_growth",
        lambda value: _graded_down(
            None if value is None else max(float(value) + 0.03, 0.0),
            0.08,
            0.03,
            0.0,
        ),
    )
    families["dilution_discipline"] = share_count

    # Les croissances corrélées sont d'abord fusionnées par année : une bonne
    # année ne peut donc plus apporter cinq points indépendants.
    growth_keys = (
        "pretax_growth_rate", "net_income_growth_rate", "eps_growth_rate",
        "cash_growth_rate", "fcf_per_share_growth_rate",
    )
    growth_years: list[tuple[float | None, float]] = []
    weights = exponential_weights(len(yearly))
    for index, row in enumerate(yearly):
        if index == 0:
            continue
        raw = sorted(
            value for key in growth_keys
            if (value := _finite_number(row.get(key))) is not None
        )
        median = raw[len(raw) // 2] if raw else None
        growth_years.append(
            (_graded_up(median, -0.10, 0.10, 0.25), weights[index])
        )
    growth_score, growth_coverage = _weighted_available(growth_years)
    families["growth"] = (growth_score, growth_coverage)

    stability_values: list[float] = []
    for key in ("roic", "gpm", "nim", "fcf_margin"):
        series = [
            value for row in yearly
            if (value := _finite_number(row.get(key))) is not None
        ]
        stable = _stability_score(series)
        if stable is not None:
            stability_values.append(stable)
    profitable = [
        bool(row.get("net_income_positive"))
        for row in yearly if row.get("net_income_positive") is not None
    ]
    if profitable:
        stability_values.append(sum(profitable) / len(profitable))
    stability_score = (
        sum(stability_values) / len(stability_values) if stability_values else None
    )
    stability_coverage = sum(
        _yearly_metric(yearly, key, lambda value: _finite_number(value))[1]
        for key in ("roic", "gpm", "nim", "fcf_margin")
    ) / 4.0
    families["stability"] = (stability_score, stability_coverage)

    resilience_parts = [
        _positive_fraction(yearly, key)
        for key in (
            "operating_income_positive", "net_income_positive", "fcf_positive",
            "pretax_income_positive", "equity_positive", "invested_capital_positive",
        )
    ]
    for key in ("roic", "fcf_margin"):
        series = [
            value for row in yearly
            if (value := _finite_number(row.get(key))) is not None
        ]
        drawdown = _drawdown_resilience(series)
        resilience_parts.append((drawdown, len(series) / len(yearly)))
    resilience_score, resilience_coverage = _combine_covered_metrics(resilience_parts)
    families["resilience"] = (resilience_score, resilience_coverage)

    durability_score, durability_coverage = _weighted_available([
        (growth_score, 0.45), (stability_score, 0.35), (resilience_score, 0.20),
    ])
    durability_evidence = (
        growth_coverage * 0.45
        + stability_coverage * 0.35
        + resilience_coverage * 0.20
    )
    families["durability"] = (durability_score, durability_coverage * durability_evidence)

    quality_family_weights = {
        "margins_pricing": 0.20,
        "profitability": 0.25,
        "balance_sheet": 0.15,
        "operating_efficiency": 0.10,
        "cash_conversion": 0.20,
    }
    if partial_financial:
        quality_family_weights = {
            "margins_pricing": 0.50,
            "profitability": 0.50,
        }
    financial_quality, quality_coverage = _combine_covered_families([
        (*families.get(name, (None, 0.0)), weight)
        for name, weight in quality_family_weights.items()
    ])
    dilution_discipline = families["dilution_discipline"][0]
    moat_proxy, moat_coverage = _combine_covered_families([
        (*families["margins_pricing"], 0.40),
        (*families["profitability"], 0.40),
        (stability_score, 1.0 if stability_score is not None else 0.0, 0.20),
    ])
    overall_value, _ = _weighted_available([
        (financial_quality, 0.60),
        (durability_score, 0.30),
        (dilution_discipline, 0.10),
    ])
    overall = float(overall_value or 0.0)

    # Confiance par famille = couverture × profondeur propre × adéquation du
    # modèle. Une valeur économiquement invalide est une preuve connue, pas une
    # donnée manquante ; sa pénalité passe par la résilience.
    model_factor = float(model_metadata["model_fit"])
    family_keys = {
        "margins_pricing": ("nim",) if partial_financial else ("nim", "gpm", "sga"),
        "profitability": ("roe",) if partial_financial else ("roe", "roic"),
        "balance_sheet": ("debt_ratio", "liab_ratio", "lt_debt_ratio", "debt_eq"),
        "operating_efficiency": ("interest_exp", "capex"),
        "cash_conversion": ("fcf_to_net_income", "fcf_margin"),
        "dilution_discipline": ("share_count_growth",),
    }
    family_confidences: dict[str, float] = {}
    family_confidences_before_fit: dict[str, float] = {}
    family_depths: dict[str, float] = {}
    family_history: dict[str, int] = {}
    for name, keys in family_keys.items():
        if name not in families:
            continue
        observations = _evidence_years(yearly, keys)
        family_history[name] = observations
        depth = _history_depth(
            observations,
            transitions=name == "dilution_discipline",
        )
        before_fit = max(0.0, min(1.0, families[name][1] * depth))
        family_depths[name] = depth
        family_confidences_before_fit[name] = before_fit
        family_confidences[name] = before_fit * model_factor
    growth_observations = _evidence_years(yearly, growth_keys)
    growth_depth = _history_depth(growth_observations, transitions=True)
    growth_before_fit = growth_coverage * growth_depth
    growth_confidence = growth_before_fit * model_factor
    stability_observations = max(
        (_evidence_years(yearly, (key,)) for key in ("roic", "gpm", "nim", "fcf_margin")),
        default=0,
    )
    stability_depth = _history_depth(stability_observations)
    stability_before_fit = stability_coverage * stability_depth
    stability_confidence = stability_before_fit * model_factor
    resilience_observations = max(
        sum(row.get(key) is not None for row in yearly)
        for key in (
            "operating_income_positive", "net_income_positive", "fcf_positive",
            "pretax_income_positive", "equity_positive", "invested_capital_positive",
        )
    )
    resilience_depth = _history_depth(resilience_observations)
    resilience_before_fit = resilience_coverage * resilience_depth
    resilience_confidence = resilience_before_fit * model_factor
    durability_confidence = (
        growth_confidence * 0.45
        + stability_confidence * 0.35
        + resilience_confidence * 0.20
    )
    family_confidences.update({
        "growth": growth_confidence,
        "stability": stability_confidence,
        "resilience": resilience_confidence,
        "durability": durability_confidence,
    })
    durability_before_fit = (
        growth_before_fit * 0.45
        + stability_before_fit * 0.35
        + resilience_before_fit * 0.20
    )
    family_confidences_before_fit.update({
        "growth": growth_before_fit,
        "stability": stability_before_fit,
        "resilience": resilience_before_fit,
        "durability": durability_before_fit,
    })
    family_depths.update({
        "growth": growth_depth,
        "stability": stability_depth,
        "resilience": resilience_depth,
        "durability": (
            growth_depth * 0.45 + stability_depth * 0.35 + resilience_depth * 0.20
        ),
    })
    family_history.update({
        "growth": growth_observations,
        "stability": stability_observations,
        "resilience": resilience_observations,
        "durability": max(
            growth_observations, stability_observations, resilience_observations
        ),
    })
    quality_confidence = sum(
        family_confidences.get(name, 0.0) * weight
        for name, weight in quality_family_weights.items()
    ) / sum(quality_family_weights.values())
    dilution_confidence = family_confidences.get("dilution_discipline", 0.0)
    confidence = max(0.0, min(
        1.0,
        quality_confidence * 0.60
        + durability_confidence * 0.30
        + dilution_confidence * 0.10,
    ))
    confidence_before_fit = (
        confidence / model_factor if model_factor > 0 else 0.0
    )
    ranking = (
        RANKING_PRIOR + confidence * (overall - RANKING_PRIOR)
        if overall_value is not None else 0.0
    )

    return {
        "model_version": BUFFETT_QUALITY_MODEL_VERSION,
        "business_model": model,
        "buffett_quality_score": round(overall * 100.0, 2),
        "financial_quality_score": round(float(financial_quality or 0.0) * 100.0, 2),
        "durability_score": round(float(durability_score or 0.0) * 100.0, 2),
        "financial_moat_proxy_score": round(float(moat_proxy or 0.0) * 100.0, 2),
        # Alias temporaire pour les anciens consommateurs ; ce n'est pas encore
        # un véritable score d'allocation du capital.
        "capital_allocation_score": round(float(dilution_discipline or 0.0) * 100.0, 2),
        "dilution_discipline_score": round(float(dilution_discipline or 0.0) * 100.0, 2),
        "resilience_score": round(float(resilience_score or 0.0) * 100.0, 2),
        "confidence_pct": round(confidence * 100.0, 2),
        "confidence_before_fit_pct": round(confidence_before_fit * 100.0, 2),
        "confidence_breakdown": {
            "model_fit": model_factor,
            "confidence_before_fit_pct": round(confidence_before_fit * 100.0, 2),
            "confidence_final_pct": round(confidence * 100.0, 2),
        },
        "ranking_score": round(ranking * 100.0, 2),
        "ranking_prior": RANKING_PRIOR * 100.0,
        **model_metadata,
        "quality_score_version": "V3.0",
        "durability_version": "V3.0",
        "history_years": len(yearly),
        "family_scores": {
            name: {
                "score": round(float(score or 0.0) * 100.0, 2),
                "coverage_pct": round(float(coverage) * 100.0, 2),
                "historical_depth_pct": round(
                    float(family_depths.get(name, 0.0)) * 100.0, 2
                ),
                "model_fit": model_factor,
                "confidence_before_fit_pct": round(
                    float(family_confidences_before_fit.get(name, 0.0)) * 100.0, 2
                ),
                "confidence_pct": round(float(family_confidences.get(name, 0.0)) * 100.0, 2),
                "history_years": int(family_history.get(name, 0)),
            }
            for name, (score, coverage) in families.items()
        },
    }


# Compatibilité des imports/tests historiques pendant la migration V2 → V3.
compute_buffett_score_v2 = compute_buffett_score_v3


# Critères lisibles pour le détail du score (clé ratio, label, catégorie, seuil,
# sens "min"=il faut ≥ seuil / "max"=il faut ≤ seuil, explication).
_BREAKDOWN_CRITERIA = [
    ("gpm", "Marge brute", "Marges", THRESHOLD_GPM, "min",
     "Une marge brute élevée signale un avantage concurrentiel durable."),
    ("nim", "Marge nette", "Marges", THRESHOLD_NIM, "min",
     "Part du chiffre d'affaires qui finit en bénéfice net."),
    ("roe", "ROE", "Rentabilité", THRESHOLD_ROE, "min",
     "Rendement des capitaux propres : efficacité du capital des actionnaires."),
    ("roic", "ROIC", "Rentabilité", THRESHOLD_ROIC, "min",
     "Rendement du capital investi, dette incluse."),
    ("debt_eq", "Dette / Capitaux propres", "Dette", THRESHOLD_DEBT_EQ, "max",
     "Endettement relatif : plus c'est bas, plus la société est solide."),
    ("lt_debt_ratio", "Dette long terme / Bénéfice", "Dette", 0.25, "max",
     "Capacité à rembourser la dette long terme avec les bénéfices."),
    ("capex", "CapEx / Bénéfice net", "Investissement", THRESHOLD_CAPEX, "max",
     "Part du bénéfice réinvestie en immobilisations (faible = capital-light)."),
]


def score_breakdown(ratios: dict, secteur: str = "", industrie: str = "") -> list[dict]:
    """Détail par critère du score MOAT pour une année de ratios.

    Retourne une liste de dicts : {cle, label, categorie, valeur, seuil, sens,
    ok, sous_score (0-1), explication}.
    """
    out: list[dict] = []
    applicable = _applicable_criteria(secteur, industrie)
    for cle, label, cat, seuil, sens, expl in _BREAKDOWN_CRITERIA:
        if cle not in applicable:
            continue
        val = ratios.get(cle)
        if val is None or not math.isfinite(val):
            continue
        ok = val >= seuil if sens == "min" else val <= seuil
        sous = _criterion_subscore(val, sens, seuil)
        out.append({
            "cle": cle,
            "label": label,
            "categorie": cat,
            "valeur": round(val, 4),
            "seuil": seuil,
            "sens": sens,
            "ok": bool(ok),
            "sous_score": round(sous, 3),
            "explication": expl,
        })
    return out


def robust_growth(values) -> Optional[float]:
    """Croissance annualisée ROBUSTE d'une série chronologique (ancien → récent).

    Médiane des croissances annuelles (YoY) sur les paires consécutives strictement
    positives. Contrairement au CAGR par extrémités, une seule année de base
    déprimée (ex. ``1 → 90``) ne fait pas exploser le résultat : la médiane ignore
    l'année aberrante. Pour 2 points, la médiane d'un unique YoY = le CAGR.

    ``None`` si non calculable (< 2 points, ou aucune paire consécutive > 0).
    """
    vals = []
    for v in (values or []):
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            vals.append(f)
    if len(vals) < 2:
        return None
    yoy = [
        vals[i + 1] / vals[i] - 1.0
        for i in range(len(vals) - 1)
        if vals[i] > 0 and vals[i + 1] > 0
    ]
    if not yoy:
        return None
    yoy.sort()
    m = len(yoy)
    return yoy[m // 2] if m % 2 else (yoy[m // 2 - 1] + yoy[m // 2]) / 2.0


def select_growth(
    forward: Optional[float],
    growth_rev: Optional[float],
    growth_eps: Optional[float],
    extreme: float = GROWTH_EXTREME,
    forward_haircut: float = GROWTH_FORWARD_HAIRCUT,
) -> tuple[Optional[float], bool]:
    """Choisit la croissance pour le PEG et juge sa fiabilité.

    Priorité à la croissance FUTURE prévue (``forward``) si positive, sinon repli
    sur l'historique en prenant la plus CONSERVATRICE des deux séries (``min`` au
    lieu de ``max`` — neutralise un EPS qui rebondit d'une base minuscule).

    ``forward_haircut`` décote la prévision d'analystes (biais optimiste connu).
    Elle ne s'applique PAS aux séries historiques, déjà conservatrices.

    Retourne ``(growth, reliable)`` :
    - ``reliable=False`` si la croissance retenue dépasse ``extreme`` (rebond/bruit)
      ou si des données existent mais sans croissance positive (déclin) ;
    - une absence TOTALE de donnée est ``(None, True)`` : neutre, on laisse les
      autres filtres décider (pas de rejet pour simple trou de données).
    """
    if forward is not None and forward > 0:
        # La fiabilité se juge sur la valeur BRUTE : décoter d'abord ferait
        # passer un forward de 0,55 (rebond suspect) sous le seuil `extreme`,
        # donc la décote ASSOUPLIRAIT le filtre au lieu de le durcir.
        reliable = forward <= extreme
        return forward * min(max(float(forward_haircut), 0.0), 1.0), reliable
    pos = [g for g in (growth_rev, growth_eps) if g is not None and g > 0]
    if pos:
        g = min(pos)
        return g, (g <= extreme)
    if any(g is not None for g in (growth_rev, growth_eps)):
        return None, False   # données présentes mais croissance ≤ 0 → non fiable
    return None, True        # aucune donnée → neutre


def compute_buy_signal(
    secteur: str,
    pays: str,
    prix: float,
    eps: float,
    per: float,
    growth: Optional[float],
    taux_obligataires: dict,
    taux_defaut: float,
    per_max: float,
    peg_max: float,
    growth_reliable: bool = True,
    peg_growth_cap: float = PEG_GROWTH_CAP,
) -> tuple[bool, Optional[float]]:
    """Calcule le signal d'achat et le PEG (pur Python).

    ``growth`` : croissance annualisée (fraction) déjà sélectionnée (forward →
    historique conservatrice, cf. ``select_growth``). Elle est BORNÉE à
    ``peg_growth_cap`` au dénominateur du PEG (#3). ``growth_reliable`` : si la
    croissance n'est pas fiable, un PEG non calculable (None) ne donne PAS de
    laissez-passer (#4).

    Retourne (achat: bool, peg: Optional[float]).
    """
    if "ETF" in str(secteur).upper():
        return True, None

    taux = taux_obligataires.get(pays, taux_defaut)
    seuil_prix = eps / (0.02 + taux) if eps and eps > 0 else 0.0

    peg: Optional[float] = None
    if growth and growth > 0 and per > 0:
        g = min(growth, peg_growth_cap)   # #3 : bornage anti-PEG-aberrant
        peg = per / (g * 100)

    if peg is not None:
        peg_ok = peg < peg_max
    else:
        # PEG non calculable (croissance absente ou ≤ 0) : laissez-passer seulement
        # si la croissance est jugée fiable (#4).
        peg_ok = bool(growth_reliable)

    achat = (
        pays != "Inconnu"
        and per > 0
        and per < per_max
        and peg_ok
        and prix < seuil_prix
    )
    return achat, peg


def compute_comparable_peg(
    per: float,
    growth: Optional[float],
    *,
    growth_reliable: bool,
    peg_growth_cap: float = PEG_GROWTH_CAP,
) -> Optional[float]:
    """PEG destiné à la comparaison sectorielle.

    Une croissance absente, non positive ou marquée aberrante rend le PEG
    indisponible. Le plafond de 30 % reste uniquement un garde-fou du calcul.
    """
    if not growth_reliable or not growth or growth <= 0 or per <= 0:
        return None
    return per / (min(growth, peg_growth_cap) * 100.0)
