"""fetch_data / fetch_info_only : différer la reprise au runner.

Yahoo bloque transitoirement la session (401 "Invalid Crumb", "User is unable
to access this feature", reponse quoteSummary None -> "argument of type
'NoneType' is not iterable"). Le fetch unitaire tourne la session puis rend
immédiatement la main. Le runner pourra ainsi retenter le ticker en fin de
passe, sans bloquer un worker sur un deuxième appel Yahoo immédiat.
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


def test_fetch_data_defers_retry_after_rotating_session(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(1, calls))

    first = data_fetch.fetch_data("MLALE.PA")
    second = data_fetch.fetch_data("MLALE.PA")

    assert first is None
    assert second is not None and second["info"]["longName"] == "Ok Corp"
    assert calls == ["MLALE.PA", "MLALE.PA"]
    assert rotations == [True]


def test_fetch_data_makes_only_one_attempt_per_call(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(99, calls))

    assert data_fetch.fetch_data("MLALE.PA") is None
    assert calls == ["MLALE.PA"]
    assert rotations == [True]


def test_fetch_data_no_retry_when_first_attempt_succeeds(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(0, calls))

    data = data_fetch.fetch_data("AAPL")

    assert data is not None
    assert calls == ["AAPL"]
    assert rotations == []


def test_fetch_data_checks_info_before_financial_statements(monkeypatch, rotations):
    accessed: list[str] = []

    class RejectedTicker:
        @property
        def info(self):
            accessed.append("info")
            raise RuntimeError("HTTP Error 401: Invalid Crumb")

        @property
        def financials(self):
            accessed.append("financials")
            return pd.DataFrame()

    monkeypatch.setattr("yfinance.Ticker", lambda *args, **kwargs: RejectedTicker())

    assert data_fetch.fetch_data("REJECTED") is None
    assert accessed == ["info"]
    assert rotations == [True]


def test_fetch_info_only_defers_retry_after_rotating_session(monkeypatch, rotations):
    calls: list = []
    monkeypatch.setattr("yfinance.Ticker", _flaky_ticker_factory(1, calls))

    first = data_fetch.fetch_info_only("SPY")
    second = data_fetch.fetch_info_only("SPY")

    assert first is None
    assert second is not None and second["info"]["longName"] == "Ok Corp"
    assert calls == ["SPY", "SPY"]
    assert rotations == [True]


def test_runner_fetch_wrapper_never_sleeps_after_failure(monkeypatch):
    from app.services.finance.buffett import runner

    monkeypatch.setattr(runner, "fetch_data", lambda *args: None)
    monkeypatch.setattr(
        runner.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("sleep interdit")),
    )

    assert runner._fetch_with_retry("FAIL", object()) is None


def test_runner_retry_batch_runs_inline_in_order():
    from app.services.finance.buffett import runner

    seen = []

    def retry_one(ticker: str) -> bool:
        seen.append(ticker)
        return True

    assert runner._run_retry_batch(["ONE", "TWO"], retry_one, max_workers=10) == 2
    assert seen == ["ONE", "TWO"]


def test_fetch_data_429_opens_circuit_and_rotates_session_once(monkeypatch, rotations):
    class RateLimitedTicker:
        @property
        def info(self):
            raise RuntimeError(
                "Too Many Requests. Rate limited. Try after a while."
            )

    class FakeLimiter:
        def __init__(self):
            self.waits = 0
            self.rate_limits = 0

        def wait_for_remote_recovery(self):
            self.waits += 1

        def record_remote_rate_limit(self):
            self.rate_limits += 1
            return 60.0

        def record_remote_success(self):
            raise AssertionError("un 429 ne doit pas fermer le circuit")

    limiter = FakeLimiter()
    monkeypatch.setattr(
        "yfinance.Ticker",
        lambda *args, **kwargs: RateLimitedTicker(),
    )

    assert data_fetch.fetch_data("603158.HK", limiter) is None
    assert limiter.waits == 1
    assert limiter.rate_limits == 1
    assert rotations == [True]
