"""Alerte de rééquilibrage : écart poids actuel/cible au-delà du seuil."""

from app.services.finance.rebalancing import _ecart_alerte, REBALANCE_ALERT_THRESHOLD_PCT


def test_ecart_within_threshold_no_alert():
    ecart, alerte = _ecart_alerte(12.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == 2.0
    assert alerte is False


def test_ecart_above_threshold_triggers_alert():
    ecart, alerte = _ecart_alerte(18.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == 8.0
    assert alerte is True


def test_underweight_above_threshold_triggers_alert():
    ecart, alerte = _ecart_alerte(2.0, 10.0, REBALANCE_ALERT_THRESHOLD_PCT)
    assert ecart == -8.0
    assert alerte is True
