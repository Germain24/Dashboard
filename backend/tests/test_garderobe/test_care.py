"""Étiquettes d'entretien (#81)."""

from __future__ import annotations

from app.services.garderobe.care import care_label


def test_wool_is_delicate_hand_wash():
    c = care_label("Laine")
    assert c["delicat"] is True
    assert c["lavage"] == "Lavage main"
    assert "30°C" in c["resume"]


def test_leather_no_machine():
    c = care_label("Cuir")
    assert c["temperature"] == 0
    assert "Jamais de machine" in c["sechage"]
    assert "°C" not in c["resume"]  # pas de température affichée


def test_unknown_material_generic():
    c = care_label("Vinyle")
    assert c["lavage"] == "Machine"
    assert c["delicat"] is False
    assert c["matiere"] == "Vinyle"


def test_none_material():
    c = care_label(None)
    assert c["resume"]  # ne plante pas, renvoie une consigne générique
