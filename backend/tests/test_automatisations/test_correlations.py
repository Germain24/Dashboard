"""Tests TDD — moteur de corrélations cross-modules (#221)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.correlations import (
    correlate_series,
    extract_metrics,
    pearson,
)

D = dt.date(2026, 6, 1)


def _days(n):
    return [D + dt.timedelta(days=i) for i in range(n)]


# ── Pearson ─────────────────────────────────────────────────────────────────--

def test_pearson_perfect_positive():
    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0


def test_pearson_perfect_negative():
    assert pearson([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0


def test_pearson_no_variance_returns_none():
    assert pearson([5, 5, 5], [1, 2, 3]) is None


# ── correlate_series ──────────────────────────────────────────────────────────

def test_correlate_aligns_common_dates_and_filters_min_pairs():
    days = _days(8)
    a = {d: i for i, d in enumerate(days)}
    b = {d: i * 2 for i, d in enumerate(days)}
    out = correlate_series({"A": a, "B": b}, min_pairs=5, min_abs_r=0.3)
    assert len(out) == 1
    assert out[0]["a"] in ("A", "B") and out[0]["b"] in ("A", "B")
    assert round(out[0]["r"], 3) == 1.0
    assert out[0]["n"] == 8


def test_correlate_skips_pairs_below_min_pairs():
    days = _days(3)
    a = {d: i for i, d in enumerate(days)}
    b = {d: i for i, d in enumerate(days)}
    assert correlate_series({"A": a, "B": b}, min_pairs=5) == []


def test_correlate_filters_weak_correlations():
    days = _days(10)
    a = {d: i for i, d in enumerate(days)}
    b = {d: (i * 7) % 3 for i, d in enumerate(days)}  # quasi sans lien
    out = correlate_series({"A": a, "B": b}, min_pairs=5, min_abs_r=0.6)
    assert out == []


def test_correlate_sorted_by_abs_r_desc():
    days = _days(10)
    base = {d: i for i, d in enumerate(days)}
    strong_neg = {d: -i for i, d in enumerate(days)}          # r = -1
    weak = {d: [0, 1, 0, 1, 2, 1, 3, 2, 4, 3][i] for i, d in enumerate(days)}
    out = correlate_series({"X": base, "Y": strong_neg, "Z": weak}, min_pairs=5, min_abs_r=0.0)
    assert abs(out[0]["r"]) >= abs(out[-1]["r"])  # trié décroissant en |r|


# ── extract_metrics ───────────────────────────────────────────────────────────

def test_extract_metrics_pulls_nested_numeric_values():
    snaps = [
        (D, {"humeur": {"valeur": 7, "energie": 6}, "sante": {"poids": 70.0}}),
        (D + dt.timedelta(days=1), {"humeur": {"valeur": 5, "energie": 4}, "sante": {"poids": 70.5}}),
    ]
    metrics = extract_metrics(snaps)
    assert metrics["Humeur"][D] == 7
    assert metrics["Énergie"][D + dt.timedelta(days=1)] == 4
    assert metrics["Poids"][D] == 70.0


def test_extract_metrics_skips_missing_and_none():
    snaps = [
        (D, {"humeur": {"valeur": 7}}),
        (D + dt.timedelta(days=1), {"humeur": {"valeur": None}, "sante": {"poids": 70}}),
    ]
    metrics = extract_metrics(snaps)
    assert D in metrics["Humeur"] and (D + dt.timedelta(days=1)) not in metrics["Humeur"]
    assert "Poids" in metrics and metrics["Poids"][D + dt.timedelta(days=1)] == 70
