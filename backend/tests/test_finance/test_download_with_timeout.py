"""download_with_timeout : borne dure sur yf.download(), qui peut rester
bloqué bien au-delà du timeout par-requête de la session (#run resté
bloqué >2h en prod dans un unique appel bulk)."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from app.services.finance.yf_session import (
    download_with_timeout, download_prices_bulk_with_retry,
    _wrap_session_with_throttle, _wait_for_global_slot,
)
import app.services.finance.yf_session as yf_session_module


def test_returns_the_download_result_when_fast_enough(monkeypatch):
    import app.services.finance.yf_session as yfs

    def fake_download(**kwargs):
        return pd.DataFrame({"Close": [1.0, 2.0]})

    monkeypatch.setattr("yfinance.download", fake_download)
    result = download_with_timeout(timeout_s=5.0, tickers="AAPL")
    assert list(result["Close"]) == [1.0, 2.0]


def test_returns_empty_dataframe_when_call_exceeds_timeout(monkeypatch):
    def slow_download(**kwargs):
        time.sleep(2.0)
        return pd.DataFrame({"Close": [1.0]})

    monkeypatch.setattr("yfinance.download", slow_download)
    result = download_with_timeout(timeout_s=0.2, tickers="AAPL")
    assert result.empty


def test_does_not_block_caller_waiting_for_the_hung_thread(monkeypatch):
    """La fonction doit revenir dans un temps borné par `timeout_s`, même si
    le thread sous-jacent ne se termine jamais (simulé par un sleep bien plus
    long que le timeout) -- pas de blocage au shutdown de l'executor."""
    def never_returns(**kwargs):
        time.sleep(10.0)
        return pd.DataFrame()

    monkeypatch.setattr("yfinance.download", never_returns)
    start = time.time()
    result = download_with_timeout(timeout_s=0.3, tickers="AAPL")
    elapsed = time.time() - start
    assert result.empty
    assert elapsed < 2.0  # largement sous les 10s du thread fantôme


# ── download_prices_bulk_with_retry ──────────────────────────────────────────

def test_bulk_retry_returns_first_result_without_sleeping_when_non_empty(monkeypatch):
    calls = {"download": 0, "sleep": 0}

    def fake_download(**kwargs):
        calls["download"] += 1
        return pd.DataFrame({"Close": [1.0]})

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: calls.__setitem__("sleep", calls["sleep"] + 1))

    result = download_prices_bulk_with_retry(["AAPL"], retries=2, cooldown_s=0.01)
    assert not result.empty
    assert calls["download"] == 1
    assert calls["sleep"] == 0


def test_bulk_retry_retries_once_then_succeeds(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def fake_download(**kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return pd.DataFrame()
        return pd.DataFrame({"Close": [1.0]})

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    result = download_prices_bulk_with_retry(["AAPL"], retries=2, cooldown_s=5.0)
    assert not result.empty
    assert attempts["n"] == 2
    assert sleeps == [5.0]  # une seule pause, avant la 2e tentative


def test_bulk_retry_gives_up_after_exhausting_retries(monkeypatch):
    attempts = {"n": 0}
    sleeps = []

    def fake_download(**kwargs):
        attempts["n"] += 1
        return pd.DataFrame()

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    result = download_prices_bulk_with_retry(["AAPL"], retries=2, cooldown_s=1.0)
    assert result.empty
    assert attempts["n"] == 3  # 1 essai initial + 2 retries
    assert sleeps == [1.0, 1.0]


# ── Throttle global au niveau session (2000 requetes/minute Yahoo Finance) ──

class _FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return "get-result"

    def post(self, *args, **kwargs):
        self.calls.append(("post", args, kwargs))
        return "post-result"


@pytest.fixture(autouse=True)
def _reset_global_throttle():
    """Isole le crenau global entre les tests (etat partage module-level)."""
    yf_session_module._global_next_slot = 0.0
    yield
    yf_session_module._global_next_slot = 0.0


def test_wrap_session_with_throttle_returns_none_for_none():
    assert _wrap_session_with_throttle(None) is None


def test_wrap_session_with_throttle_preserves_call_and_return_value():
    session = _FakeSession()
    wrapped = _wrap_session_with_throttle(session)
    assert wrapped is session  # modifie en place
    result = wrapped.get("https://example.com", timeout=5)
    assert result == "get-result"
    assert session.calls == [("get", ("https://example.com",), {"timeout": 5})]


def test_wrap_session_with_throttle_spaces_out_consecutive_calls():
    """N'utilise PAS de time.sleep mocke : GLOBAL_MIN_INTERVAL_S (0.03s) est
    assez petit pour dormir reellement dans un test sans le ralentir de facon
    perceptible, et un sleep mocke casserait le modele de "prochain crenau"
    (la file virtuelle avancerait plus vite que le temps reel, faussant les
    durees attendues entre appels)."""
    session = _wrap_session_with_throttle(_FakeSession())

    start = time.time()
    session.get()
    session.get()
    session.post()
    elapsed = time.time() - start

    # 3 appels -> 2 intervalles a respecter au minimum (le 1er ne dort jamais).
    assert elapsed >= 2 * yf_session_module.GLOBAL_MIN_INTERVAL_S


def test_wait_for_global_slot_does_not_sleep_when_slot_already_free(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    _wait_for_global_slot()
    assert sleeps == []  # premier appel, aucun crenau precedent -> pas d'attente
