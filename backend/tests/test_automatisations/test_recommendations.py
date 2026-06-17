"""Tests TDD — recommandations priorisées par impact (#227)."""

from __future__ import annotations

from app.services.automatisations.recommendations import (
    compute_recommendations,
    rank_recommendations,
)


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


# ─── Intégration (régressions) ───────────────────────────────────────────────

def test_compute_recommendations_includes_wellbeing_component(mem_session):
    """Régression : compute_recommendations doit construire le snapshot avant de
    calculer le bien-être (et non passer la Session telle quelle, ce qui levait
    une AttributeError silencieusement avalée → aucune composante de bien-être)."""
    recs = compute_recommendations(mem_session)
    # Au moins une reco provient d'une composante de bien-être (≠ insights/anomalie).
    assert any(r["module"] not in ("insights", "anomalie") for r in recs)


def test_compute_recommendations_does_not_persist_anomaly_notifications(mem_session):
    """Régression : un GET /recommendations ne doit pas écrire de Notification."""
    import datetime as dt
    from sqlmodel import select
    from app.models.sante import MesureSante
    from app.models.scheduler import Notification
    today = dt.date.today()
    for i, poids in enumerate([70.0, 70.1, 70.0, 70.2, 72.5, 72.8, 73.0]):
        mem_session.add(MesureSante(date=today - dt.timedelta(days=6 - i), poids=poids))
    mem_session.commit()
    compute_recommendations(mem_session)
    notifs = list(mem_session.exec(select(Notification)).all())
    assert all(not n.source.startswith("anomaly_") for n in notifs)
