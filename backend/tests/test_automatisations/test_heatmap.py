"""Tests TDD — heatmap annuelle multi-métriques (#233)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.heatmap import build_heatmap

D = dt.date(2026, 6, 1)


def _snaps():
    return [
        (D, {"humeur": {"valeur": 7, "energie": 6}, "habitudes": {"pct": 80}}),
        (D + dt.timedelta(days=1), {"humeur": {"valeur": 4, "energie": 5}, "habitudes": {"pct": 50}}),
        (D + dt.timedelta(days=2), {"humeur": {"valeur": 9, "energie": 8}}),
    ]


def test_cells_for_metric_sorted_by_date():
    out = build_heatmap(_snaps(), "Humeur")
    assert out["metric"] == "Humeur"
    dates = [c["date"] for c in out["cells"]]
    assert dates == sorted(dates)
    assert out["cells"][0] == {"date": D.isoformat(), "value": 7}
    assert out["min"] == 4 and out["max"] == 9


def test_available_metrics_listed():
    out = build_heatmap(_snaps(), "Humeur")
    assert "Humeur" in out["available"] and "Habitudes %" in out["available"]


def test_unknown_metric_returns_empty_cells():
    out = build_heatmap(_snaps(), "Inconnu")
    assert out["cells"] == []
    assert out["min"] == 0 and out["max"] == 0
