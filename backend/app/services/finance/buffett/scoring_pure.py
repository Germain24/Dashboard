"""Scoring MOAT pur Python — zéro dépendance pandas/scipy.

Toutes les fonctions acceptent des list[dict] (une entrée par année)
et retournent des scalaires. Testable sans DB en < 1 s.
"""

from __future__ import annotations

import math
from typing import Optional


# À incrémenter dès qu'une formule MOAT change. Le cache conserve les ETF à 200,
# mais force alors le recalcul de toutes les actions avec le nouveau modèle.
SCORING_MODEL_VERSION = 2


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
# vers ~0 et valide à tort l'achat. 0.30 = 30 %/an, déjà très élevé pour un titre
# de qualité durable.
PEG_GROWTH_CAP = 0.30
# Au-delà de ce seuil, une croissance est jugée NON fiable (rebond de base, bruit).
GROWTH_EXTREME = 0.50


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
) -> tuple[Optional[float], bool]:
    """Choisit la croissance pour le PEG et juge sa fiabilité.

    Priorité à la croissance FUTURE prévue (``forward``) si positive, sinon repli
    sur l'historique en prenant la plus CONSERVATRICE des deux séries (``min`` au
    lieu de ``max`` — neutralise un EPS qui rebondit d'une base minuscule).

    Retourne ``(growth, reliable)`` :
    - ``reliable=False`` si la croissance retenue dépasse ``extreme`` (rebond/bruit)
      ou si des données existent mais sans croissance positive (déclin) ;
    - une absence TOTALE de donnée est ``(None, True)`` : neutre, on laisse les
      autres filtres décider (pas de rejet pour simple trou de données).
    """
    if forward is not None and forward > 0:
        return forward, (forward <= extreme)
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
