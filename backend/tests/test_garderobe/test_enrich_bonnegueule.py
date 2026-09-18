"""Enrichissement des échelles — fonction pure + table."""
from __future__ import annotations

from scripts.enrich_bonnegueule import ENRICHMENT, insert_after_entry


def test_insert_apres_entree_ordre_preserve():
    assert insert_after_entry(
        ["Uniqlo", "Beams Plus", "Auralee"], ["Asphalte", "Loom"]
    ) == ["Uniqlo", "Asphalte", "Loom", "Beams Plus", "Auralee"]


def test_dedup_vs_existant_insensible_casse():
    # "asphalte" déjà présent (casse différente) -> non ré-inséré
    assert insert_after_entry(
        ["Uniqlo", "Asphalte", "Auralee"], ["asphalte", "Loom"]
    ) == ["Uniqlo", "Loom", "Asphalte", "Auralee"]


def test_dedup_entre_nouvelles():
    assert insert_after_entry(["Uniqlo"], ["Loom", "loom", "Asphalte"]) == [
        "Uniqlo",
        "Loom",
        "Asphalte",
    ]


def test_echelle_vide_et_un_element():
    assert insert_after_entry([], ["A", "B", "a"]) == ["A", "B"]
    assert insert_after_entry(["Uniqlo"], ["Asphalte"]) == ["Uniqlo", "Asphalte"]


def test_jamais_de_retrait_len_croit():
    old = ["Uniqlo", "Beams Plus"]
    new = insert_after_entry(old, ["Asphalte"])
    assert len(new) >= len(old)
    assert set(old).issubset(set(new))


def test_table_enrichment_coherente():
    assert "T-shirts" in ENRICHMENT
    assert ENRICHMENT["Chemises"] == ["Asphalte", "Officine Générale", "De Bonne Facture"]
    # toutes les valeurs sont des listes non vides de chaînes
    for t, brands in ENRICHMENT.items():
        assert isinstance(t, str) and t
        assert brands and all(isinstance(b, str) and b for b in brands)
