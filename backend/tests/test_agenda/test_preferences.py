"""Préférences de planification (moment par activité)."""

from __future__ import annotations

from app.services.agenda import preferences as prefs


def test_roundtrip_and_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "_path", lambda: tmp_path / "agenda_preferences.json")
    assert prefs.get_preferences() == {"moments": {}}

    prefs.set_preferences({"moments": {"sport": "soir", "etudes": "matin", "x": "soir", "cuisine": "INVALIDE"}})
    out = prefs.get_preferences()
    assert out["moments"] == {"sport": "soir", "etudes": "matin"}   # x et valeur invalide rejetés


def test_remove_preference(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "_path", lambda: tmp_path / "agenda_preferences.json")
    prefs.set_preferences({"moments": {"sport": "soir"}})
    prefs.set_preferences({"moments": {"sport": ""}})        # vide → retire
    assert prefs.get_preferences()["moments"] == {}
