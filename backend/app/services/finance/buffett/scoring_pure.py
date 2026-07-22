"""Scoring MOAT pur Python — zéro dépendance pandas/scipy.

Toutes les fonctions acceptent des list[dict] (une entrée par année)
et retournent des scalaires. Testable sans DB en < 1 s.
"""

from __future__ import annotations

import math
import statistics
import unicodedata

# À incrémenter dès qu'une formule MOAT change. Le cache conserve les ETF à 200,
# mais force alors le recalcul de toutes les actions avec le nouveau modèle.
SCORING_MODEL_VERSION = 3


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
# Plus petit groupe impair avec deux observations de chaque côté de la médiane.
# En dessous, une médiane locale serait presque le titre lui-même : repli secteur,
# puis global. Quelques nouvelles actions Chine/Japon ne peuvent donc pas déplacer
# artificiellement leur propre référence.
RELATIVE_MIN_PEERS = 5


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
    # Signal unique lié aux rachats/dilution : la croissance PAR ACTION mesure
    # leur effet net. Les anciens `buybacks` (flux brut) et `cap_stock_var` (flux
    # net) récompensaient une deuxième et une troisième fois la même opération.
    "eps_growth": ("bool", None),
    "cash_growth": ("bool", None),
    "debt_ratio": ("max", 0.60),
    "liab_ratio": ("min", 1.0),
    "lt_debt_ratio": ("max", 0.25),
    "debt_eq": ("max", THRESHOLD_DEBT_EQ),
    "retained_growth": ("bool", None),
    "roe": ("min", THRESHOLD_ROE),
    "roic": ("min", THRESHOLD_ROIC),
    "capex": ("max", THRESHOLD_CAPEX),
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


def _fold_label(value: object) -> str:
    """Libellé comparable (casse/accents/espaces neutralisés)."""
    folded = (
        unicodedata.normalize("NFKD", str(value or "").strip())
        .encode("ascii", "ignore")
        .decode()
        .casefold()
    )
    return " ".join(folded.split())


_FINANCIAL_SECTOR_ALIASES = {
    "finance", "financial", "financial services", "financials",
    "services financiers", "service financier",
}


def normalize_sector(secteur: object) -> str | None:
    """Clé sectorielle stable; ``None`` pour les libellés non exploitables."""
    key = _fold_label(secteur)
    if key in {"", "nan", "none", "inconnu", "unknown", "todo", "etf"}:
        return None
    if key in _FINANCIAL_SECTOR_ALIASES:
        return "financial services"
    return key


# Régions larges : elles corrigent les niveaux de valorisation propres aux
# marchés sans créer de cible de rendement/volatilité. La liste couvre les pays
# actuellement présents dans ToutBroker et reste volontairement explicite.
_COUNTRIES_BY_REGION: dict[str, set[str]] = {
    "north_america": {
        "united states", "canada", "bermuda", "bahamas",
    },
    "latin_america": {
        "argentina", "brazil", "chile", "colombia", "costa rica", "curacao",
        "mexico", "martinique", "panama", "peru", "uruguay",
    },
    "europe": {
        "austria", "belgium", "bulgaria", "cyprus", "czech republic", "denmark",
        "finland", "france", "germany", "gibraltar", "greece", "guernsey",
        "hungary", "iceland", "ireland", "isle of man", "italy", "jersey",
        "lithuania", "luxembourg", "malta", "monaco", "netherlands", "norway",
        "poland", "portugal", "romania", "russia", "spain", "sweden",
        "switzerland", "turkey", "united kingdom",
    },
    "asia_pacific": {
        "australia", "british virgin islands", "cambodia", "cayman islands",
        "china", "hong kong", "india", "indonesia", "japan", "kazakhstan",
        "macau", "malaysia", "myanmar", "new zealand", "philippines",
        "singapore", "south korea", "taiwan", "thailand", "vietnam",
    },
    "middle_east_africa": {
        "gabon", "israel", "jordan", "mauritius", "morocco", "saudi arabia",
        "south africa", "united arab emirates",
    },
}
_REGION_BY_COUNTRY = {
    country: region
    for region, countries in _COUNTRIES_BY_REGION.items()
    for country in countries
}
_COUNTRY_ALIASES = {
    "au": "australia", "br": "brazil", "ca": "canada", "ch": "switzerland",
    "cn": "china", "de": "germany", "es": "spain", "fr": "france",
    "gb": "united kingdom", "hk": "hong kong", "in": "india", "it": "italy",
    "jp": "japan", "kr": "south korea", "mx": "mexico", "nl": "netherlands",
    "no": "norway", "sg": "singapore", "tw": "taiwan", "uk": "united kingdom",
    "us": "united states",
}


