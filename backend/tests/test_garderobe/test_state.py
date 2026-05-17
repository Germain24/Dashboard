"""Tests des helpers d'état d'un vêtement."""

from app.services.garderobe.state import (
    disponible,
    is_worn_out,
    needs_wash,
    ports_avant_lavage,
    proprete_pct,
    vie_pct,
)


def _item(portes=0, etat_propre=10, usure_max=100):
    return {
        "id": "x", "nom": "x", "categorie": "Haut",
        "portes": portes, "etat_propre": etat_propre, "usure_max": usure_max,
    }


def test_proprete_pct_full_when_just_washed():
    assert proprete_pct(_item(portes=0)) == 100


def test_proprete_pct_drops_with_wear():
    # etat_propre=10, portes=5 → reste 5 ports avant lavage → 50%
    assert proprete_pct(_item(portes=5, etat_propre=10)) == 50


def test_needs_wash_triggers_at_threshold():
    assert needs_wash(_item(portes=10, etat_propre=10)) is True
    assert needs_wash(_item(portes=9, etat_propre=10)) is False
    # 0 ports = pas besoin de lavage (item neuf)
    assert needs_wash(_item(portes=0, etat_propre=10)) is False


def test_vie_pct_decreases_with_wear():
    assert vie_pct(_item(portes=0, usure_max=100)) == 100
    assert vie_pct(_item(portes=50, usure_max=100)) == 50
    assert vie_pct(_item(portes=100, usure_max=100)) == 0


def test_is_worn_out_only_when_zero_vie():
    assert is_worn_out(_item(portes=99, usure_max=100)) is False
    assert is_worn_out(_item(portes=100, usure_max=100)) is True


def test_ports_avant_lavage():
    assert ports_avant_lavage(_item(portes=0, etat_propre=10)) == 10
    assert ports_avant_lavage(_item(portes=3, etat_propre=10)) == 7
    # Quand besoin de lavage, plus de ports possibles
    assert ports_avant_lavage(_item(portes=10, etat_propre=10)) == 0


def test_disponible_combines_wash_and_worn_out():
    # Pas besoin de lavage, pas HS
    assert disponible(_item(portes=5, etat_propre=10, usure_max=100)) is True
    # À laver
    assert disponible(_item(portes=10, etat_propre=10, usure_max=100)) is False
    # HS
    assert disponible(_item(portes=100, etat_propre=200, usure_max=100)) is False
