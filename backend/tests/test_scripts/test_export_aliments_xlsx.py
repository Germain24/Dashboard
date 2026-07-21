"""Export du catalogue nutrition en Excel (2 feuilles) — parties pures."""

from __future__ import annotations

from scripts.export_aliments_xlsx import _cell_value, _retired_columns


def test_cell_value_parses_dot_decimal():
    assert _cell_value("0.799") == 0.799


def test_cell_value_parses_comma_decimal():
    assert _cell_value("0,799") == 0.799


def test_cell_value_empty_is_none():
    assert _cell_value("") is None


def test_cell_value_non_numeric_stays_text():
    assert _cell_value("ETF") == "ETF"


def test_retired_columns_keeps_only_marked_suffixes():
    rows = [
        ["Nutriments", "Oeufs", "Whey protein (Inshape)", "Saumon (ON)", "Truite"],
        ["Prix", "1.2", "5.87", "9.47", "3.0"],
    ]
    out = _retired_columns(rows)
    assert out[0] == ["Nutriments", "Whey protein (Inshape)", "Saumon (ON)"]
    assert out[1] == ["Prix", "5.87", "9.47"]


def test_retired_columns_empty_backup_returns_empty():
    assert _retired_columns([]) == []


def test_retired_columns_none_marked_keeps_only_label_column():
    rows = [["Nutriments", "Oeufs", "Truite"], ["Prix", "1.2", "3.0"]]
    out = _retired_columns(rows)
    assert out[0] == ["Nutriments"]
    assert out[1] == ["Prix"]