def region_for_country(pays: object) -> str | None:
    """Région de comparaison d'un pays Yahoo Finance, sinon ``None``."""
    key = _fold_label(pays)
    return _REGION_BY_COUNTRY.get(_COUNTRY_ALIASES.get(key, key))


def _applicable_criteria(secteur: str = "", industrie: str = "") -> set[str]:
    keys = set(_CRITERIA)
    keys -= _SECTOR_EXCLUDED.get(normalize_sector(secteur) or "", set())
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
        retained_growth, roe, roic, capex,
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


def robust_growth(values) -> float | None:
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
    forward: float | None,
    growth_rev: float | None,
    growth_eps: float | None,
    extreme: float = GROWTH_EXTREME,
) -> tuple[float | None, bool]:
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


def _finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _positive_float(value: object) -> float | None:
    result = _finite_float(value)
    return result if result is not None and result > 0 else None


def _group_medians(rows: list[dict], field: str, group: str) -> tuple[dict[str, float], dict[str, int]]:
    values: dict[str, list[float]] = {}
    for row in rows:
        key = row.get(group)
        value = _positive_float(row.get(field))
        if key and value is not None:
            values.setdefault(str(key), []).append(value)
    return (
        {key: float(statistics.median(items)) for key, items in values.items()},
        {key: len(items) for key, items in values.items()},
    )


def _hierarchical_reference(
    sector: str | None,
    region: str | None,
    by_sector_region: dict[str, float],
    sector_region_counts: dict[str, int],
    by_sector: dict[str, float],
    sector_counts: dict[str, int],
    global_median: float | None,
    global_count: int,
) -> tuple[float | None, str, int]:
    """Référence stable : secteur×région → secteur → univers global.

    Une strate locale n'est utilisée qu'avec :data:`RELATIVE_MIN_PEERS`
    observations valides. Cela évite qu'un singleton soit sa propre référence
    (ratio 1,0 garanti) et rend l'ajout progressif de nouveaux pays inoffensif.
    """
    intersection = f"{sector or ''}\x1f{region or ''}"
    local_n = sector_region_counts.get(intersection, 0)
    if local_n >= RELATIVE_MIN_PEERS:
        return by_sector_region.get(intersection), "sector_region", local_n
    sector_n = sector_counts.get(sector or "", 0)
    if sector_n >= RELATIVE_MIN_PEERS:
        return by_sector.get(sector or ""), "sector", sector_n
    if global_count >= RELATIVE_MIN_PEERS:
        return global_median, "global", global_count
    return None, "insufficient", global_count


def selection_score(raw_score: object, metrics: dict | None = None) -> float:
    """Score comparable entre secteurs/régions, avec repli sur le score brut."""
    metrics = metrics or {}
    value = _finite_float(metrics.get("ScoreSelection"))
    if value is None:
        relative = metrics.get("valuation_relative") or {}
        value = _finite_float(relative.get("score_selection"))
    if value is None:
        value = _finite_float(raw_score) or 0.0
    return max(0.0, min(200.0, value))


