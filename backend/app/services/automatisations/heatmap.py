"""Heatmap annuelle multi-métriques (#233).

Restitue la valeur quotidienne d'une métrique de vie sur ~1 an (depuis les
DailySnapshot #212), pour un rendu « contributions » côté UI. build_heatmap est
pur ; compute_heatmap charge la base.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlmodel import Session

from app.services.automatisations.correlations import extract_metrics, load_snapshot_series


def build_heatmap(
    snapshots: list[tuple[dt.date, dict]], metric: str,
) -> dict[str, Any]:
    """Cellules {date, value} pour `metric` + liste des métriques disponibles."""
    metrics = extract_metrics(snapshots)
    series = metrics.get(metric, {})
    cells = [{"date": d.isoformat(), "value": v} for d, v in sorted(series.items())]
    vals = [c["value"] for c in cells]
    return {
        "metric": metric,
        "available": sorted(metrics.keys()),
        "cells": cells,
        "min": min(vals) if vals else 0,
        "max": max(vals) if vals else 0,
    }


def compute_heatmap(
    session: Session, *, metric: str = "Humeur", days: int = 365,
) -> dict[str, Any]:
    return build_heatmap(load_snapshot_series(session, days=days), metric)
