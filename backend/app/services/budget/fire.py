"""Rapport d'indépendance financière (FIRE) : taux d'épargne, années restantes (#268).

`savings_rate` et `fire_projection` sont purs (testables sans base) ; `fire_report`
est le wrapper DB : il consomme les agrégats déjà en place — `spending_trend`
(#113) pour les revenus/dépenses et `net_worth_summary` (#257) pour le
patrimoine net — sans rien recalculer.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Optional

# Règle des 4 % : le capital visé vaut 1/taux_retrait × les dépenses annuelles
# (25× à 4 %). Le rendement est un rendement RÉEL (net d'inflation), d'où 5 %
# plutôt que le nominal historique — sinon les années restantes sont optimistes.
TAUX_RETRAIT_DEFAUT = 0.04
RENDEMENT_REEL_DEFAUT = 0.05

# Borne dure de la projection : au-delà l'horizon n'a plus de sens à échelle
# humaine, et surtout la boucle ne peut jamais tourner indéfiniment quand
# l'épargne est nulle ou négative (le capital n'atteint alors jamais l'objectif).
HORIZON_MAX_DEFAUT = 60


def savings_rate(revenus: float, depenses: float) -> float:
    """Taux d'épargne en % : (revenus − dépenses) / revenus. 0 sans revenus.

    Peut être négatif (on dépense plus qu'on ne gagne) : c'est une information
    utile, pas une erreur — on ne la borne donc pas à 0.
    """
    if revenus <= 0:
        return 0.0
    return round((revenus - depenses) / revenus * 100, 1)


def fire_projection(
    patrimoine_net: float, epargne_annuelle: float, depenses_annuelles: float, *,
    taux_retrait: float = TAUX_RETRAIT_DEFAUT,
    rendement_reel: float = RENDEMENT_REEL_DEFAUT,
    horizon_max: int = HORIZON_MAX_DEFAUT,
) -> dict[str, Any]:
    """Années restantes avant l'indépendance financière. Pur.

    Simule le capital année par année (`capital × (1+rendement) + épargne`) et
    interpole linéairement dans l'année de franchissement. Cas dégénérés :

    - dépenses nulles      → objectif nul, l'indépendance est acquise (0 an) ;
    - patrimoine ≥ objectif → 0 an, `atteint=True` ;
    - objectif hors portée → la boucle s'arrête sur `horizon_max` et
      `annees_restantes` vaut None (jamais un nombre bidon). C'est le cas dès que
      l'épargne est nulle ou négative ET que le rendement ne suffit pas à
      combler l'écart — un déficit léger reste rattrapable par la capitalisation,
      et la projection le reflète alors normalement.
    """
    objectif = depenses_annuelles / taux_retrait if taux_retrait > 0 and depenses_annuelles > 0 else 0.0
    base: dict[str, Any] = {
        "patrimoine_net": round(patrimoine_net, 2),
        "epargne_annuelle": round(epargne_annuelle, 2),
        "depenses_annuelles": round(depenses_annuelles, 2),
        "objectif_fi": round(objectif, 2),
        "taux_epargne_pct": savings_rate(epargne_annuelle + depenses_annuelles, depenses_annuelles),
        "taux_retrait_pct": round(taux_retrait * 100, 2),
        "rendement_reel_pct": round(rendement_reel * 100, 2),
        "horizon_max": horizon_max,
        "progression_pct": round(patrimoine_net / objectif * 100, 1) if objectif > 0 else 100.0,
    }
    if patrimoine_net >= objectif:
        return {**base, "annees_restantes": 0.0, "atteint": True}

    capital = patrimoine_net
    for annee in range(1, horizon_max + 1):
        debut = capital
        capital = capital * (1 + rendement_reel) + epargne_annuelle
        if capital >= objectif:
            fraction = (objectif - debut) / (capital - debut) if capital > debut else 1.0
            return {**base, "annees_restantes": round(annee - 1 + fraction, 1), "atteint": False}
    return {**base, "annees_restantes": None, "atteint": False}


# ── Wrapper DB ────────────────────────────────────────────────────────────────

def fire_report(
    session, *, months: int = 12,
    taux_retrait: float = TAUX_RETRAIT_DEFAUT,
    rendement_reel: float = RENDEMENT_REEL_DEFAUT,
    horizon_max: int = HORIZON_MAX_DEFAUT,
    cad_eur: Optional[float] = None,
    today: Optional[dt.date] = None,
) -> dict[str, Any]:
    """Rapport FIRE consolidé : tendance budget + patrimoine net existants.

    Les transactions budget sont saisies en CAD (défaut du modèle) alors que le
    patrimoine est consolidé en EUR : les agrégats budget sont convertis avec le
    MÊME convertisseur que le patrimoine, sinon le ratio patrimoine/dépenses
    mélangerait deux devises. `cad_eur` injecte le taux (tests, et évite un appel
    de change quand l'appelant le connaît déjà).
    """
    from app.services.budget.analytics import spending_trend
    from app.services.finance.patrimoine import net_worth_summary, to_eur

    today = today or dt.date.today()
    history = spending_trend(session, months, today=today)
    taux = cad_eur if cad_eur is not None else to_eur(1.0, "CAD")
    n = len(history) or 1
    revenus_annuels = sum(m["revenus"] for m in history) / n * 12 * taux
    depenses_annuelles = sum(m["depenses"] for m in history) / n * 12 * taux

    patrimoine = net_worth_summary(session, cad_eur=cad_eur)["net"]
    out = fire_projection(
        patrimoine, revenus_annuels - depenses_annuelles, depenses_annuelles,
        taux_retrait=taux_retrait, rendement_reel=rendement_reel, horizon_max=horizon_max,
    )
    annees = out["annees_restantes"]
    return {
        **out,
        "revenus_annuels": round(revenus_annuels, 2),
        "mois_analyses": len(history),
        "annee_cible": today.year + math.ceil(annees) if annees is not None else None,
        "devise": "EUR",
        "taux_cad_eur": round(taux, 4),
    }