def is_selection_eligible(
    raw_score: object,
    metrics: dict | None,
    threshold: float,
    *,
    is_etf: bool = False,
    is_forced: bool = False,
    is_held: bool = False,
) -> bool:
    """Décision finale du crible avant les filtres de liquidité/produit.

    Une action ordinaire doit satisfaire les deux conditions indépendantes :
    qualité relative au-dessus du seuil ET valorisation relative achetable.
    ETF, titres explicitement forcés et positions déjà présentes dans la cible
    restent dans l'univers afin que l'optimiseur puisse les conserver ou les
    réduire. Ils restent soumis aux filtres aval qui leur sont applicables.
    """
    if is_etf or is_forced or is_held:
        return True
    return bool(
        selection_score(raw_score, metrics) >= threshold
        and (metrics or {}).get("Achat", False)
    )


def calibrate_relative_selection(
    results: dict[str, tuple[float, dict]],
    *,
    always_buy: set[str] | None = None,
) -> dict[str, tuple[float, dict]]:
    """Normalise qualité, PER et PEG relativement au secteur ET à la région.

    La population de référence contient toutes les actions valides du run, pas
    seulement celles qui dépassent déjà le score de sélection. Cela évite un
    cercle vicieux où le filtre financier détermine lui-même sa médiane.

    - le score de qualité est recentré sur la médiane de ses pairs, puis
      ré-ancré sur la médiane globale ;
    - PER et PEG sont divisés par leur médiane de pairs ; ``1`` signifie donc
      exactement « au niveau des pairs » ;
    - les pairs sont cherchés dans secteur×région avec au moins 5 observations,
      sinon dans le secteur mondial, sinon dans tout l'univers ;
    - ``Achat`` exige PER relatif <= 1 et, si calculable, PEG relatif <= 1.

    Aucun objectif de rendement/volatilité ni plafond PER/PEG universel n'entre
    dans cette fonction. Le dictionnaire d'entrée n'est pas muté.
    """
    forced = {str(t).strip().upper() for t in (always_buy or set())}
    rows: list[dict] = []
    for ticker, (raw_score, source_metrics) in results.items():
        metrics = dict(source_metrics or {})
        score = _finite_float(raw_score) or 0.0
        is_etf = score >= 200.0 or _fold_label(metrics.get("Secteur")) == "etf"
        sector = None if is_etf else normalize_sector(metrics.get("Secteur"))
        region = None if is_etf else region_for_country(metrics.get("Pays"))
        rows.append({
            "ticker": str(ticker),
            "score": score,
            "metrics": metrics,
            "is_etf": is_etf,
            "sector": sector,
            "region": region,
            "peer_group": f"{sector or ''}\x1f{region or ''}",
            "per": _positive_float(metrics.get("PER")),
            "peg": _positive_float(metrics.get("PEG")),
        })

    peers = [row for row in rows if not row["is_etf"] and row["sector"] and row["region"]]

    score_peers = [row for row in peers if 0.0 < row["score"] < 200.0]
    score_global = (
        float(statistics.median(row["score"] for row in score_peers))
        if score_peers else None
    )
    score_pair, score_pair_n = _group_medians(score_peers, "score", "peer_group")
    score_sector, score_sector_n = _group_medians(score_peers, "score", "sector")

    per_pair, per_pair_n = _group_medians(peers, "per", "peer_group")
    per_sector, per_sector_n = _group_medians(peers, "per", "sector")
    per_values = [row["per"] for row in peers if row["per"] is not None]
    per_global = float(statistics.median(per_values)) if per_values else None

    peg_pair, peg_pair_n = _group_medians(peers, "peg", "peer_group")
    peg_sector, peg_sector_n = _group_medians(peers, "peg", "sector")
    peg_values = [row["peg"] for row in peers if row["peg"] is not None]
    peg_global = float(statistics.median(peg_values)) if peg_values else None

    calibrated: dict[str, tuple[float, dict]] = {}
    for row in rows:
        ticker = row["ticker"]
        raw_score = row["score"]
        metrics = row["metrics"]
        if row["is_etf"] or ticker.strip().upper() in forced:
            metrics["Achat"] = True
            metrics["ScoreSelection"] = raw_score
            calibrated[ticker] = (raw_score, metrics)
            continue

        sector = row["sector"]
        region = row["region"]
        quality_ref, quality_scope, quality_n = _hierarchical_reference(
            sector, region,
            score_pair, score_pair_n, score_sector, score_sector_n,
            score_global, len(score_peers),
        )
        if quality_ref is not None and score_global is not None:
            adjusted_score = raw_score + score_global - quality_ref
        else:
            adjusted_score = raw_score
        adjusted_score = max(0.0, min(100.0, adjusted_score))

        per_ref, per_scope, per_n = _hierarchical_reference(
            sector, region,
            per_pair, per_pair_n, per_sector, per_sector_n,
            per_global, len(per_values),
        )
        peg_ref, peg_scope, peg_n = _hierarchical_reference(
            sector, region,
            peg_pair, peg_pair_n, peg_sector, peg_sector_n,
            peg_global, len(peg_values),
        )
        per_relative = row["per"] / per_ref if row["per"] is not None and per_ref else None
        peg_relative = row["peg"] / peg_ref if row["peg"] is not None and peg_ref else None

        base_eligible = metrics.get("valuation_base_eligible")
        if base_eligible is None:
            base_eligible = bool(
                sector and region and row["per"] is not None
                and metrics.get("growth_reliable", True) is not False
            )
        achat = bool(
            base_eligible
            and per_relative is not None and per_relative <= 1.0
            and (peg_relative is None or peg_relative <= 1.0)
        )

        relative = {
            "model": "sector_region_median_v1",
            "region": region,
            "score_selection": round(adjusted_score, 4),
            "quality_reference": round(quality_ref, 4) if quality_ref is not None else None,
            "quality_global_median": round(score_global, 4) if score_global is not None else None,
            "quality_peer_scope": quality_scope,
            "quality_peer_count": quality_n,
            "per_reference": round(per_ref, 6) if per_ref is not None else None,
            "per_relative": round(per_relative, 6) if per_relative is not None else None,
            "per_peer_scope": per_scope,
            "per_peer_count": per_n,
            "peg_reference": round(peg_ref, 6) if peg_ref is not None else None,
            "peg_relative": round(peg_relative, 6) if peg_relative is not None else None,
            "peg_peer_scope": peg_scope,
            "peg_peer_count": peg_n,
        }
        metrics["Achat"] = achat
        metrics["valuation_base_eligible"] = bool(base_eligible)
        metrics["ScoreSelection"] = adjusted_score
        metrics["valuation_relative"] = relative
        calibrated[ticker] = (raw_score, metrics)
    return calibrated


