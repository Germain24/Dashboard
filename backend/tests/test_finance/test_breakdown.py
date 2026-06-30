"""Répartition du portefeuille (géo / secteur / défensif) affichée dans les logs."""

from app.services.finance.buffett.breakdown import (
    portfolio_breakdown,
    format_breakdown_lines,
    _ascii,
    _canon_sector,
    _fr_country,
)


def test_sector_canon_merges_en_fr_duplicates():
    assert _canon_sector("Healthcare") == _canon_sector("Sante") == "Sante"
    assert _canon_sector("Technology") == _canon_sector("Technologie") == "Technologie"
    assert _canon_sector("Basic Materials") == "Materiaux"
    assert _canon_sector("Telecoms") == _canon_sector("Communication Services") == "Communication"
    assert _canon_sector("") == "Inconnu"


def test_country_fr_translation():
    assert _fr_country("United States") == "Etats-Unis"
    assert _fr_country("Germany") == "Allemagne"
    assert _fr_country("Other") == "Autres"
    assert _fr_country("France") == "France"


def test_breakdown_aggregates_and_normalizes():
    w = {"A": 50, "B": 50}                       # somme 100 -> normalisé à 1
    defmap = {"A": 1.0, "B": 0.0}                # A 100% défensif
    paysmap = {"A": {"United States": 1.0}, "B": {"France": 0.5, "Germany": 0.5}}
    classmap = {"A": "Obligations", "B": "Actions"}
    sectmap = {"A": "Souverain", "B": "Actions diversifiees"}
    b = portfolio_breakdown(w, defmap, paysmap, classmap, sectmap)
    assert abs(b["defensif"] - 0.5) < 1e-9
    assert abs(b["agressif"] - 0.5) < 1e-9
    assert abs(b["pays"]["United States"] - 0.5) < 1e-9
    assert abs(b["pays"]["France"] - 0.25) < 1e-9
    assert abs(b["classe"]["Actions"] - 0.5) < 1e-9
    assert abs(b["secteur"]["Souverain"] - 0.5) < 1e-9


def test_breakdown_unknown_lookthrough_goes_to_inconnu():
    w = {"X": 100}
    b = portfolio_breakdown(w, {}, {}, {}, {})
    assert abs(b["pays"]["Inconnu"] - 1.0) < 1e-9
    assert b["defensif"] == 0.0
    assert abs(b["agressif"] - 1.0) < 1e-9


def test_breakdown_ignores_zero_and_negative_weights():
    w = {"A": 100, "B": 0, "C": -5}
    b = portfolio_breakdown(w, {"A": 1.0}, {"A": {"USA": 1.0}}, {"A": "Actions"}, {"A": "Tech"})
    assert abs(b["pays"]["USA"] - 1.0) < 1e-9


def test_format_lines_are_ascii_only():
    b = portfolio_breakdown(
        {"A": 100}, {"A": 1.0}, {"A": {"United States": 1.0}},
        {"A": "Matières premières"}, {"A": "Énergie"},
    )
    lines = format_breakdown_lines(b)
    text = "\n".join(lines)
    assert text.encode("ascii")          # ne lève pas -> 100% ASCII (sûr pour cp1252)
    assert any("Defensif vs Agressif" in ln for ln in lines)


def test_ascii_strips_accents():
    assert _ascii("Énergie") == "Energie"
    assert _ascii("Matières premières") == "Matieres premieres"
