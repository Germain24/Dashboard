"""Profils de valorisation par secteur — pur Python, zéro dépendance pandas.

Le signal d'achat compare chaque titre aux quantiles de SON secteur. Le PER et le
PEG classiques ne sont pas comparables partout :

- immobilier : le résultat net est écrasé par les amortissements comptables ;
- cycliques : au sommet du cycle les bénéfices explosent, le PER paraît bas juste
  avant le retournement ;
- valeurs matures : une croissance faible mais un gros dividende rend le PEG nu
  systématiquement mauvais (d'où le PEG ajusté du dividende de Peter Lynch) ;
- banques/assureurs : le PER seul ignore la rentabilité des fonds propres.

Chaque secteur reçoit donc un profil à DEUX axes (valeur + qualité), et jamais
plus : les seuils étant des quantiles, chaque filtre supplémentaire coupe encore
une fraction du secteur et finirait par l'assécher.

Règle d'or : le quantile d'un secteur est calculé sur la MÊME métrique que le
filtre de ce secteur. Aucune valeur spécialisée ne rejoint le pool global, qui
reste en PER/PEG.

Convention : toutes les métriques sont orientées « plus petit = mieux », comme le
PER et le PEG. En particulier ``peg_dividende = PER / (g + rendement)`` — la règle
« intéressant si > 1 » de Lynch s'applique à la formule INVERSE et ne doit pas
être transposée telle quelle ici.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# À incrémenter à chaque changement de formule : permet d'ignorer un bloc
# `secteurs_extra["valuation"]` calculé par une version antérieure.
VALUATION_MODEL_VERSION = 1


@dataclass(frozen=True)
class ValuationAxis:
    """Un axe de comparaison sectorielle (toujours « plus petit = mieux »)."""

    key: str
    label: str


@dataclass(frozen=True)
class ValuationProfile:
    name: str
    value_axis: ValuationAxis
    quality_axis: ValuationAxis


STANDARD = ValuationProfile(
    "standard",
    ValuationAxis("per", "PER"),
    ValuationAxis("peg", "PEG"),
)

_IMMOBILIER = ValuationProfile(
    "immobilier",
    ValuationAxis("p_ffo", "P/FFO"),
    ValuationAxis("peg_ffo", "PEG (FFO)"),
)

_CYCLIQUE = ValuationProfile(
    "cyclique",
    ValuationAxis("per_normalise", "PER normalisé"),
    ValuationAxis("peg_normalise", "PEG normalisé"),
)

_MATURE = ValuationProfile(
    "mature",
    ValuationAxis("per", "PER"),
    ValuationAxis("peg_dividende", "PEG ajusté du dividende"),
)

_FINANCE = ValuationProfile(
    "finance",
    ValuationAxis("pb_over_roe", "P/B ÷ ROE"),
    ValuationAxis("peg_dividende", "PEG ajusté du dividende"),
)

# Clés = secteurs canoniques FR produits par breakdown._canon_sector.
_PROFILE_BY_SECTOR: dict[str, ValuationProfile] = {
    "Immobilier": _IMMOBILIER,
    "Energie": _CYCLIQUE,
    "Materiaux": _CYCLIQUE,
    "Industrie": _CYCLIQUE,
    "Conso. de base": _MATURE,
    "Services aux collectivites": _MATURE,
    "Finance": _FINANCE,
}

_PROFILE_BY_NAME: dict[str, ValuationProfile] = {
    profile.name: profile
    for profile in (STANDARD, _IMMOBILIER, _CYCLIQUE, _MATURE, _FINANCE)
}


def profile_for_sector(
    canon_sector: str,
    *,
    enabled: bool = True,
    overrides: Mapping[str, str] | None = None,
) -> ValuationProfile:
    """Profil d'un secteur canonique ; ``STANDARD`` si désactivé ou inconnu."""
    if not enabled:
        return STANDARD
    sector = str(canon_sector or "").strip()
    forced = (overrides or {}).get(sector)
    if forced:
        return _PROFILE_BY_NAME.get(str(forced), STANDARD)
    return _PROFILE_BY_SECTOR.get(sector, STANDARD)


