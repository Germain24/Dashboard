"""fetch_data / fetch_info_only : retenter UNE fois avec une session neuve.

Yahoo bloque transitoirement la session (401 "Invalid Crumb", "User is unable
to access this feature", reponse quoteSummary None -> "argument of type
'NoneType' is not iterable"). Avant : le ticker etait abandonne au premier
echec, sans jamais changer de session/IP. Maintenant : rotate_session() puis
un 2e essai avant d'abandonner.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.finance.buffett import data_fetch


class _OkTicker:
    def __init__(self, symbol, session=None):
        self.financials = pd.DataFrame({"Revenue": [1.0]})
        self.balance_sheet = pd.DataFrame({"Assets": [2.0]})
        self.cashflow = pd.DataFrame({"FCF": [3.0]})
        self.info = {"longName": "Ok Corp"}


def _flaky_ticker_factory(fail_times: int, calls: list):
    """Ticker qui echoue `fail_times` fois (401 crumb simule) puis repond."""

    def factory(symbol, session=None):
        calls.append(symbol)
        if len(calls) <= fail_times:
            raise RuntimeError("HTTP Error 401: Invalid Crumb")
        return _OkTicker(symbol, session)

    return factory


@pytest.fixture
def rotations(monkeypatch):
    seen = []
    monkeypatch.setattr("app.services.finance.yf_session.rotate_session",
                        lambda: seen.append(True))
    return seen


def test_fetch_data_retries_once_with_fresh_session(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(1, calls))

    data = data_fetch.fetch_data("MLALE.PA")

    assert data is not None and data["info"]["longName"] == "Ok Corp"
    assert calls == ["MLALE.PA", "MLALE.PA"]  # 1 echec + 1 retry reussi
    assert rotations == [True]  # session tournee entre les deux


def test_fetch_data_gives_up_after_second_failure(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(99, calls))

    assert data_fetch.fetch_data("MLALE.PA") is None
    assert calls == ["MLALE.PA", "MLALE.PA"]  # jamais plus de 2 tentatives


def test_fetch_data_no_retry_when_first_attempt_succeeds(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(0, calls))

    data = data_fetch.fetch_data("AAPL")

    assert data is not None
    assert calls == ["AAPL"]
    assert rotations == []


def test_fetch_info_only_retries_once_with_fresh_session(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(1, calls))

    data = data_fetch.fetch_info_only("SPY")

    assert data is not None and data["info"]["longName"] == "Ok Corp"
    assert calls == ["SPY", "SPY"]
    assert rotations == [True]
