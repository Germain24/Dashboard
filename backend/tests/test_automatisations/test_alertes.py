"""Tests TDD — alertes de seuils configurables (#235)."""

from __future__ import annotations

from app.services.automatisations.alertes import evaluate_alerts


def test_greater_than_triggers():
    out = evaluate_alerts([{"metric": "Poids", "op": ">", "seuil": 80}], {"Poids": 82})
    assert len(out) == 1
    assert out[0]["valeur"] == 82
    assert "Poids" in out[0]["message"]


def test_less_than_triggers():
    out = evaluate_alerts([{"metric": "Habitudes %", "op": "<", "seuil": 50}], {"Habitudes %": 30})
    assert len(out) == 1


def test_not_triggered():
    assert evaluate_alerts([{"metric": "Poids", "op": ">", "seuil": 80}], {"Poids": 78}) == []


def test_disabled_alert_skipped():
    out = evaluate_alerts([{"metric": "Poids", "op": ">", "seuil": 80, "enabled": False}], {"Poids": 90})
    assert out == []


def test_missing_metric_skipped():
    assert evaluate_alerts([{"metric": "Poids", "op": ">", "seuil": 80}], {"Humeur": 5}) == []


def test_ge_le_operators():
    assert len(evaluate_alerts([{"metric": "X", "op": ">=", "seuil": 5}], {"X": 5})) == 1
    assert len(evaluate_alerts([{"metric": "X", "op": "<=", "seuil": 5}], {"X": 5})) == 1
