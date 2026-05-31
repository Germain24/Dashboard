import datetime as dt
from app.services.budget.imports import _parse_desjardins, _parse_generic


def test_parse_generic():
    row = ["2026-05-15", "METRO INC", "-45.32"]
    assert _parse_generic(row) == (dt.date(2026, 5, 15), -45.32, "METRO INC")


def test_parse_desjardins_debit():
    row = ["2026-05-15", "STARBUCKS", "6.75", "", "1200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == -6.75


def test_parse_desjardins_credit():
    row = ["2026-05-01", "SALAIRE", "", "3000.00", "4200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == 3000.0
