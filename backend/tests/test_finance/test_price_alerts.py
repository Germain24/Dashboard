"""Tests alertes de marché (seuils de prix par ticker) — #265."""

import pytest

from app.services.finance.price_alerts import (
    add_alert,
    check_alerts,
    list_alerts,
    remove_alert,
    update_alert,
)


# ── Fonctions pures ──────────────────────────────────────────────────────────

def test_check_alerts_triggered_au_dessus():
    alerts = [{"id": 1, "ticker": "AAPL", "seuil": 200.0, "direction": "au_dessus", "actif": True}]
    result = check_alerts(alerts, {"AAPL": 210.0})
    assert len(result) == 1
    assert result[0]["prix_actuel"] == 210.0
    assert result[0]["declenchee"] is True


def test_check_alerts_not_triggered_au_dessus():
    alerts = [{"id": 1, "ticker": "AAPL", "seuil": 200.0, "direction": "au_dessus", "actif": True}]
    result = check_alerts(alerts, {"AAPL": 190.0})
    assert result[0]["declenchee"] is False
    assert result[0]["prix_actuel"] == 190.0


def test_check_alerts_triggered_en_dessous():
    alerts = [{"id": 2, "ticker": "MSFT", "seuil": 300.0, "direction": "en_dessous", "actif": True}]
    result = check_alerts(alerts, {"MSFT": 290.0})
    assert result[0]["declenchee"] is True


def test_check_alerts_not_triggered_en_dessous():
    alerts = [{"id": 2, "ticker": "MSFT", "seuil": 300.0, "direction": "en_dessous", "actif": True}]
    result = check_alerts(alerts, {"MSFT": 310.0})
    assert result[0]["declenchee"] is False


def test_check_alerts_no_price_available():
    alerts = [{"id": 3, "ticker": "XYZ", "seuil": 50.0, "direction": "au_dessus", "actif": True}]
    result = check_alerts(alerts, {})
    assert result[0]["prix_actuel"] is None
    assert result[0]["declenchee"] is False


def test_check_alerts_inactive_ignored():
    alerts = [{"id": 4, "ticker": "AAPL", "seuil": 100.0, "direction": "au_dessus", "actif": False}]
    result = check_alerts(alerts, {"AAPL": 999.0})
    assert result == []


def test_check_alerts_boundary_equal_triggers():
    alerts = [{"id": 5, "ticker": "AAPL", "seuil": 200.0, "direction": "au_dessus", "actif": True}]
    result = check_alerts(alerts, {"AAPL": 200.0})
    assert result[0]["declenchee"] is True


# ── Fonctions avec store JSON ────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path):
    return tmp_path / "finance_price_alerts.json"


def test_list_empty(store):
    assert list_alerts(path=store) == []


def test_add_alert(store):
    alert = add_alert("aapl", 200.0, "au_dessus", path=store)
    assert alert["ticker"] == "AAPL"
    assert alert["seuil"] == 200.0
    assert alert["direction"] == "au_dessus"
    assert alert["actif"] is True
    assert alert["id"] >= 1
    assert "cree_le" in alert


def test_add_alert_invalid_direction(store):
    with pytest.raises(ValueError):
        add_alert("AAPL", 200.0, "n_importe_quoi", path=store)


def test_list_persists(store):
    add_alert("AAPL", 200.0, "au_dessus", path=store)
    add_alert("MSFT", 300.0, "en_dessous", path=store)
    items = list_alerts(path=store)
    assert len(items) == 2
    assert {i["ticker"] for i in items} == {"AAPL", "MSFT"}


def test_update_alert(store):
    alert = add_alert("AAPL", 200.0, "au_dessus", path=store)
    updated = update_alert(alert["id"], {"seuil": 250.0}, path=store)
    assert updated is not None
    assert updated["seuil"] == 250.0
    assert updated["ticker"] == "AAPL"


def test_update_alert_toggle_actif(store):
    alert = add_alert("AAPL", 200.0, "au_dessus", path=store)
    updated = update_alert(alert["id"], {"actif": False}, path=store)
    assert updated["actif"] is False


def test_update_nonexistent(store):
    result = update_alert(999, {"seuil": 5}, path=store)
    assert result is None


def test_remove_alert(store):
    alert = add_alert("AAPL", 200.0, "au_dessus", path=store)
    assert remove_alert(alert["id"], path=store) is True
    assert list_alerts(path=store) == []


def test_remove_nonexistent(store):
    assert remove_alert(999, path=store) is False
