"""Projection d'épargne/investissement à intérêts composés (pur, sans réseau)."""

from __future__ import annotations


def project_savings(
    initial: float,
    versement_mensuel: float,
    taux_annuel_pct: float,
    mois: int,
) -> dict:
    """Projette une épargne avec versements mensuels et capitalisation mensuelle.

    À chaque mois : valeur = valeur × (1 + r_mensuel) + versement.
    Retourne la courbe + totaux.
    """
    mois = max(0, int(mois))
    r = (taux_annuel_pct / 100.0) / 12.0

    valeur = float(initial)
    total_verse = float(initial)
    courbe = [{"mois": 0, "valeur": round(valeur, 2), "verse": round(total_verse, 2),
               "interets": 0.0}]
    for m in range(1, mois + 1):
        valeur = valeur * (1 + r) + versement_mensuel
        total_verse += versement_mensuel
        courbe.append({
            "mois": m,
            "valeur": round(valeur, 2),
            "verse": round(total_verse, 2),
            "interets": round(valeur - total_verse, 2),
        })

    return {
        "courbe": courbe,
        "valeur_finale": round(valeur, 2),
        "total_verse": round(total_verse, 2),
        "total_interets": round(valeur - total_verse, 2),
    }


def mois_pour_objectif(
    initial: float,
    versement_mensuel: float,
    taux_annuel_pct: float,
    objectif: float,
    max_mois: int = 1200,
) -> int | None:
    """Nombre de mois pour atteindre ``objectif`` (None si hors d'atteinte sous max_mois)."""
    if initial >= objectif:
        return 0
    r = (taux_annuel_pct / 100.0) / 12.0
    valeur = float(initial)
    for m in range(1, max_mois + 1):
        valeur = valeur * (1 + r) + versement_mensuel
        if valeur >= objectif:
            return m
    return None
