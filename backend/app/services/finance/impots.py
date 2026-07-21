"""Estimation francaise des impots sur un CTO.

Le module se limite aux plus-values mobilieres et aux dividendes ordinaires.
Il ne remplace ni l'IFU du courtier ni le simulateur de la DGFiP. Les calculs
du barème sont volontairement presentes comme une comparaison marginale : la
decote, le plafonnement du quotient familial, les credits d'impot et les
contributions sur hauts revenus ne sont pas modelises.
"""

from __future__ import annotations

import datetime as dt

PFU_IR_RATE = 0.128
SOCIAL_RATE_BEFORE_2025 = 0.172
SOCIAL_RATE_FROM_2025 = 0.186
SOCIAL_RATE = SOCIAL_RATE_FROM_2025
PFU_RATE = PFU_IR_RATE + SOCIAL_RATE
DIVIDEND_ALLOWANCE_RATE = 0.40
DEDUCTIBLE_CSG_RATE = 0.068

# Les cles sont les annees de perception des revenus, pas les annees de
# declaration. Le bareme 2026 s'applique ainsi aux revenus 2025.
BAREMES_BY_INCOME_YEAR: dict[int, list[tuple[float, float]]] = {
    2024: [
        (11_497.0, 0.00),
        (29_315.0, 0.11),
        (83_823.0, 0.30),
        (180_294.0, 0.41),
        (float("inf"), 0.45),
    ],
    2025: [
        (11_600.0, 0.00),
        (29_579.0, 0.11),
        (84_577.0, 0.30),
        (181_917.0, 0.41),
        (float("inf"), 0.45),
    ],
}
BAREME_2026 = BAREMES_BY_INCOME_YEAR[2025]


def social_rate_for_income_year(annee: int) -> float:
    """Taux applique aux revenus du patrimoine non preleves a la source.

    Les plus-values 2025, taxees sur l'avis 2026, entrent dans le taux de
    18,6 %. Les revenus anterieurs conservent 17,2 %.
    """
    return SOCIAL_RATE_FROM_2025 if annee >= 2025 else SOCIAL_RATE_BEFORE_2025


def bareme_for_income_year(annee: int) -> tuple[list[tuple[float, float]], int, bool]:
    """Renvoie (bareme, annee_de_revenus_reference, est_provisoire)."""
    known = [year for year in BAREMES_BY_INCOME_YEAR if year <= annee]
    reference = max(known) if known else min(BAREMES_BY_INCOME_YEAR)
    return BAREMES_BY_INCOME_YEAR[reference], reference, reference != annee


def net_gain_after_carryforward(
    gain_annee: float, moins_values_reportees: float,
) -> tuple[float, float]:
    if gain_annee <= 0:
        return 0.0, round(moins_values_reportees - gain_annee, 2)
    imputable = min(gain_annee, moins_values_reportees)
    return round(gain_annee - imputable, 2), round(moins_values_reportees - imputable, 2)


def pfu_tax(
    net_gain: float,
    dividendes_bruts: float = 0.0,
    *,
    interets_bruts: float = 0.0,
    annee: int | None = None,
) -> dict[str, float]:
    annee = annee or dt.date.today().year
    base = (
        max(0.0, net_gain)
        + max(0.0, dividendes_bruts)
        + max(0.0, interets_bruts)
    )
    social_rate = social_rate_for_income_year(annee)
    ir = round(base * PFU_IR_RATE, 2)
    social = round(base * social_rate, 2)
    return {
        "base": round(base, 2),
        "ir": ir,
        "social": social,
        "total": round(ir + social, 2),
        "taux_ir_pct": round(PFU_IR_RATE * 100, 1),
        "taux_sociaux_pct": round(social_rate * 100, 1),
    }


def bareme_marginal_tax(
    revenu_imposable: float,
    parts: float = 1.0,
    bareme: list[tuple[float, float]] | None = None,
    *,
    annee: int | None = None,
) -> float:
    if parts <= 0:
        parts = 1.0
    if bareme is None:
        bareme, _, _ = bareme_for_income_year(annee or dt.date.today().year)
    revenu_par_part = max(0.0, revenu_imposable) / parts
    impot_par_part = 0.0
    plancher = 0.0
    for plafond, taux in bareme:
        if revenu_par_part <= plancher:
            break
        tranche = min(revenu_par_part, plafond) - plancher
        impot_par_part += tranche * taux
        plancher = plafond
    return round(impot_par_part * parts, 2)


def bareme_tax_on_investment(
    autres_revenus_imposables: float,
    net_gain: float,
    dividendes_bruts: float = 0.0,
    parts: float = 1.0,
    *,
    annee: int | None = None,
    dividendes_eligibles_abattement: bool = True,
    dividendes_eligibles_bruts: float | None = None,
    interets_bruts: float = 0.0,
) -> dict[str, float]:
    annee = annee or dt.date.today().year
    gain = max(0.0, net_gain)
    dividends = max(0.0, dividendes_bruts)
    interests = max(0.0, interets_bruts)
    eligible_dividends = dividends if dividendes_eligibles_bruts is None else max(
        0.0, min(dividends, dividendes_eligibles_bruts)
    )
    if not dividendes_eligibles_abattement:
        eligible_dividends = 0.0
    allowance = eligible_dividends * DIVIDEND_ALLOWANCE_RATE
    base_ir = gain + dividends + interests - allowance
    base_social = gain + dividends + interests
    bareme, _, _ = bareme_for_income_year(annee)
    ir = round(
        bareme_marginal_tax(autres_revenus_imposables + base_ir, parts, bareme)
        - bareme_marginal_tax(autres_revenus_imposables, parts, bareme),
        2,
    )
    social_rate = social_rate_for_income_year(annee)
    social = round(base_social * social_rate, 2)
    return {
        "base": round(base_social, 2),
        "base_ir": round(base_ir, 2),
        "abattement_dividendes": round(allowance, 2),
        "ir": ir,
        "social": social,
        "total": round(ir + social, 2),
        "taux_sociaux_pct": round(social_rate * 100, 1),
        "csg_deductible_annee_suivante": round(base_social * DEDUCTIBLE_CSG_RATE, 2),
    }


def bareme_tax_on_gain(
    autres_revenus_imposables: float,
    net_gain: float,
    parts: float = 1.0,
    *,
    annee: int | None = None,
) -> dict[str, float]:
    return bareme_tax_on_investment(
        autres_revenus_imposables,
        net_gain,
        parts=parts,
        annee=annee,
    )


def compare_regimes(
    autres_revenus_imposables: float,
    net_gain: float,
    parts: float = 1.0,
    *,
    annee: int | None = None,
    dividendes_bruts: float = 0.0,
    dividendes_eligibles_abattement: bool = True,
    dividendes_eligibles_bruts: float | None = None,
    interets_bruts: float = 0.0,
) -> dict:
    annee = annee or dt.date.today().year
    pfu = pfu_tax(
        net_gain,
        dividendes_bruts,
        interets_bruts=interets_bruts,
        annee=annee,
    )
    bareme = bareme_tax_on_investment(
        autres_revenus_imposables,
        net_gain,
        dividendes_bruts,
        parts,
        annee=annee,
        dividendes_eligibles_abattement=dividendes_eligibles_abattement,
        dividendes_eligibles_bruts=dividendes_eligibles_bruts,
        interets_bruts=interets_bruts,
    )
    if pfu["total"] == bareme["total"]:
        recommande = "egalite"
    else:
        recommande = "pfu" if pfu["total"] < bareme["total"] else "bareme"
    return {"pfu": pfu, "bareme": bareme, "recommande": recommande}
