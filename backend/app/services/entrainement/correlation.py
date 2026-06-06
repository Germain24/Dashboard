"""Corrélation entraînement ↔ poids (lien Santé) — #112.

Agrège, par semaine (ancrée lundi), le tonnage d'entraînement (somme reps×poids
de toutes les séries) et le poids moyen mesuré (MesureSante côté Santé), puis
calcule un coefficient de corrélation de Pearson entre les deux séries. Permet de
voir si le volume d'entraînement accompagne une prise ou une perte de poids.

`pearson` est pur et testable ; l'agrégation est déterministe (date injectable).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models.entrainement import Seance, SetSerie
from app.models.sante import MesureSante


def pearson(pairs: list[tuple[float, float]]) -> Optional[float]:
    """Coefficient de Pearson, ou None si < 3 points ou variance nulle."""
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    vx = sum((x - mx) ** 2 for x, _ in pairs)
    vy = sum((y - my) ** 2 for _, y in pairs)
    if vx <= 0 or vy <= 0:
        return None
    return round(cov / (vx ** 0.5 * vy ** 0.5), 2)


def _monday(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


@dataclass
class WeekPoint:
    semaine: str  # date ISO du lundi de la semaine
    tonnage_kg: float
    seances: int
    poids_kg: Optional[float]


def training_weight_correlation(
    session: Session, *, weeks: int = 12, today: Optional[dt.date] = None
) -> dict:
    """Séries hebdo (tonnage + poids moyen) + corrélation de Pearson sur `weeks` semaines."""
    today = today or dt.date.today()
    start = _monday(today) - dt.timedelta(days=7 * (weeks - 1))
    cutoff = dt.datetime.combine(start, dt.time.min)

    tonnage_by_week: dict[dt.date, float] = {}
    seances_by_week: dict[dt.date, set] = {}
    rows = session.exec(
        select(SetSerie, Seance)
        .join(Seance, Seance.id == SetSerie.seance_id)
        .where(Seance.date >= cutoff)
    ).all()
    for s, seance in rows:
        wk = _monday(seance.date.date())
        tonnage_by_week[wk] = tonnage_by_week.get(wk, 0.0) + (s.reps or 0) * (s.poids_kg or 0.0)
        seances_by_week.setdefault(wk, set()).add(seance.id)

    weight_by_week: dict[dt.date, list[float]] = {}
    for m in session.exec(select(MesureSante).where(MesureSante.date >= start)).all():
        if m.poids is not None:
            weight_by_week.setdefault(_monday(m.date), []).append(m.poids)

    series: list[WeekPoint] = []
    for i in range(weeks):
        wk = start + dt.timedelta(days=7 * i)
        weights = weight_by_week.get(wk, [])
        series.append(WeekPoint(
            semaine=wk.isoformat(),
            tonnage_kg=round(tonnage_by_week.get(wk, 0.0), 1),
            seances=len(seances_by_week.get(wk, set())),
            poids_kg=round(sum(weights) / len(weights), 1) if weights else None,
        ))

    pairs = [(p.tonnage_kg, p.poids_kg) for p in series if p.tonnage_kg > 0 and p.poids_kg is not None]
    return {"weeks": series, "correlation": pearson(pairs), "n": len(pairs)}
