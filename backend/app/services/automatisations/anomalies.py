"""Détection d'anomalies de routine (#213).

Analyse les 7 derniers jours de données (poids, sommeil, dépenses) et
envoie une Notification proactive quand une déviation significative est détectée.
"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Optional

from sqlmodel import Session, select

from app.models.scheduler import Notification


# ─── Fonctions pures ─────────────────────────────────────────────────────────

def detect_weight_anomaly(
    weights: list[float],
    spike_threshold: float = 2.0,
    min_samples: int = 5,
) -> Optional[dict]:
    """Détecte un gain/perte rapide de poids (> spike_threshold en 3 jours).

    `weights` : liste chronologique (le plus ancien en premier).
    """
    if len(weights) < min_samples:
        return None
    recent = weights[-3:]
    baseline = weights[:-3]
    if not baseline:
        return None
    baseline_mean = statistics.mean(baseline)
    recent_mean = statistics.mean(recent)
    delta = recent_mean - baseline_mean
    if abs(delta) >= spike_threshold:
        return {
            "type": "weight_spike",
            "delta": round(delta, 2),
            "baseline_mean": round(baseline_mean, 2),
            "recent_mean": round(recent_mean, 2),
        }
    return None


def detect_sleep_anomaly(
    hours: list[float],
    deficit_threshold: float = 6.0,
    min_low_days: int = 5,
) -> Optional[dict]:
    """Détecte un déficit chronique de sommeil (< 6h sur ≥5 des 7 derniers jours)."""
    if not hours:
        return None
    low_days = sum(1 for h in hours if h < deficit_threshold)
    if low_days >= min_low_days:
        moyenne = round(statistics.mean(hours), 2)
        return {
            "type": "sleep_deficit",
            "moyenne": moyenne,
            "jours_en_deficit": low_days,
        }
    return None


def detect_expense_anomaly(
    weekly_totals: list[float],
    multiplier: float = 1.5,
    min_samples: int = 3,
) -> Optional[dict]:
    """Détecte un pic de dépenses hebdomadaires (dernière semaine > 1.5× la moyenne)."""
    if len(weekly_totals) < min_samples:
        return None
    derniere = weekly_totals[-1]
    history = weekly_totals[:-1]
    moyenne = statistics.mean(history)
    if moyenne > 0 and derniere > moyenne * multiplier:
        return {
            "type": "expense_spike",
            "valeur": round(derniere, 2),
            "moyenne": round(moyenne, 2),
            "ratio": round(derniere / moyenne, 2),
        }
    return None


# ─── Collecte des données ────────────────────────────────────────────────────

def _get_weight_series(session: Session, today: dt.date, days: int = 10) -> list[float]:
    from app.models.sante import MesureSante
    start = today - dt.timedelta(days=days)
    rows = session.exec(
        select(MesureSante)
        .where(MesureSante.date >= start)
        .where(MesureSante.date <= today)
        .where(MesureSante.poids.isnot(None))  # type: ignore[attr-defined]
        .order_by(MesureSante.date)
    ).all()
    return [r.poids for r in rows if r.poids is not None]


def _get_sleep_series(session: Session, today: dt.date, days: int = 7) -> list[float]:
    from app.models.sante import MesureSante
    start = today - dt.timedelta(days=days)
    rows = session.exec(
        select(MesureSante)
        .where(MesureSante.date >= start)
        .where(MesureSante.date <= today)
        .order_by(MesureSante.date)
    ).all()
    hours = []
    for r in rows:
        extra = r.extra or {}
        if "sleep_hours" in extra:
            try:
                hours.append(float(extra["sleep_hours"]))
            except (ValueError, TypeError):
                pass
    return hours


def _get_weekly_expense_series(session: Session, today: dt.date, weeks: int = 6) -> list[float]:
    """Retourne les totaux de dépenses par semaine (valeur absolue), du plus ancien au plus récent."""
    try:
        from app.models.budget import BudgetTransaction
    except ImportError:
        return []

    totals = []
    for week_offset in range(weeks, 0, -1):
        week_start = today - dt.timedelta(weeks=week_offset)
        week_end = week_start + dt.timedelta(days=7)
        rows = session.exec(
            select(BudgetTransaction)
            .where(BudgetTransaction.date >= week_start)
            .where(BudgetTransaction.date < week_end)
            .where(BudgetTransaction.montant < 0)
        ).all()
        total = sum(abs(r.montant) for r in rows)
        totals.append(total)
    return totals


# ─── Orchestration ────────────────────────────────────────────────────────────

def run_anomaly_detection(
    session: Session,
    today: Optional[dt.date] = None,
) -> list[dict]:
    """Lance la détection sur les 3 axes et crée des Notifications pour les anomalies."""
    today = today or dt.date.today()
    anomalies: list[dict] = []

    weight_series = _get_weight_series(session, today)
    w_anomaly = detect_weight_anomaly(weight_series)
    if w_anomaly:
        delta = w_anomaly["delta"]
        direction = "hausse" if delta > 0 else "baisse"
        session.add(Notification(
            source="anomaly_weight",
            level="warning",
            titre="Variation de poids inhabituelle",
            message=f"{direction} de {abs(delta):.1f} kg sur 3 jours (moy. ref {w_anomaly['baseline_mean']:.1f}kg)",
        ))
        anomalies.append(w_anomaly)

    sleep_series = _get_sleep_series(session, today)
    s_anomaly = detect_sleep_anomaly(sleep_series)
    if s_anomaly:
        session.add(Notification(
            source="anomaly_sleep",
            level="warning",
            titre="Deficit de sommeil detecte",
            message=f"Moyenne {s_anomaly['moyenne']}h/nuit sur {s_anomaly['jours_en_deficit']} jours (cible >= 6h)",
        ))
        anomalies.append(s_anomaly)

    expense_series = _get_weekly_expense_series(session, today)
    e_anomaly = detect_expense_anomaly(expense_series)
    if e_anomaly:
        session.add(Notification(
            source="anomaly_expenses",
            level="warning",
            titre="Depenses inhabituelles",
            message=f"Cette semaine : {e_anomaly['valeur']:.0f}$ vs moy. {e_anomaly['moyenne']:.0f}$ (x{e_anomaly['ratio']:.1f})",
        ))
        anomalies.append(e_anomaly)

    if anomalies:
        session.commit()
    return anomalies
