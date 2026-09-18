"""download_with_timeout : borne dure sur yf.download(), qui peut rester
bloqué bien au-delà du timeout par-requête de la session (#run resté
bloqué >2h en prod dans un unique appel bulk)."""

from __future__ import annotations

import time

import pandas as pd
import pytest

import app.services.finance.yf_session as yf_session_module
from app.services.finance.yf_session import (
    _wait_for_global_slot,
    _wrap_session_with_throttle,
    download_prices_bulk_with_retry,
    download_with_timeout,
)


def test_returns_the_download_result_when_fast_enough(monkeypatch):

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
    assert sleeps == []  # aucun cooldown arbitraire ; seul le quota HTTP attend


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
    assert sleeps == []


# ── Throttle global au niveau session (2000 requetes/minute Yahoo Finance) ──

class _FakeSession:
    def __init__(self):
        self.calls = []

    def request(self, method, *args, **kwargs):
        self.calls.append((method.lower(), args, kwargs))
        return f"{method.lower()}-result"

    def get(self, *args, **kwargs):
        return self.request("GET", *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.request("POST", *args, **kwargs)


@pytest.fixture(autouse=True)
def _reset_global_throttle():
    """Isole le quota global entre les tests."""
    yf_session_module.reset_sessions()
    yield
    yf_session_module.reset_sessions()


def test_wrap_session_with_throttle_returns_none_for_none():
    assert _wrap_session_with_throttle(None) is None


def test_wrap_session_with_throttle_preserves_call_and_return_value():
    session = _FakeSession()
    wrapped = _wrap_session_with_throttle(session)
    assert wrapped is session  # modifie en place
    result = wrapped.get("https://example.com", timeout=5)
    assert result == "get-result"
    assert session.calls == [("get", ("https://example.com",), {"timeout": 5})]


def test_wrap_session_counts_each_real_request_once(monkeypatch):
    reservations = []
    monkeypatch.setattr(
        yf_session_module,
        "_wait_for_global_slot",
        lambda: reservations.append("request"),
    )
    session = _wrap_session_with_throttle(_FakeSession())

    session.get()
    session.post()
    assert reservations == ["request", "request"]


def test_wait_for_global_slot_does_not_sleep_when_slot_already_free(monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    _wait_for_global_slot()
    assert sleeps == []  # quota 2 000/min encore libre


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


# ── Telechargement par LOTS -- un yf.download unique de milliers de tickers ne
# peut jamais finir sous le timeout dur de 180s des lors que le throttle global
# espace chaque requete (2000/h = 1,8s) : ~100 requetes max par appel. #bug
# rapporte : 2898 tickers eligibles -> 3 tentatives vides -> run termine sans
# allocation ("Cours indisponibles"). Le telechargement doit se faire par lots
# dont le timeout est proportionnel a la taille du lot. ──

def test_bulk_download_is_chunked(monkeypatch):
    calls = []

    def fake_download(**kwargs):
        chunk = list(kwargs["tickers"])
        calls.append(chunk)
        return _fake_raw(chunk)

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(
        ["A", "B", "C", "D", "E"], retries=1, cooldown_s=0.01, chunk_size=2,
    )

    assert calls == [["A", "B"], ["C", "D"], ["E"]]
    assert set(result.columns.get_level_values(0)) == {"A", "B", "C", "D", "E"}


def test_bulk_download_retries_only_missing_across_chunks(monkeypatch):
    """C (2e lot) echoue au 1er tour ; le 2e tour ne redemande QUE C."""
    calls = []

    def fake_download(**kwargs):
        chunk = list(kwargs["tickers"])
        calls.append(chunk)
        if calls.count(chunk) == 1 and chunk == ["C", "D"]:
            return _fake_raw(["D"])  # C manquant au 1er tour
        return _fake_raw(chunk)

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    result = download_prices_bulk_with_retry(
        ["A", "B", "C", "D"], retries=2, cooldown_s=0.01, chunk_size=2,
    )

    assert calls == [["A", "B"], ["C", "D"], ["C"]]
    assert set(result.columns.get_level_values(0)) == {"A", "B", "C", "D"}


def test_chunk_timeout_excludes_normal_hourly_quota_wait(monkeypatch):
    timeouts = []

    def fake_download(**kwargs):
        timeouts.append(kwargs.get("timeout_s"))
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    download_prices_bulk_with_retry(
        [f"T{i}" for i in range(50)], retries=0, cooldown_s=0.01, chunk_size=50,
    )

    assert len(timeouts) == 1
    assert timeouts[0] is not None
    assert timeouts[0] == 540.0


def test_bulk_download_reports_progress_per_chunk(monkeypatch):
    progress = []

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: _fake_raw(list(kw["tickers"])))
    monkeypatch.setattr("time.sleep", lambda s: None)

    download_prices_bulk_with_retry(
        ["A", "B", "C"], retries=0, cooldown_s=0.01, chunk_size=2,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    assert progress == [(2, 3), (3, 3)]


# ── Cache memoire quotidien des clotures (opt-in) : le bouton "Creer le
# portefeuille optimal" re-telechargeait les MEMES ~2900 cours 5 ans que le run
# venait de recuperer (~87 min sous throttle 2000/h), pour rien. ──

@pytest.fixture
def _isolated_price_cache(monkeypatch, tmp_path):
    """Cache disque isole (le vrai PRICE_CACHE_DIR persiste entre les runs)."""
    monkeypatch.setattr(yf_session_module, "PRICE_CACHE_DIR", tmp_path / "price_cache")


def test_bulk_cache_avoids_redownload_same_day(monkeypatch, _isolated_price_cache):
    yf_session_module.clear_bulk_cache()
    calls = []

    def fake_download(**kwargs):
        calls.append(list(kwargs["tickers"]))
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    r1 = download_prices_bulk_with_retry(
        ["A", "B"], retries=0, cooldown_s=0.01, period="5y", interval="1d",
        use_cache=True,
    )
    r2 = download_prices_bulk_with_retry(
        ["A", "B"], retries=0, cooldown_s=0.01, period="5y", interval="1d",
        use_cache=True,
    )

    assert calls == [["A", "B"]]  # 2e appel servi par le cache, zero download
    for r in (r1, r2):
        assert set(r.columns.get_level_values(0)) == {"A", "B"}
        assert list(r["A"]["Close"]) == [100.0, 101.0]


def test_bulk_cache_preserves_volume(monkeypatch, _isolated_price_cache):
    """La liquidite ETF doit rester calculable apres un cache hit."""
    yf_session_module.clear_bulk_cache()
    calls = []

    def fake_download(**kwargs):
        calls.append(list(kwargs["tickers"]))
        return pd.concat(
            {
                ticker: pd.DataFrame(
                    {"Close": [100.0, 101.0], "Volume": [1_000.0, 2_000.0]}
                )
                for ticker in kwargs["tickers"]
            },
            axis=1,
        )

    monkeypatch.setattr(
        "app.services.finance.yf_session.download_with_timeout",
        lambda **kw: fake_download(**kw),
    )

    download_prices_bulk_with_retry(
        ["ETF"], retries=0, period="5y", interval="1d", use_cache=True,
    )
    cached = download_prices_bulk_with_retry(
        ["ETF"], retries=0, period="5y", interval="1d", use_cache=True,
    )

    assert calls == [["ETF"]]
    assert list(cached["ETF"]["Volume"]) == [1_000.0, 2_000.0]


def test_bulk_download_honours_stop_between_chunks(monkeypatch):
    calls = []
    stopped = False

    def fake_download(**kwargs):
        nonlocal stopped
        calls.append(list(kwargs["tickers"]))
        stopped = True
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr(
        "app.services.finance.yf_session.download_with_timeout",
        lambda **kw: fake_download(**kw),
    )

    result = download_prices_bulk_with_retry(
        ["A", "B", "C"],
        retries=0,
        chunk_size=1,
        should_stop=lambda: stopped,
    )

    assert calls == [["A"]]
    assert set(result.columns.get_level_values(0)) == {"A"}


def test_bulk_cache_only_downloads_missing_tickers(monkeypatch, _isolated_price_cache):
    yf_session_module.clear_bulk_cache()
    calls = []

    def fake_download(**kwargs):
        calls.append(list(kwargs["tickers"]))
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    download_prices_bulk_with_retry(
        ["A", "B"], retries=0, cooldown_s=0.01, period="5y", interval="1d",
        use_cache=True,
    )
    r = download_prices_bulk_with_retry(
        ["A", "B", "C"], retries=0, cooldown_s=0.01, period="5y", interval="1d",
        use_cache=True,
    )

    assert calls == [["A", "B"], ["C"]]  # seul C manquait
    assert set(r.columns.get_level_values(0)) == {"A", "B", "C"}


def test_bulk_cache_disabled_by_default(monkeypatch, _isolated_price_cache):
    yf_session_module.clear_bulk_cache()
    calls = []

    def fake_download(**kwargs):
        calls.append(list(kwargs["tickers"]))
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    download_prices_bulk_with_retry(["A"], retries=0, cooldown_s=0.01,
                                    period="5y", interval="1d")
    download_prices_bulk_with_retry(["A"], retries=0, cooldown_s=0.01,
                                    period="5y", interval="1d")

    assert calls == [["A"], ["A"]]  # pas de cache implicite


def test_bulk_cache_survives_process_restart_via_disk(monkeypatch, _isolated_price_cache):
    """uvicorn --reload tue le cache memoire a chaque edition de code : le
    niveau disque doit servir les clotures du jour sans re-telechargement."""
    yf_session_module.clear_bulk_cache()
    calls = []

    def fake_download(**kwargs):
        calls.append(list(kwargs["tickers"]))
        return _fake_raw(list(kwargs["tickers"]))

    monkeypatch.setattr("app.services.finance.yf_session.download_with_timeout",
                         lambda **kw: fake_download(**kw))
    monkeypatch.setattr("time.sleep", lambda s: None)

    download_prices_bulk_with_retry(["A", "B"], retries=0, cooldown_s=0.01,
                                    period="5y", interval="1d", use_cache=True)
    yf_session_module.clear_bulk_cache()  # simule un redemarrage du process
    r = download_prices_bulk_with_retry(["A", "B"], retries=0, cooldown_s=0.01,
                                        period="5y", interval="1d", use_cache=True)

    assert calls == [["A", "B"]]  # 2e appel servi par le DISQUE
    assert set(r.columns.get_level_values(0)) == {"A", "B"}
    assert list(r["A"]["Close"]) == [100.0, 101.0]


def test_bulk_cache_hits_are_reported_as_progress(monkeypatch, _isolated_price_cache):
    yf_session_module.clear_bulk_cache()
    monkeypatch.setattr(
        "app.services.finance.yf_session.download_with_timeout",
        lambda **kwargs: _fake_raw(list(kwargs["tickers"])),
    )
    download_prices_bulk_with_retry(
        ["A", "B"], retries=0, period="5y", interval="1d", use_cache=True,
    )
    progress = []

    download_prices_bulk_with_retry(
        ["A", "B"], retries=0, period="5y", interval="1d", use_cache=True,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    assert progress == [(2, 2)]
