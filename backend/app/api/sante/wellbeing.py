"""Sous-routeur Santé : hydratation, sommeil, dépense, qualité, bilan énergétique (#504)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.db import get_session

router = APIRouter()


@router.post("/water")
def add_water(date: dt.date | None = None, ml: float = 250, session: Session = Depends(get_session)):
    """Ajoute de l'eau (ml) au total du jour (#66 hydratation)."""
    from app.services.sante.wellbeing import add_water as _add
    return _add(session, date or dt.date.today(), ml)


@router.get("/water/today")
def water_today(session: Session = Depends(get_session)):
    from app.services.sante.wellbeing import get_water
    return get_water(session, dt.date.today())


@router.post("/sleep")
def log_sleep(heures: float, qualite: int | None = None, date: dt.date | None = None,
              session: Session = Depends(get_session)):
    """Enregistre le sommeil du jour (#68)."""
    from app.services.sante.wellbeing import set_sleep
    return set_sleep(session, date or dt.date.today(), heures, qualite)


@router.get("/sleep/summary")
def sleep_summary(days: int = 30, session: Session = Depends(get_session)):
    """Corrélation sommeil ↔ poids sur la période."""
    from app.services.sante.wellbeing import sleep_weight_summary
    return sleep_weight_summary(session, days)


@router.get("/workout-burn")
def workout_burn(date: dt.date | None = None, session: Session = Depends(get_session)):
    """Calories dépensées en séance ce jour (intégration Entraînement, #67)."""
    from app.services.sante.workout import burned_kcal_for_date
    return burned_kcal_for_date(session, date or dt.date.today())


@router.get("/quality/weekly")
def quality_weekly(days: int = Query(7, ge=1, le=31), session: Session = Depends(get_session)):
    """Score de qualité nutritionnelle sur la fenêtre glissante (#65)."""
    from app.services.sante.quality import weekly_nutrition_quality
    return weekly_nutrition_quality(session, days=days)


@router.get("/energy/balance")
def energy_balance(days: int = Query(7, ge=1, le=31), session: Session = Depends(get_session)):
    """Bilan énergétique moyen + alerte déficit/surplus agressif (#70)."""
    from app.services.sante.energy import weekly_energy_balance
    return weekly_energy_balance(session, days=days)
