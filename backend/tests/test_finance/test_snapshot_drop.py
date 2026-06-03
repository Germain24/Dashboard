"""Détection de chute de valeur du portefeuille (alerte snapshot)."""

from app.services.finance.snapshots import drop_alert_pct


def test_big_drop_triggers():
    assert drop_alert_pct(100.0, 92.0, seuil_pct=5.0) == 8.0


def test_small_drop_no_alert():
    assert drop_alert_pct(100.0, 97.0, seuil_pct=5.0) is None


def test_gain_no_alert():
    assert drop_alert_pct(100.0, 110.0, seuil_pct=5.0) is None


def test_invalid_prev():
    assert drop_alert_pct(0.0, 50.0) is None
    assert drop_alert_pct(None, 50.0) is None
