import pandas as pd

from app.services.finance.catalog.validation import validate_yahoo_symbols


def test_yahoo_validation_uses_batches_and_marks_missing():
    calls = []

    def downloader(symbols, **kwargs):
        calls.append(list(symbols))
        columns = pd.MultiIndex.from_product([symbols[:-1], ["Close"]])
        return pd.DataFrame([[10.0] * len(columns)], columns=columns)

    result = validate_yahoo_symbols(
        ["A", "B", "C", "D", "E"], batch_size=3, downloader=downloader
    )
    assert calls == [["A", "B", "C"], ["D", "E"]]
    assert result == {"A": True, "B": True, "C": False, "D": True, "E": False}
