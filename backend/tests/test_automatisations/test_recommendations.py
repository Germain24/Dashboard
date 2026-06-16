"""Tests TDD — recommandations priorisées par impact (#227)."""

from __future__ import annotations

from app.services.automatisations.recommendations import rank_recommendations


def test_worst_wellbeing_component_becomes_high_impact_rec():
    recs = rank_recommendations(
        wellbeing_components={"habitudes": 80, "humeur": 30, "nutrition": 70, "entrainement": 60},
        vigilance=[], anomalies=[],
    )
    assert recs[0]["module"] == "humeur"        # la plus basse
    assert recs[0]["impact"] == 70              # 100 - 30


def test_vigilance_and_anomalies_become_recs():
    recs = rank_recommendations(
        wellbeing_components={},
        vigilance=["Dépenses ↑ 40%"],
        anomalies=["Poids en hausse anormale"],
    )
    modules = {r["module"] for r in recs}
    assert "insights" in modules and "anomalie" in modules
    assert any("Dépenses" in r["titre"] for r in recs)


def test_sorted_by_impact_desc():
    recs = rank_recommendations(
        wellbeing_components={"humeur": 90},   # impact 10 (faible)
        vigilance=["x"],                         # 55
        anomalies=["y"],                         # 70
    )
    impacts = [r["impact"] for r in recs]
    assert impacts == sorted(impacts, reverse=True)


def test_min_impact_filter():
    recs = rank_recommendations(
        wellbeing_components={"humeur": 95},   # impact 5
        vigilance=[], anomalies=[], min_impact=50,
    )
    assert recs == []


def test_each_rec_has_required_fields():
    recs = rank_recommendations(
        wellbeing_components={"nutrition": 40}, vigilance=[], anomalies=[],
    )
    r = recs[0]
    assert set(["titre", "module", "impact", "raison"]).issubset(r)
