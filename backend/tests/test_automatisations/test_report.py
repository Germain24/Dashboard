"""Tests TDD — bilan mensuel « de vie » (#234)."""

from __future__ import annotations

import datetime as dt

from app.services.automatisations.report import build_monthly_report


def _snaps():
    base = dt.date(2026, 6, 1)
    return [
        (base, {"humeur": {"valeur": 6, "energie": 5}, "habitudes": {"pct": 70},
                "budget": {"depenses_total": 30}, "sante": {"poids": 80.0},
                "entrainement": {"nb_seances": 1, "tonnage_kg": 1000}}),
        (base + dt.timedelta(days=1), {"humeur": {"valeur": 8, "energie": 7}, "habitudes": {"pct": 90},
                "budget": {"depenses_total": 20}, "sante": {"poids": 79.0},
                "entrainement": {"nb_seances": 1, "tonnage_kg": 1200}}),
    ]


def test_period_and_coverage():
    r = build_monthly_report(_snaps(), year=2026, month=6)
    assert r["annee"] == 2026 and r["mois"] == 6
    assert r["jours_couverts"] == 2


def test_aggregates_means_and_sums():
    r = build_monthly_report(_snaps(), year=2026, month=6)
    m = r["metriques"]
    assert m["Humeur"] == 7.0          # moyenne (6,8)
    assert m["Dépenses"] == 50.0       # somme
    assert m["Séances"] == 2.0         # somme


def test_weight_delta_first_to_last():
    r = build_monthly_report(_snaps(), year=2026, month=6)
    assert r["poids"]["debut"] == 80.0
    assert r["poids"]["fin"] == 79.0
    assert r["poids"]["delta"] == -1.0


def test_empty_month():
    r = build_monthly_report([], year=2026, month=7)
    assert r["jours_couverts"] == 0
    assert r["metriques"] == {}
    assert r["poids"] is None
