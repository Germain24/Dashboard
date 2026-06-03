"""Intégration Entraînement → Santé : calories dépensées en séance (#67).

Côté Santé, l'intensité des séances ajuste déjà *catégoriquement* la cible
calorique (CONV 7, `_resolve_intensity`). Cet item complète l'intégration en
exposant la dépense calorique **réelle** mesurée par le module Entraînement
(`kcal_for_date`), pour afficher le bilan net du jour (consommé − dépensé).

Fallback défensif : si Entraînement est indisponible (table manquante, import
KO), on retourne `{total_kcal: 0, available: False}` au lieu de planter.
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session


def burned_kcal_for_date(session: Session, date: dt.date) -> dict:
    """Calories dépensées en séance ce jour-là (muscu + cardio).

    Retour stable :
        {date, total_kcal, kcal_muscu, kcal_cardio, available}
    """
    base = {
        "date": str(date),
        "total_kcal": 0.0,
        "kcal_muscu": 0.0,
        "kcal_cardio": 0.0,
        "available": False,
    }
    try:
        from app.services.entrainement.calories import kcal_for_date
    except Exception:  # pragma: no cover — défensif
        return base
    try:
        r = kcal_for_date(session, date)
    except Exception:  # pragma: no cover — défensif
        return base
    return {
        "date": str(date),
        "total_kcal": float(r.get("total_kcal", 0.0)),
        "kcal_muscu": float(r.get("kcal_muscu", 0.0)),
        "kcal_cardio": float(r.get("kcal_cardio", 0.0)),
        "available": True,
    }
