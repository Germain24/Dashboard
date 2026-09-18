"""Hydratation (#66) et sommeil (#68) — stockés dans MesureSante.extra (sans migration)."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlmodel import Session, select

from app.models.sante import MesureSante

CIBLE_EAU_ML_DEFAUT = 2500


def _upsert_mesure(session: Session, date: dt.date) -> MesureSante:
    m = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    if not m:
        m = MesureSante(date=date)
        session.add(m)
        session.commit()
        session.refresh(m)
    return m


def add_water(session: Session, date: dt.date, ml: float) -> dict:
    """Ajoute ``ml`` d'eau au total du jour. Retourne l'état d'hydratation."""
    m = _upsert_mesure(session, date)
    extra = dict(m.extra or {})
    extra["eau_ml"] = max(0.0, round(float(extra.get("eau_ml", 0)) + ml))
    m.extra = extra
    session.add(m)
    session.commit()
    return get_water(session, date)


def get_water(session: Session, date: dt.date, cible_ml: int = CIBLE_EAU_ML_DEFAUT) -> dict:
    m = session.exec(select(MesureSante).where(MesureSante.date == date)).first()
    eau = float((m.extra or {}).get("eau_ml", 0)) if m and m.extra else 0.0
    return {
        "date": str(date),
        "eau_ml": eau,
        "cible_ml": cible_ml,
        "pct": round(eau / cible_ml * 100) if cible_ml else 0,
    }


def set_sleep(session: Session, date: dt.date, heures: float, qualite: Optional[int] = None) -> dict:
    """Enregistre la durée (h) et la qualité (1-5) du sommeil du jour."""
    m = _upsert_mesure(session, date)
    extra = dict(m.extra or {})
    extra["sommeil_h"] = round(float(heures), 1)
    if qualite is not None:
        extra["sommeil_q"] = int(qualite)
    m.extra = extra
    session.add(m)
    session.commit()
    return {"date": str(date), "sommeil_h": extra["sommeil_h"], "sommeil_q": extra.get("sommeil_q")}


def sleep_weight_summary(session: Session, days: int = 30) -> dict:
    """Corrélation simple sommeil ↔ poids sur la période (signe de la covariance)."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = list(session.exec(
        select(MesureSante).where(MesureSante.date >= cutoff).order_by(MesureSante.date.asc())
    ).all())
    pairs = [
        (float((r.extra or {}).get("sommeil_h")), r.poids)
        for r in rows
        if r.extra and r.extra.get("sommeil_h") is not None and r.poids is not None
    ]
    if len(pairs) < 3:
        return {"n": len(pairs), "correlation": None, "sommeil_moyen_h": None}
    n = len(pairs)
    sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
    mx, my = sx / n, sy / n
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    corr = cov / (vx ** 0.5 * vy ** 0.5) if vx > 0 and vy > 0 else 0.0
    return {"n": n, "correlation": round(corr, 2), "sommeil_moyen_h": round(mx, 1)}
