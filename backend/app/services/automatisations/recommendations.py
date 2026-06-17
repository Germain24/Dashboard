"""Recommandations personnalisées priorisées par impact (#227).

Agrège des signaux déjà calculés (composantes du bien-être #222, points de
vigilance #223, anomalies #213) et les classe par impact estimé (0-100) pour
proposer des actions concrètes, les plus utiles en premier.

rank_recommendations est pur (testable) ; compute_recommendations charge les
signaux depuis les services.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

_IMPACT_VIGILANCE = 55
_IMPACT_ANOMALIE = 70


def rank_recommendations(
    *,
    wellbeing_components: dict[str, float] | None = None,
    vigilance: list[str] | None = None,
    anomalies: list[str] | None = None,
    min_impact: float = 0,
) -> list[dict[str, Any]]:
    """Construit et classe les recommandations par impact décroissant."""
    recs: list[dict[str, Any]] = []

    if wellbeing_components:
        label, score = min(wellbeing_components.items(), key=lambda kv: kv[1])
        recs.append({
            "titre": f"Renforce « {label} »",
            "module": label,
            "impact": round(max(0.0, 100 - score)),
            "raison": f"composante la plus basse du bien-être ({round(score)}/100)",
        })

    for v in (vigilance or []):
        recs.append({
            "titre": v, "module": "insights", "impact": _IMPACT_VIGILANCE,
            "raison": "point de vigilance cette semaine",
        })

    for a in (anomalies or []):
        recs.append({
            "titre": a, "module": "anomalie", "impact": _IMPACT_ANOMALIE,
            "raison": "anomalie détectée dans tes routines",
        })

    recs = [r for r in recs if r["impact"] >= min_impact]
    recs.sort(key=lambda r: -r["impact"])
    return recs


def compute_recommendations(session: Session, *, min_impact: float = 0) -> list[dict[str, Any]]:
    """Charge les signaux (bien-être, insights, anomalies) et les classe."""
    components: dict[str, float] = {}
    try:
        from app.services.automatisations.snapshot import build_daily_snapshot
        from app.services.automatisations.wellbeing import compute_wellbeing_score
        wb = compute_wellbeing_score(build_daily_snapshot(session))
        components = dict(wb.get("components") or {})
    except Exception:
        pass

    vigilance: list[str] = []
    try:
        from app.services.automatisations.insights import build_weekly_insights
        vigilance = list(build_weekly_insights(session).get("vigilance") or [])
    except Exception:
        pass

    anomalies: list[str] = []
    try:
        from app.services.automatisations.anomalies import run_anomaly_detection
        for a in run_anomaly_detection(session, notify=False) or []:
            anomalies.append(a.get("message") if isinstance(a, dict) else str(a))
    except Exception:
        pass

    return rank_recommendations(
        wellbeing_components=components, vigilance=vigilance,
        anomalies=anomalies, min_impact=min_impact,
    )
