"""Tests TDD — détection de liens décalés / « causalités probables » (#224)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.causalites import detect_lagged_links

D = dt.date(2026, 6, 1)


def _days(n):
    return [D + dt.timedelta(days=i) for i in range(n)]


def test_detects_directional_lagged_link():
    days = _days(10)
    a = {d: i for i, d in enumerate(days)}                       # A le jour J
    b = {d: i for i, d in enumerate(days)}                       # B = A décalé : B[J+1] suit A[J]
    out = detect_lagged_links({"A": a, "B": b}, lag=1, min_pairs=5, min_abs_r=0.5)
    # A[J] vs B[J+1] : A=0..8 corrélé à B=1..9 -> r=1
    link = next((x for x in out if x["cause"] == "A" and x["effet"] == "B"), None)
    assert link is not None
    assert round(link["r"], 3) == 1.0
    assert link["lag"] == 1
    assert link["n"] == 9


def test_below_min_pairs_skipped():
    days = _days(4)
    a = {d: i for i, d in enumerate(days)}
    b = {d: i for i, d in enumerate(days)}
    assert detect_lagged_links({"A": a, "B": b}, lag=1, min_pairs=5) == []


def test_weak_links_filtered():
    days = _days(12)
    a = {d: i for i, d in enumerate(days)}
    b = {d: (i * 5) % 4 for i, d in enumerate(days)}
    assert detect_lagged_links({"A": a, "B": b}, lag=1, min_pairs=5, min_abs_r=0.8) == []


def test_both_directions_considered():
    days = _days(10)
    a = {d: i for i, d in enumerate(days)}
    b = {d: 2 * i for i, d in enumerate(days)}
    out = detect_lagged_links({"A": a, "B": b}, lag=1, min_pairs=5, min_abs_r=0.5)
    pairs = {(x["cause"], x["effet"]) for x in out}
    assert ("A", "B") in pairs and ("B", "A") in pairs


def test_sorted_by_abs_r():
    days = _days(12)
    a = {d: i for i, d in enumerate(days)}
    b = {d: -i for i, d in enumerate(days)}
    c = {d: [0, 1, 0, 2, 1, 3, 2, 4, 3, 5, 4, 6][i] for i, d in enumerate(days)}
    out = detect_lagged_links({"A": a, "B": b, "C": c}, lag=1, min_pairs=5, min_abs_r=0.0)
    rs = [abs(x["r"]) for x in out]
    assert rs == sorted(rs, reverse=True)
