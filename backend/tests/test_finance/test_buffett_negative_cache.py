from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta

import pandas as pd
from sqlmodel import Session

from app.models.finance import BuffettRun
from app.services.finance.buffett.cache_manager import CacheManager
from app.services.finance.buffett.scoring_pure import SCORING_MODEL_VERSION


def _empty_response() -> dict:
    return {
        "income": pd.DataFrame(),
        "balance": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "info": {},
    }


def _configure_uncached_ticker(monkeypatch, runner, tmp_path) -> None:
    monkeypatch.setattr(runner.Config, "output_dir", lambda: tmp_path)
    monkeypatch.setattr(runner, "_check_is_etf", lambda *args, **kwargs: False)
    monkeypatch.setattr(runner, "_is_forced", lambda _ticker: False)


def test_empty_cache_is_permanent_and_survives_save(tmp_path):
    cache_path = tmp_path / "cache_status.json"
    cache = CacheManager(str(cache_path))
    cache.update_empty(
        "DEAD",
        {"Nom": "DEAD", "Secteur": "Inconnu", "Achat": False},
        "empty_financials_confirmed",
    )
    cache.save()

    raw = json.loads(cache_path.read_text())
    assert raw["DEAD"]["status"] == "empty_confirmed"
    assert raw["DEAD"]["score"] == 0.0
    assert raw["DEAD"]["reason"] == "empty_financials_confirmed"
    assert raw["DEAD"]["score_model_version"] == SCORING_MODEL_VERSION

    # Ni la TTL, ni l'absence de latest_year ne doivent invalider l'entrée.
    raw["DEAD"]["last_update"] = (datetime.now() - timedelta(days=500)).isoformat()
    cache_path.write_text(json.dumps(raw))
    reloaded = CacheManager(str(cache_path))
    assert reloaded.get_cached_result("DEAD") == (
        0.0,
        {
            "Nom": "DEAD",
            "Secteur": "Inconnu",
            "Achat": False,
            "Erreur": "empty_financials_confirmed",
        },
    )

    reloaded.invalidate("DEAD")
    assert reloaded.get_cached_result("DEAD") is None


def test_cache_checkpoint_is_thresholded_and_atomic(tmp_path):
    cache_path = tmp_path / "cache_status.json"
    cache = CacheManager(str(cache_path))
    cache.update_empty("ONE", {"Nom": "One"}, "empty")

    assert cache.checkpoint(every=2) is False
    assert not cache_path.exists()

    cache.update_empty("TWO", {"Nom": "Two"}, "empty")
    assert cache.checkpoint(every=2) is True
    assert set(json.loads(cache_path.read_text(encoding="utf-8"))) == {"ONE", "TWO"}
    assert list(tmp_path.glob(".cache_status.json-*.tmp")) == []


