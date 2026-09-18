"""Score de forme quotidien (type Garmin) — agrège sommeil + sport + nutrition.

Chaque composante est notée 0-100 (None si donnée absente). Le score du jour est
la moyenne des composantes disponibles. Fonctions de notation pures (testables) ;
`compute_score`/`score_history` lisent la base.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, func, select

from app.models.entrainement import Seance
from app.models.sante import MesureSante, PlanNutrition

SOMMEIL_CIBLE_H = 8.0
SPORT_CIBLE_SEMAINE = 4


def sommeil_score(heures: Optional[float]) -> Optional[float]:
    """100 à la cible (8 h), -12,5 pts par heure d'écart, borné [0, 100]."""
    if heures is None:
        return None
    return round(max(0.0, min(100.0, 100 - abs(heures - SOMMEIL_CIBLE_H) * 12.5)), 1)


def nutrition_score(consumed_kcal: Optional[float], target_kcal: Optional[float]) -> Optional[float]:
    """Adhérence calorique : 100 si consommé = cible, décroît avec l'écart relatif."""
    if not consumed_kcal or not target_kcal:
        return None
    ecart = abs(consumed_kcal - target_kcal) / target_kcal
    return round(max(0.0, min(100.0, 100 - ecart * 100)), 1)


def sport_score(sessions_7d: Optional[int], cible: int = SPORT_CIBLE_SEMAINE) -> Optional[float]:
    """Régularité : séances des 7 derniers jours vs cible hebdo, plafonné à 100."""
    if sessions_7d is None:
        return None
    return round(min(100.0, sessions_7d / cible * 100), 1)


def day_score(
    *, sommeil: Optional[float], sport: Optional[float], nutrition: Optional[float],
) -> dict:
    """Score global = moyenne des composantes disponibles (None si aucune)."""
    composantes = {"sommeil": sommeil, "sport": sport, "nutrition": nutrition}
    vals = [v for v in composantes.values() if v is not None]
    return {
        "score": round(sum(vals) / len(vals), 1) if vals else None,
        "composantes": composantes,
    }


# ── Lecture base ──────────────────────────────────────────────────────────────

def _sommeil_h(session: Session, date: dt.date) -> Optional[float]:
    m = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if m and m.extra and m.extra.get("sommeil_h") is not None:
        try:
            return float(m.extra["sommeil_h"])
        except (TypeError, ValueError):
            return None
    return None


def _sessions_7d(session: Session, date: dt.date) -> int:
    start = dt.datetime.combine(date - dt.timedelta(days=6), dt.time.min)
    end = dt.datetime.combine(date, dt.time.max)
    return int(session.exec(
        select(func.count()).select_from(Seance)
        .where(Seance.date >= start).where(Seance.date <= end)
    ).one())


def _nutrition_kcal(session: Session, date: dt.date) -> tuple[Optional[float], Optional[float]]:
    p = session.exec(select(PlanNutrition).where(PlanNutrition.date == date)).first()
    if not p or not p.consumed or not p.targets:
        return None, None
    return p.consumed.get("Calories"), p.targets.get("Calories")


def compute_score(session: Session, date: dt.date) -> dict:
    """Score du jour + composantes + valeurs brutes (sommeil h, séances 7j, kcal)."""
    h = _sommeil_h(session, date)
    s7 = _sessions_7d(session, date)
    cons, targ = _nutrition_kcal(session, date)
    out = day_score(
        sommeil=sommeil_score(h),
        sport=sport_score(s7),
        nutrition=nutrition_score(cons, targ),
    )
    out["date"] = date.isoformat()
    out["details"] = {
        "sommeil_h": h, "sessions_7j": s7,
        "kcal_consommees": cons, "kcal_cible": targ,
    }
    return out


def score_history(session: Session, days: int = 90) -> list[dict]:
    """Série du score sur les `days` derniers jours (croissant)."""
    today = dt.date.today()
    out = []
    for k in range(days, -1, -1):
        d = today - dt.timedelta(days=k)
        s = compute_score(session, d)
        out.append({"date": d.isoformat(), "score": s["score"]})
    return out