def _positive_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def dividend_yield_pct(raw, *, max_pct: float = 15.0) -> float | None:
    """Rendement du dividende en POURCENTAGE.

    Yahoo renvoie déjà un pourcentage (médiane observée ~2,8 sur le cache local).
    On ne tente donc AUCUNE conversion automatique : l'heuristique « valeur ≤ 1
    ⇒ multiplier par 100 » transformerait un vrai rendement de 0,95 % en 95 %.
    Au-delà de ``max_pct`` la donnée est jugée corrompue ou piège à dividende, et
    écartée (``None``) plutôt que silencieusement écrêtée.
    """
    number = _positive_float(raw)
    if number is None or number <= 0:
        return None
    return number if number <= float(max_pct) else None


def _capped_growth_pct(
    growth: float | None, *, growth_reliable: bool, peg_growth_cap: float
) -> float | None:
    """Croissance en points de pourcentage, bornée — ou ``None`` si inutilisable."""
    if not growth_reliable:
        return None
    number = _positive_float(growth)
    if number is None or number <= 0:
        return None
    return min(number, float(peg_growth_cap)) * 100.0


def dividend_adjusted_peg(
    per: float | None,
    growth: float | None,
    dividend_pct: float | None,
    *,
    growth_reliable: bool,
    peg_growth_cap: float,
) -> float | None:
    """PEG de Lynch : ``PER / (croissance % + rendement %)``. Plus petit = mieux.

    Un dividende absent vaut 0 : une valeur mature qui ne distribue rien n'est pas
    exclue, elle est simplement moins bien classée que ses pairs distributeurs.
    """
    price_earnings = _positive_float(per)
    if price_earnings is None or price_earnings <= 0:
        return None
    growth_pct = _capped_growth_pct(
        growth, growth_reliable=growth_reliable, peg_growth_cap=peg_growth_cap
    )
    if growth_pct is None:
        return None
    yield_pct = dividend_pct if dividend_pct is not None else 0.0
    denominator = growth_pct + max(float(yield_pct), 0.0)
    if denominator <= 0:
        return None
    return price_earnings / denominator


def compute_ffo(
    net_income, depreciation_amortization, gain_loss_on_sale_ppe
) -> float | None:
    """FFO ≈ résultat net + amortissements − plus-values de cession.

    Convention de signe vérifiée sur le cache : ``Gain Loss On Sale Of PPE`` est
    POSITIF quand il s'agit d'un gain, il se retranche donc bien. Un poste absent
    vaut 0 (fréquent : la ligne n'existe que sur ~la moitié des exercices).
    """
    income = _positive_float(net_income)
    if income is None:
        return None
    depreciation = _positive_float(depreciation_amortization) or 0.0
    gain = _positive_float(gain_loss_on_sale_ppe) or 0.0
    return income + max(depreciation, 0.0) - gain


def price_to_ffo(market_cap, ffo) -> float | None:
    capitalisation = _positive_float(market_cap)
    funds = _positive_float(ffo)
    if capitalisation is None or funds is None:
        return None
    if capitalisation <= 0 or funds <= 0:
        return None
    return capitalisation / funds


def normalized_per(
    market_cap,
    net_incomes: Sequence[float] | None,
    *,
    min_years: int = 3,
    max_years: int = 5,
) -> tuple[float | None, int]:
    """PER sur bénéfice moyen des derniers exercices. Retourne (valeur, n_années).

    Ce n'est PAS un CAPE : la fenêtre disponible est de 5 ans (pas 10) et il n'y a
    pas d'ajustement d'inflation. La capitalisation est courante face à des
    bénéfices passés — c'est exactement l'effet recherché : un cyclique au sommet
    affiche un PER bas et un PER normalisé élevé.
    """
    capitalisation = _positive_float(market_cap)
    if capitalisation is None or capitalisation <= 0:
        return None, 0
    values = [
        number
        for number in (_positive_float(item) for item in (net_incomes or []))
        if number is not None
    ]
    values = values[-int(max_years):] if max_years > 0 else values
    if len(values) < int(min_years):
        return None, len(values)
    average = sum(values) / len(values)
    if average <= 0:
        # Pertes récurrentes : pas de PER normalisé exploitable (le titre sort du
        # filtre au lieu de passer grâce à un exercice ponctuellement bénéficiaire).
        return None, len(values)
    return capitalisation / average, len(values)


