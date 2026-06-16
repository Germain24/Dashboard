"""Bilan mensuel « de vie » (#234).

Agrège un mois de DailySnapshot (#212) en un bilan synthétique, rendu côté UI
en page imprimable (-> « Enregistrer en PDF » du navigateur). Reproductible à la
demande pour n'importe quel mois (les snapshots quotidiens font l'archive).
build_monthly_report est pur ; compute_monthly_report charge la base.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot
from app.services.automatisations.correlations import extract_metrics

_MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# label -> agrégation pour le bilan
_AGG = {
    "Humeur": "mean", "Énergie": "mean", "Habitudes %": "mean",
    "Dépenses": "sum", "Séances": "sum", "Tonnage": "sum", "Événements": "sum",
}


def build_monthly_report(
    snapshots: list[tuple[dt.date, dict]], *, year: int, month: int,
) -> dict[str, Any]:
    """Bilan synthétique du mois (moyennes/sommes + évolution du poids)."""
    metrics = extract_metrics(snapshots)
    dates = sorted({d for d, _ in snapshots})

    metriques: dict[str, float] = {}
    for label, how in _AGG.items():
        vals = list(metrics.get(label, {}).values())
        if not vals:
            continue
        metriques[label] = round(sum(vals) / len(vals), 1) if how == "mean" else round(sum(vals), 2)

    poids = None
    pseries = metrics.get("Poids", {})
    if pseries:
        ordered = [pseries[d] for d in sorted(pseries)]
        poids = {"debut": ordered[0], "fin": ordered[-1], "delta": round(ordered[-1] - ordered[0], 2)}

    return {
        "annee": year,
        "mois": month,
        "periode": f"{_MOIS_FR[month]} {year}",
        "jours_couverts": len(dates),
        "metriques": metriques,
        "poids": poids,
    }


def compute_monthly_report(session: Session, *, year: int, month: int) -> dict[str, Any]:
    last_day = calendar.monthrange(year, month)[1]
    start = dt.date(year, month, 1)
    end = dt.date(year, month, last_day)
    rows = session.exec(
        select(DailySnapshot)
        .where(DailySnapshot.date >= start)
        .where(DailySnapshot.date <= end)
    ).all()
    snaps: list[tuple[dt.date, dict]] = []
    for row in rows:
        try:
            snaps.append((row.date, json.loads(row.data)))
        except (ValueError, TypeError):
            continue
    return build_monthly_report(snaps, year=year, month=month)
