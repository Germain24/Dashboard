"""Calcul de l'impôt sur les plus-values de cession de valeurs mobilières (CTO,
compte-titres ordinaire — hors PEA, régime différent).

Deux régimes possibles en France ; l'utilisateur choisit LORS DE SA
DÉCLARATION, et l'option s'applique à TOUS ses revenus du capital de l'année
(pas de mix PFU sur certaines lignes / barème sur d'autres) :

- **PFU** ("Flat Tax") : 30 % du gain net = 12,8 % IR + 17,2 % prélèvements
  sociaux. Taux fixe, indépendant du revenu global.
- **Barème progressif** (sur option) : le gain est ajouté au revenu
  imposable et taxé au barème IR (0/11/30/41/45 %, tranches 2026 sur les
  revenus 2025) + 17,2 % de prélèvements sociaux (dus dans les deux cas).
  Avantageux seulement si le foyer est dans une tranche basse.

**Moins-values** : imputées sur les plus-values de la MÊME année ; le solde
négatif est reporté sur les 10 années suivantes (jamais au-delà, et jamais en
arrière). `net_gain_after_carryforward` applique ce report.

Ce module est pur (aucun accès DB/réseau) ; `compute_realized_gains_fifo`
dans `impots_transactions.py` alimente `net_gain` depuis le grand livre des
transactions.
"""

from __future__ import annotations

PFU_IR_RATE = 0.128
PFU_SOCIAL_RATE = 0.172
PFU_RATE = PFU_IR_RATE + PFU_SOCIAL_RATE  # 0.30

SOCIAL_RATE = 0.172  # prélèvements sociaux : dus dans les DEUX régimes

# Barème IR 2026 (revenus 2025), par part de quotient familial. Chaque tuple
# (plafond_tranche, taux) ; la dernière tranche a un plafond infini.
BAREME_2026: list[tuple[float, float]] = [
    (11_600.0, 0.00),
    (29_579.0, 0.11),
    (84_577.0, 0.30),
    (181_917.0, 0.41),
    (float("inf"), 0.45),
]


def net_gain_after_carryforward(
    gain_annee: float, moins_values_reportees: float,
) -> tuple[float, float]:
    """Impute le report de moins-values des années précédentes sur le gain de
    l'année (#10 ans max, géré par l'appelant qui ne transmet que le solde
    encore valide). Renvoie `(gain_net_imposable, solde_a_reporter)`.

    - Gain positif, moins-values dispo : imputation totale ou partielle.
    - Gain négatif (perte de l'année) : rien d'imposable, tout s'ajoute au
      report existant.
    """
    if gain_annee <= 0:
        return 0.0, round(moins_values_reportees - gain_annee, 2)  # -gain_annee > 0
    imputable = min(gain_annee, moins_values_reportees)
    return round(gain_annee - imputable, 2), round(moins_values_reportees - imputable, 2)


def pfu_tax(net_gain: float) -> dict[str, float]:
    """Impôt au régime PFU (Flat Tax 30 %). `net_gain` déjà net des
    moins-values imputées — un gain <= 0 ne doit rien."""
    if net_gain <= 0:
        return {"ir": 0.0, "social": 0.0, "total": 0.0}
    ir = round(net_gain * PFU_IR_RATE, 2)
    social = round(net_gain * PFU_SOCIAL_RATE, 2)
    return {"ir": ir, "social": social, "total": round(ir + social, 2)}


def bareme_marginal_tax(
    revenu_imposable: float, parts: float = 1.0,
    bareme: list[tuple[float, float]] = BAREME_2026,
) -> float:
    """Impôt IR (hors prélèvements sociaux) selon le barème progressif par
    tranche, pour `parts` parts de quotient familial (quotient conjugal +
    enfants)."""
    if parts <= 0:
        parts = 1.0
    revenu_par_part = revenu_imposable / parts
    impot_par_part = 0.0
    plancher = 0.0
    for plafond, taux in bareme:
        if revenu_par_part <= plancher:
            break
        tranche = min(revenu_par_part, plafond) - plancher
        impot_par_part += tranche * taux
        plancher = plafond
    return round(impot_par_part * parts, 2)


def bareme_tax_on_gain(
    autres_revenus_imposables: float, net_gain: float, parts: float = 1.0,
) -> dict[str, float]:
    """Impôt dû sur `net_gain` si le foyer opte pour le barème progressif.

    Méthode différentielle (le gain vient s'empiler sur les autres revenus,
    donc taxé aux tranches marginales du foyer) : impôt(autres+gain) −
    impôt(autres seuls) isole la part d'IR imputable au gain. + prélèvements
    sociaux (17,2 %, dus dans tous les cas, indépendants du barème)."""
    if net_gain <= 0:
        return {"ir": 0.0, "social": 0.0, "total": 0.0}
    ir = round(
        bareme_marginal_tax(autres_revenus_imposables + net_gain, parts)
        - bareme_marginal_tax(autres_revenus_imposables, parts), 2,
    )
    social = round(net_gain * SOCIAL_RATE, 2)
    return {"ir": ir, "social": social, "total": round(ir + social, 2)}


def compare_regimes(
    autres_revenus_imposables: float, net_gain: float, parts: float = 1.0,
) -> dict:
    """Compare PFU vs barème progressif sur `net_gain` (déjà net des
    moins-values imputées) et recommande le moins coûteux."""
    pfu = pfu_tax(net_gain)
    bareme = bareme_tax_on_gain(autres_revenus_imposables, net_gain, parts)
    recommande = "pfu" if pfu["total"] <= bareme["total"] else "bareme"
    return {"pfu": pfu, "bareme": bareme, "recommande": recommande}
