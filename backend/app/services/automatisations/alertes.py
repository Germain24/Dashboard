"""Alertes de seuils configurables (#235).

L'utilisateur définit des seuils sur n'importe quelle métrique de vie
(« Poids > 80 », « Habitudes % < 50 »…). Le check évalue la dernière valeur de
chaque métrique et notifie celles qui franchissent leur seuil. Config stockée
dans les préférences (pas de modèle/migration). evaluate_alerts est pur.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlmodel import Session, select

from app.models.snapshot import DailySnapshot
from app.models.scheduler import Notification
from app.services.automatisations.correlations import METRIC_PATHS, extract_metrics
from app.services.settings import get_preferences, set_preferences

_PREF_KEY = "metric_alerts"
_OPS = {
    ">": lambda v, s: v > s,
    "<": lambda v, s: v < s,
    ">=": lambda v, s: v >= s,
    "<=": lambda v, s: v <= s,
}


def evaluate_alerts(
    alerts: list[dict], values: dict[str, float],
) -> list[dict[str, Any]]:
    """Retourne les alertes franchies par la valeur courante de leur métrique."""
    out: list[dict[str, Any]] = []
    for a in alerts:
        if not a.get("enabled", True):
            continue
        metric = a.get("metric")
        op = a.get("op")
        if metric not in values or op not in _OPS:
            continue
        seuil = float(a.get("seuil", 0))
        v = values[metric]
        if _OPS[op](v, seuil):
            out.append({
                "metric": metric, "op": op, "seuil": seuil, "valeur": v,
                "message": f"{metric} {op} {seuil} (actuel : {v})",
            })
    return out


def current_metric_values(session: Session, *, days: int = 21) -> dict[str, float]:
    """Dernière valeur connue de chaque métrique sur la fenêtre récente."""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = session.exec(select(DailySnapshot).where(DailySnapshot.date >= cutoff)).all()
    snaps: list[tuple[dt.date, dict]] = []
    for row in rows:
        try:
            snaps.append((row.date, json.loads(row.data)))
        except (ValueError, TypeError):
            continue
    metrics = extract_metrics(snaps)
    return {label: series[max(series)] for label, series in metrics.items() if series}


def get_alerts() -> list[dict]:
    return list(get_preferences().get(_PREF_KEY) or [])


def set_alerts(alerts: list[dict]) -> list[dict]:
    set_preferences({_PREF_KEY: alerts})
    return get_alerts()


def available_metrics() -> list[str]:
    return sorted(METRIC_PATHS.keys())


def check_alerts(session: Session, *, notify: bool = True) -> list[dict[str, Any]]:
    """Évalue les alertes configurées et notifie celles qui se déclenchent."""
    triggered = evaluate_alerts(get_alerts(), current_metric_values(session))
    if notify:
        for t in triggered:
            session.add(Notification(
                source="alertes", level="warning",
                titre="Seuil franchi", message=t["message"],
            ))
        if triggered:
            session.commit()
    return triggered
