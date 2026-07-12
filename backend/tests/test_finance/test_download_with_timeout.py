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
        return _fake_raw(["AAPL"])

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
        return _fake_raw(["AAPL"])

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


# ── Retry PAR TICKER -- seuls les tickers encore sans donnees sont retentes ;
# un ticker qui reste sans donnees apres `retries` tentatives est ignore
# (absent du resultat) sans faire echouer les autres ──

def _fake_raw(tickers: list[str]) -> pd.DataFrame:
    """DataFrame MultiIndex (ticker, champ) comme un vrai yf.download(group_by='ticker').
    Liste vide -> DataFrame vide (aucun ticker n'a de donnees)."""
    if not tickers:
        return pd.DataFrame()
    return pd.concat(
        {t: pd.DataFrame({"Close": [100.0, 101.0]}) for t in tickers}, axis=1,
    )


def test_bulk_retry_per_ticker_returns_all_when_everything_succeeds(monkeypatch):
    calls = []

    def fake_download(**kwargs):
        chunk = list(kwargs["tickers"])
        calls.append(chunk)
        return _fake_raw(chunk)

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(["A", "B", "C"], retries=2, cooldown_s=0.01)

    assert calls == [["A", "B", "C"]]  # un seul appel, rien a retenter
    assert set(result.columns.get_level_values(0)) == {"A", "B", "C"}


def test_bulk_retry_per_ticker_only_retries_the_missing_ones(monkeypatch):
    """B echoue au 1er essai (absent du DataFrame retourne) ; le 2e essai ne
    redemande QUE B (A et C, deja obtenus, ne sont pas re-telecharges)."""
    calls = []

    def fake_download(**kwargs):
        chunk = list(kwargs["tickers"])
        calls.append(chunk)
        if chunk == ["A", "B", "C"]:
            return _fake_raw(["A", "C"])  # B manquant
        return _fake_raw(chunk)

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(["A", "B", "C"], retries=2, cooldown_s=0.01)

    assert calls == [["A", "B", "C"], ["B"]]
    assert set(result.columns.get_level_values(0)) == {"A", "B", "C"}


def test_bulk_retry_per_ticker_drops_ticker_still_missing_after_retries_but_keeps_others(monkeypatch):
    """B ne revient jamais, meme apres retries=2 (3 tentatives) -- il est ignore,
    mais A et C (obtenus des le 1er essai) sont bien dans le resultat final."""
    calls = []

    def fake_download(**kwargs):
        chunk = list(kwargs["tickers"])
        calls.append(chunk)
        if "B" in chunk:
            return _fake_raw([t for t in chunk if t != "B"])
        return _fake_raw(chunk)

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(["A", "B", "C"], retries=2, cooldown_s=0.01)

    assert calls == [["A", "B", "C"], ["B"], ["B"]]  # 1 essai initial + 2 retries pour B
    assert set(result.columns.get_level_values(0)) == {"A", "C"}  # B ignore, pas d'exception


def test_bulk_retry_per_ticker_returns_empty_when_nothing_ever_succeeds(monkeypatch):
    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: pd.DataFrame())
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(["A", "B"], retries=1, cooldown_s=0.01)
    assert result.empty