def test_empty_response_is_cached_and_next_run_does_not_fetch(monkeypatch, tmp_path):
    from app.services.finance.buffett import broker_availability, runner

    _configure_uncached_ticker(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(broker_availability, "load_broker_universe", lambda: set())
    fetches: list[str] = []
    monkeypatch.setattr(
        runner,
        "_fetch_with_retry",
        lambda ticker, limiter, stop=None: fetches.append(ticker) or _empty_response(),
    )
    cache = CacheManager(str(tmp_path / "cache.json"))

    first_results: dict = {}
    assert runner._analyze_one(
        "DEAD", first_results, cache, object(), set(), threading.Lock()
    )
    assert cache.is_empty_confirmed("DEAD")
    assert first_results["DEAD"][0] == 0.0

    second_results: dict = {}
    assert runner._analyze_one(
        "DEAD", second_results, cache, object(), set(), threading.Lock()
    )
    assert fetches == ["DEAD"]
    assert second_results["DEAD"][0] == 0.0


def test_broker_protected_empty_response_is_cached(monkeypatch, tmp_path):
    from app.services.finance.buffett import broker_availability, runner

    _configure_uncached_ticker(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(broker_availability, "load_broker_universe", lambda: {"SAFE"})
    monkeypatch.setattr(runner, "_fetch_with_retry", lambda *args: _empty_response())
    cache = CacheManager(str(tmp_path / "cache.json"))
    deleted: set[str] = set()

    assert runner._analyze_one(
        "SAFE", {}, cache, object(), deleted, threading.Lock()
    )
    assert cache.is_empty_confirmed("SAFE")
    assert deleted == set()


def test_transient_fetch_error_never_creates_negative_cache(monkeypatch, tmp_path):
    from app.services.finance.buffett import runner

    _configure_uncached_ticker(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(runner, "_fetch_with_retry", lambda *args: None)
    cache = CacheManager(str(tmp_path / "cache.json"))

    assert not runner._analyze_one(
        "RETRY", {}, cache, object(), set(), threading.Lock()
    )
    assert not cache.is_empty_confirmed("RETRY")
    assert "RETRY" not in cache.cache


def test_force_bypasses_negative_cache_and_fetches_yahoo(monkeypatch, tmp_path):
    from app.services.finance.buffett import broker_availability, runner

    _configure_uncached_ticker(monkeypatch, runner, tmp_path)
    monkeypatch.setattr(broker_availability, "load_broker_universe", lambda: set())
    fetches: list[str] = []
    monkeypatch.setattr(
        runner,
        "_fetch_with_retry",
        lambda ticker, limiter, stop=None: fetches.append(ticker) or _empty_response(),
    )
    cache = CacheManager(str(tmp_path / "cache.json"))
    cache.update_empty("DEAD", {"Nom": "DEAD"}, "empty_financials_confirmed")

    assert runner._analyze_one(
        "DEAD", {}, cache, object(), set(), threading.Lock(), force=True
    )
    assert fetches == ["DEAD"]


def test_zero_result_marks_ticker_done_for_resume(mem_engine):
    from app.services.finance.buffett.reporting import get_done_tickers, upsert_result

    with Session(mem_engine) as session:
        run = BuffettRun(run_date=datetime.now().date())
        session.add(run)
        session.commit()
        session.refresh(run)
        upsert_result(
            session,
            run.id,
            "DEAD",
            0.0,
            {"Nom": "DEAD", "Achat": False, "Erreur": "empty_financials_confirmed"},
        )
        assert "DEAD" in get_done_tickers(session, run.id)


def test_api_forwards_force_to_single_ticker_analysis(monkeypatch):
    from app.api.finance import buffett
    from app.services.finance.buffett import runner

    calls: list[tuple[str, bool]] = []

    def fake_analyze(ticker: str, cache=None, force: bool = False):
        calls.append((ticker, force))
        return 0.0, {"Nom": ticker, "Achat": False}

    monkeypatch.setattr(runner, "analyze_single_ticker", fake_analyze)
    response = asyncio.run(buffett.buffett_analyze_ticker("dead", force=True))

    assert calls == [("DEAD", True)]
    assert response["score"] == 0.0


def test_single_ticker_force_invalidates_negative_entry(monkeypatch):
    from app.services.finance import yf_session
    from app.services.finance.buffett import runner

    class FakeCache:
        invalidated: list[str] = []

        def is_empty_confirmed(self, ticker: str) -> bool:
            return True

        def invalidate(self, ticker: str) -> None:
            self.invalidated.append(ticker)

        def save(self) -> None:
            pass

    seen_force: list[bool] = []

    def fake_analyze(ticker, results, *args, force=False, **kwargs):
        seen_force.append(force)
        results[ticker] = (12.0, {"Nom": ticker})
        return True

    monkeypatch.setattr(runner.Config, "load_params", lambda: None)
    monkeypatch.setattr(runner.Config, "ensure_dirs", lambda: None)
    monkeypatch.setattr(yf_session, "http_rate_limiter", lambda: object())
    monkeypatch.setattr(runner, "_analyze_one", fake_analyze)
    cache = FakeCache()

    assert runner.analyze_single_ticker("DEAD", cache=cache, force=True) == (
        12.0,
        {"Nom": "DEAD"},
    )
    assert cache.invalidated == ["DEAD"]
    assert seen_force == [True]