def compute_buy_signal(
    secteur: str,
    pays: str,
    prix: float,
    eps: float,
    per: float,
    growth: float | None,
    taux_obligataires: dict,
    taux_defaut: float,
    per_max: float,
    peg_max: float,
    growth_reliable: bool = True,
    peg_growth_cap: float = PEG_GROWTH_CAP,
) -> tuple[bool, float | None]:
    """Calcule l'admissibilité de base et le PEG (pur Python).

    ``growth`` : croissance annualisée (fraction) déjà sélectionnée (forward →
    historique conservatrice, cf. ``select_growth``). Elle est BORNÉE à
    ``peg_growth_cap`` au dénominateur du PEG. ``growth_reliable=False`` bloque
    l'admissibilité, y compris lorsqu'un PEG numérique a pu être calculé.

    ``taux_obligataires``, ``taux_defaut``, ``per_max`` et ``peg_max`` restent dans
    la signature pour compatibilité avec les anciens appels, mais ne décident plus
    du signal. Les plafonds absolus biaisaient structurellement les secteurs et les
    pays. La décision finale est prise par :func:`calibrate_relative_selection`,
    contre les médianes secteur/région du run complet.

    Retourne (admissible_de_base: bool, peg: float | None).
    """
    if "ETF" in str(secteur).upper():
        return True, None

    peg: float | None = None
    if growth and growth > 0 and per > 0:
        g = min(growth, peg_growth_cap)   # #3 : bornage anti-PEG-aberrant
        peg = per / (g * 100)

    achat = (
        region_for_country(pays) is not None
        and normalize_sector(secteur) is not None
        and bool(growth_reliable)
        and prix > 0
        and eps > 0
        and per > 0
    )
    return achat, peg
