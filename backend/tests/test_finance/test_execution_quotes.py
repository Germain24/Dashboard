import numpy as np
import pandas as pd

from app.services.finance import yf_session
from app.services.finance.buffett import allocation
from app.services.finance.buffett.execution import prepare_execution_quotes


def test_secondary_quotes_are_batched_and_missing_price_is_not_primary(monkeypatch):
    requested = []
    def download(tickers, **kwargs):
        requested.append(tickers)
        return pd.DataFrame({"SECOND": [12.0]})
    monkeypatch.setattr(yf_session, "download_prices_bulk_with_retry", download)
    monkeypatch.setattr(allocation, "close_prices_from_download", lambda raw, _: raw)
    monkeypatch.setattr(allocation, "latest_prices_eur", lambda raw, _: {"SECOND": 12.0})
    frame = pd.DataFrame([
        {"Ticker Yahoo Finance": "A", "Execution Routes": {"B1": "SECOND", "B2": "MISSING"}},
        {"Ticker Yahoo Finance": "C", "Execution Routes": {"B1": "SECOND", "B2": "INACCESSIBLE"}},
    ])
    routes, prices = prepare_execution_quotes(
        ["A", "C"], ["B1", "B2"], np.array([[True, True], [True, False]]), frame, {"A": 100, "C": 200},
    )
    assert requested == [["MISSING", "SECOND"]]
    assert routes["A", "B1"] == "SECOND"
    assert prices["A", "B1"] == prices["C", "B1"] == 12.0
    assert prices["A", "B2"] == 0.0


def test_primary_quotes_do_not_download_and_nan_metadata_is_safe(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("No download needed")
    monkeypatch.setattr(yf_session, "download_prices_bulk_with_retry", unexpected)
    routes, prices = prepare_execution_quotes(
        ["A"], ["B"], [[True]], pd.DataFrame([
            {"Ticker Yahoo Finance": "A", "Execution Routes": float("nan")},
        ]), {"A": 42.0},
    )
    assert routes == {("A", "B"): "A"}
    assert prices == {("A", "B"): 42.0}
