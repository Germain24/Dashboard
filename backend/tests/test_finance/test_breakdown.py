"""Répartition du portefeuille (géo / secteur / défensif) affichée dans les logs."""

from app.services.finance.buffett.breakdown import (
    _ascii,
    _canon_sector,
    _fr_country,
    format_breakdown_lines,
    portfolio_breakdown,
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
    assert b["pays_contributions"]["France"] == {"B": 0.25}
    assert b["secteur_contributions"]["Souverain"] == {"A": 0.5}


def test_breakdown_unknown_lookthrough_goes_to_inconnu():
    w = {"X": 100}
    b = portfolio_breakdown(w, {}, {}, {}, {})
    assert abs(b["pays"]["Inconnu"] - 1.0) < 1e-9
    assert b["defensif"] == 0.0
    assert abs(b["agressif"] - 1.0) < 1e-9


def test_breakdown_unknown_lookthrough_stays_explicit_when_peers_known():
    w = {"A": 50, "X": 50}
    paysmap = {"A": {"France": 1.0}}
    b = portfolio_breakdown(w, {}, paysmap, {}, {})
    assert b["pays"] == {"France": 0.5, "Inconnu": 0.5}
    assert b["pays_contributions"]["Inconnu"] == {"X": 0.5}


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


def test_format_lines_show_each_ticker_contribution():
    b = portfolio_breakdown(
        {"CWI.PA": 12, "CSI": 8, "DDE": 3, "TECH": 77},
        {},
        {
            "CWI.PA": {"France": 0.5, "Germany": 0.5},
            "CSI": {"France": 1.0},
            "DDE": {"Germany": 1.0},
            "TECH": {"United States": 1.0},
        },
        {},
        {
            "CWI.PA": "Finance",
            "CSI": "Finance",
            "DDE": "Finance",
            "TECH": "Technologie",
        },
    )
    text = "\n".join(format_breakdown_lines(b))
    assert "Finance 23.0% (CWI.PA 12.0%; CSI 8.0%; DDE 3.0%)" in text
    assert "France 14.0% (CSI 8.0%; CWI.PA 6.0%)" in text
    assert "Allemagne 9.0% (CWI.PA 6.0%; DDE 3.0%)" in text


def test_breakdown_splits_world_etf_between_sectors():
    b = portfolio_breakdown(
        {"WORLD": 100.0},
        {},
        {"WORLD": {"USA": 0.7, "Japan": 0.3}},
        {"WORLD": "Actions"},
        {"WORLD": "Actions diversifiees"},
        {"WORLD": {"Technology": 0.30, "Financial Services": 0.20,
                    "Healthcare": 0.50}},
    )

    assert b["secteur"] == {
        "Technologie": 0.30,
        "Finance": 0.20,
        "Sante": 0.50,
    }
    assert b["secteur_contributions"]["Technologie"] == {"WORLD": 0.30}


def test_runtime_etf_exposures_are_used_by_breakdown_logger(monkeypatch, capsys):
    """Le logger doit reprendre les cartes calculées pendant le run Buffett."""
    from app.services.finance.buffett import breakdown

    monkeypatch.setattr(
        breakdown,
        "load_classification",
        lambda: ({"WORLD": "Actions"}, {"WORLD": "Actions diversifiees"}),
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.broker_availability.aggregate_weights",
        lambda alloc: {"WORLD": 100.0},
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.lookthrough.load_lookthrough",
        lambda: ({}, {}),
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.sector_lookthrough.load_sector_lookthrough",
        lambda: ({}, {}),
    )

    breakdown.log_portfolio_breakdown(
        [{"ticker": "WORLD", "poids_pct": 100.0}],
        country_exposures={"WORLD": {"United States": 0.7, "Japan": 0.3}},
        sector_exposures={"WORLD": {"Technology": 0.6, "Healthcare": 0.4}},
        defensive_exposures={"WORLD": 0.4},
    )

    output = capsys.readouterr().out
    assert "Inconnu 100.0%" not in output
    assert "Etats-Unis 70.0%" in output
    assert "Japon 30.0%" in output
    assert "Technologie 60.0%" in output
    assert "Sante 40.0%" in output
