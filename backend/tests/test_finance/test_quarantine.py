from pathlib import Path

import pytest

from app.services.finance.buffett.quarantine import classify_error, record_quarantine


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("HTTP 401 Invalid Crumb", "authentication"),
        ("argument of type 'NoneType' is not iterable", "authentication"),
        ("DNS name resolution failed", "network"),
        ("Read timed out", "timeout"),
        ("404 possibly delisted", "invalid_mapping"),
        ("empty financial statements", "empty_financials"),
    ],
)
def test_error_classification(message, expected):
    assert classify_error(message) == expected


def test_quarantine_counts_confirmations(tmp_path: Path):
    database = tmp_path / "cache.db"
    assert record_quarantine(
        "BAD.L", error_kind="invalid_mapping", error="404", database=database
    ) == 1
    assert record_quarantine(
        "BAD.L", error_kind="invalid_mapping", error="404", database=database
    ) == 2