def price_to_book_over_roe(price_to_book, roe) -> float | None:
    """P/B rapporté à la rentabilité des fonds propres. Plus petit = mieux.

    Une banque à P/B 1,5 et ROE 15 % (0,10) est mieux valorisée qu'une banque à
    P/B 1,2 et ROE 6 % (0,20). ``roe`` est une FRACTION (0,12 = 12 %).
    """
    book = _positive_float(price_to_book)
    equity_return = _positive_float(roe)
    if book is None or equity_return is None:
        return None
    if book <= 0 or equity_return <= 0:
        return None
    return book / (equity_return * 100.0)


def build_valuation_metrics(
    *,
    secteur: str,
    per: float | None,
    growth: float | None,
    growth_reliable: bool,
    peg: float | None,
    info_fields: Mapping[str, object] | None = None,
    fundamentals: Mapping[str, object] | None = None,
    peg_growth_cap: float,
    dividend_yield_max_pct: float = 15.0,
    normalized_min_years: int = 3,
    normalized_max_years: int = 5,
) -> dict:
    """Toutes les métriques de valorisation d'un titre, quel que soit son profil.

    On calcule ce qui est calculable sans se soucier du secteur : c'est le signal
    d'achat qui choisira les deux axes pertinents. Une métrique non calculable
    vaut ``None`` — jamais 0, jamais un repli silencieux sur une autre métrique.
    """
    info = info_fields or {}
    facts = fundamentals or {}

    per_value = _positive_float(per)
    if per_value is not None and per_value <= 0:
        per_value = None

    dividend_pct = dividend_yield_pct(
        info.get("DividendYield"), max_pct=dividend_yield_max_pct
    )
    market_cap = _positive_float(info.get("MarketCap"))
    if market_cap is None or market_cap <= 0:
        shares = _positive_float(facts.get("shares_outstanding"))
        price = _positive_float(info.get("Prix"))
        market_cap = shares * price if (shares and price and shares > 0 and price > 0) else None

    growth_pct = _capped_growth_pct(
        growth, growth_reliable=growth_reliable, peg_growth_cap=peg_growth_cap
    )

    ffo = compute_ffo(
        facts.get("net_income"),
        facts.get("depreciation_amortization"),
        facts.get("gain_loss_on_sale_ppe"),
    )
    p_ffo = price_to_ffo(market_cap, ffo)
    peg_ffo = (p_ffo / growth_pct) if (p_ffo is not None and growth_pct) else None

    per_norm, years = normalized_per(
        market_cap,
        facts.get("net_income_series"),
        min_years=normalized_min_years,
        max_years=normalized_max_years,
    )
    peg_norm = (per_norm / growth_pct) if (per_norm is not None and growth_pct) else None

    return {
        "model_version": VALUATION_MODEL_VERSION,
        "per": per_value,
        "peg": _positive_float(peg),
        "p_ffo": p_ffo,
        "peg_ffo": peg_ffo,
        "per_normalise": per_norm,
        "peg_normalise": peg_norm,
        "peg_dividende": dividend_adjusted_peg(
            per_value,
            growth,
            dividend_pct,
            growth_reliable=growth_reliable,
            peg_growth_cap=peg_growth_cap,
        ),
        "pb_over_roe": price_to_book_over_roe(
            info.get("PriceToBook"), info.get("ROE")
        ),
        "dividend_yield_pct": dividend_pct,
        "price_to_book": _positive_float(info.get("PriceToBook")),
        "roe": _positive_float(info.get("ROE")),
        "market_cap": market_cap,
        "ffo": ffo,
        "net_income_years": years,
        "secteur_canonique": str(secteur or ""),
    }
