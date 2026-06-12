"""Tests TDD pour la détection d'anomalies (#213)."""
import pytest
from tests.conftest import mem_session  # noqa: F401
from sqlmodel import select

from app.models.scheduler import Notification
from app.services.automatisations.anomalies import (
    detect_weight_anomaly,
    detect_sleep_anomaly,
    detect_expense_anomaly,
    run_anomaly_detection,
)


# ─── Fonctions pures ─────────────────────────────────────────────────────────

class TestDetectWeightAnomaly:
    def test_no_data_returns_none(self):
        assert detect_weight_anomaly([]) is None

    def test_not_enough_data_returns_none(self):
        # Besoin de ≥5 valeurs pour détecter
        assert detect_weight_anomaly([70.0, 70.1, 69.9]) is None

    def test_stable_weight_no_anomaly(self):
        weights = [70.0, 70.1, 69.9, 70.2, 70.0, 70.1, 70.0]
        assert detect_weight_anomaly(weights) is None

    def test_sudden_gain_detected(self):
        # Les 4 premières valeurs sont stables, les 3 dernières sautent de +2.5kg
        weights = [70.0, 70.1, 70.0, 70.2, 72.5, 72.8, 73.0]
        result = detect_weight_anomaly(weights)
        assert result is not None
        assert result["type"] == "weight_spike"
        assert result["delta"] > 0

    def test_sudden_loss_detected(self):
        weights = [70.0, 70.1, 70.0, 70.2, 67.5, 67.3, 67.0]
        result = detect_weight_anomaly(weights)
        assert result is not None
        assert result["type"] == "weight_spike"
        assert result["delta"] < 0


class TestDetectSleepAnomaly:
    def test_no_data_returns_none(self):
        assert detect_sleep_anomaly([]) is None

    def test_normal_sleep_no_anomaly(self):
        hours = [7.5, 8.0, 7.0, 7.5, 8.0, 7.5, 8.0]
        assert detect_sleep_anomaly(hours) is None

    def test_consistently_low_sleep_detected(self):
        # < 6h sur la plupart des jours
        hours = [5.0, 5.5, 5.0, 4.5, 5.0, 5.5, 5.0]
        result = detect_sleep_anomaly(hours)
        assert result is not None
        assert result["type"] == "sleep_deficit"
        assert result["moyenne"] < 6.0

    def test_single_bad_night_not_anomaly(self):
        hours = [7.5, 8.0, 7.0, 4.0, 8.0, 7.5, 8.0]
        assert detect_sleep_anomaly(hours) is None


class TestDetectExpenseAnomaly:
    def test_no_data_returns_none(self):
        assert detect_expense_anomaly([]) is None

    def test_normal_expenses_no_anomaly(self):
        # Dépenses hebdomadaires en valeur absolue
        totals = [500.0, 520.0, 490.0, 510.0, 505.0, 515.0]
        assert detect_expense_anomaly(totals) is None

    def test_spike_detected(self):
        totals = [500.0, 520.0, 490.0, 510.0, 505.0, 950.0]
        result = detect_expense_anomaly(totals)
        assert result is not None
        assert result["type"] == "expense_spike"
        assert result["valeur"] > result["moyenne"] * 1.5

    def test_not_enough_history(self):
        assert detect_expense_anomaly([500.0]) is None


# ─── Intégration DB ──────────────────────────────────────────────────────────

class TestRunAnomalyDetection:
    def test_creates_weight_notification(self, mem_session):
        import datetime as dt
        from app.models.sante import MesureSante
        # Crée des poids : 7 jours normaux puis spike
        today = dt.date.today()
        poids_values = [70.0, 70.1, 70.0, 70.2, 72.5, 72.8, 73.0]
        for i, poids in enumerate(poids_values):
            date = today - dt.timedelta(days=len(poids_values) - 1 - i)
            mem_session.add(MesureSante(date=date, poids=poids))
        mem_session.commit()
        run_anomaly_detection(mem_session, today=today)
        notifs = list(mem_session.exec(select(Notification)).all())
        assert any("poids" in n.message.lower() or "weight" in n.source for n in notifs)

    def test_no_anomaly_no_notification(self, mem_session):
        run_anomaly_detection(mem_session)
        notifs = list(mem_session.exec(select(Notification)).all())
        assert notifs == []
