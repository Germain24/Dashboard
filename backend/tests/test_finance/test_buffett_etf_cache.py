"""Tests du correctif cache ETF permanent (bug perf mensuel Buffett).

Contexte : un ETF n'a pas de fondamentaux qui changent (Score=200 fige par
convention) -> son cache ne devrait JAMAIS expirer sur la TTL de 60 jours,
contrairement a une action (dont les fondamentaux bougent). Trois bugs
corriges ici :

1. CacheManager.get_cached_result() verifiait la TTL de 60 jours AVANT
   l'exemption ETF (score>=200) -> un ETF cache depuis >60 jours etait
   force-refreshe comme une action normale.
2. _analyze_one() ne court-circuitait pas les ETF connus (_check_is_etf)
   sur cache-froid -> passait par le telechargement complet (4 appels
   yfinance) juste pour renvoyer Score=200 fige.
3. save_local_data() ne persistait un fichier local que si income/balance/
   cashflow etait non-vide -- or un vrai ETF yfinance a ces 3 DataFrames
   VIDES (ce n'est pas une entreprise), seul `.info` est renseigne -> le
   court-circuit "fichier local" ne pouvait jamais s'activer pour un ETF.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta

import pandas as pd
import pytest


# ── Fix #1 : TTL 60 jours ne doit plus s'appliquer aux ETF (score>=200) ─────


def _write_cache(tmp_path, entries: dict) -> "object":
    from app.services.finance.buffett.cache_manager import CacheManager

    cache_file = tmp_path / "cache_status.json"
    cache_file.write_text(json.dumps(entries))
    return CacheManager(str(cache_file))


def test_etf_cache_hit_survives_past_60_day_ttl(tmp_path):
    """Un ETF (score=200) cache il y a 90 jours doit quand meme etre retourne
    par get_cached_result -- avant le fix, l'age >= 60 jours court-circuitait
    AVANT que l'exemption ETF (score >= 200) ne soit meme regardee."""
    old_date = (datetime.now() - timedelta(days=90)).isoformat()
    cm = _write_cache(tmp_path, {
        "CW8.PA": {
            "last_update": old_date, "latest_year": 2020, "score": 200.0,
            "metrics": {"Nom": "Amundi MSCI World"}, "status": "success",
        },
    })
    result = cm.get_cached_result("CW8.PA")
    assert result is not None
    score, metrics = result
    assert score == 200.0
    assert metrics["Nom"] == "Amundi MSCI World"


def test_non_etf_stock_still_respects_60_day_ttl(tmp_path):
    """Regression guard : une action normale (score < 200) cachee il y a 90
    jours doit toujours expirer -- seul le cas ETF doit devenir permanent."""
    old_date = (datetime.now() - timedelta(days=90)).isoformat()
    cm = _write_cache(tmp_path, {
        "AAPL": {
            "last_update": old_date, "latest_year": 2020, "score": 85.0,
            "metrics": {"Nom": "Apple Inc."}, "status": "success",
        },
    })
    assert cm.get_cached_result("AAPL") is None


def test_etf_cache_hit_within_60_days_still_works(tmp_path):
    """Non-regression : un ETF cache recemment (< 60 jours) continue de
    retourner un hit (comportement deja correct avant le fix)."""
    recent = (datetime.now() - timedelta(days=5)).isoformat()
    cm = _write_cache(tmp_path, {
        "IWDA.L": {
            "last_update": recent, "latest_year": 2024, "score": 200.0,
            "metrics": {"Nom": "iShares Core MSCI World"}, "status": "success",
        },
    })
    result = cm.get_cached_result("IWDA.L")
    assert result is not None
    assert result[0] == 200.0


def test_non_etf_stock_within_age_window_still_works(tmp_path):
    """Non-regression : une action normale, fraiche et dans la fenetre d'age
    financier, continue de retourner un hit."""
    recent = datetime.now().isoformat()
    this_year = datetime.now().year - 1  # age_fin == 1 (dans [MIN_AGE_YEARS, MAX_AGE_YEARS])
    cm = _write_cache(tmp_path, {
        "AAPL": {
            "last_update": recent, "latest_year": this_year, "score": 85.0,
            "metrics": {"Nom": "Apple Inc."}, "status": "success",
        },
    })
    result = cm.get_cached_result("AAPL")
    assert result is not None
    assert result[0] == 85.0


# ── Interaction avec purge_misclassified_etf_cache (reclassification) ──────


def test_purge_still_invalidates_reclassified_etf_after_ttl_reorder(tmp_path):
    """Un titre fige Score=200 (ex-ETF) qui n'est PLUS dans l'ensemble ETF
    autoritaire (ToutBroker) doit rester purge du cache par
    purge_misclassified_etf_cache, meme apres le reordonnancement de la TTL
    dans get_cached_result -- la purge est un mecanisme independant qui tourne
    AVANT get_cached_result a chaque run (cf. runner.run_buffett_analysis)."""
    from app.services.finance.buffett.cache_manager import (
        CacheManager,
        purge_misclassified_etf_cache,
    )

    cache_file = tmp_path / "cache_status.json"
    outdir = tmp_path / "fin"
    outdir.mkdir()
    old_date = (datetime.now() - timedelta(days=90)).isoformat()
    cache_file.write_text(json.dumps({
        "BA.TO": {
            "last_update": old_date, "latest_year": 2020, "score": 200.0,
            "metrics": {"Nom": "The Boeing Company"}, "status": "success",
        },
    }))
    (outdir / "BA.TO.xlsx").write_text("x")

    # BA.TO n'est plus dans l'ensemble ETF (reclassifie en action) -> purge.
    res = purge_misclassified_etf_cache(str(cache_file), str(outdir), etf_tickers=set())
    assert res["removed"] == 1
    assert not (outdir / "BA.TO.xlsx").exists()

    # Apres purge, plus aucun cache hit pour ce ticker (force reanalyse).
    cm = CacheManager(str(cache_file))
    assert cm.get_cached_result("BA.TO") is None


def test_purge_does_not_remove_still_classified_etf(tmp_path):
    """Non-regression : un ETF toujours classe ETF (present dans
    etf_tickers) n'est pas purge -- meme si son cache a plus de 60 jours --
    et reste donc disponible via get_cached_result apres le fix #1."""
    from app.services.finance.buffett.cache_manager import (
        CacheManager,
        purge_misclassified_etf_cache,
    )

    cache_file = tmp_path / "cache_status.json"
    outdir = tmp_path / "fin"
    outdir.mkdir()
    old_date = (datetime.now() - timedelta(days=90)).isoformat()
    cache_file.write_text(json.dumps({
        "CW8.PA": {
            "last_update": old_date, "latest_year": 2020, "score": 200.0,
            "metrics": {"Nom": "Amundi MSCI World"}, "status": "success",
        },
    }))

    res = purge_misclassified_etf_cache(str(cache_file), str(outdir), etf_tickers={"CW8.PA"})
    assert res["removed"] == 0

    cm = CacheManager(str(cache_file))
    result = cm.get_cached_result("CW8.PA")
    assert result is not None
    assert result[0] == 200.0


# ── Fix #2 : _analyze_one doit court-circuiter un ETF sur cache-froid ──────


class _FakeCacheMiss:
    """Simule un cache-froid (aucune entree) -- force le passage dans
    _analyze_one au-dela de l'etape 0."""

    def get_cached_result(self, ticker):
        return None

    def get_status(self, ticker, file_path):
        return "download"

    def update(self, *args, **kwargs):
        pass


def test_analyze_one_etf_short_circuits_without_expensive_fetch(monkeypatch, tmp_path):
    """Un ETF connu (_check_is_etf True), meme sans aucune entree de cache ni
    fichier local, doit renvoyer Score=200 SANS jamais appeler
    _fetch_with_retry (le telechargement complet 4-appels yfinance). Un fetch
    allege ".info seul" (_fetch_info_with_retry) est tolere / mocke ici."""
    from app.services.finance.buffett import runner

    monkeypatch.setattr(runner, "_check_is_etf", lambda t, data=None: t.upper() == "CW8.PA")
    monkeypatch.setattr(runner, "load_local_data", lambda t: None)
    monkeypatch.setattr(runner.Config, "FOLDER_PATH", str(tmp_path))

    expensive_fetch_called = {"n": 0}

    def _fail_if_called(t, rl, sf=None):
        expensive_fetch_called["n"] += 1
        raise AssertionError("_fetch_with_retry ne doit pas etre appele pour un ETF connu")

    monkeypatch.setattr(runner, "_fetch_with_retry", _fail_if_called)
    monkeypatch.setattr(
        runner, "_fetch_info_with_retry",
        lambda t, rl, sf=None: {"info": {"longName": "Amundi MSCI World", "currentPrice": 42.0}},
    )

    results: dict = {}
    deleted: set = set()
    ok = runner._analyze_one(
        "CW8.PA", results, _FakeCacheMiss(), object(), deleted, threading.Lock()
    )

    assert ok is True
    assert expensive_fetch_called["n"] == 0
    assert results["CW8.PA"][0] == 200.0
    assert results["CW8.PA"][1]["Secteur"] == "ETF"
    assert results["CW8.PA"][1]["Nom"] == "Amundi MSCI World"


def test_analyze_one_etf_info_fetch_uses_lightweight_path_not_full_fetch(monkeypatch, tmp_path):
    """Verifie explicitement que le chemin ETF cache-froid appelle bien
    _fetch_info_with_retry (le fetch allege), et jamais _fetch_with_retry
    (le fetch complet 4-appels) -- couvre la regression inverse ou quelqu'un
    reviendrait au fetch complet par erreur."""
    from app.services.finance.buffett import runner

    monkeypatch.setattr(runner, "_check_is_etf", lambda t, data=None: True)
    monkeypatch.setattr(runner, "load_local_data", lambda t: None)
    monkeypatch.setattr(runner.Config, "FOLDER_PATH", str(tmp_path))
    monkeypatch.setattr(runner, "_fetch_with_retry",
                         lambda t, rl, sf=None: (_ for _ in ()).throw(
                             AssertionError("full fetch ne doit pas etre appele")))

    info_calls = {"n": 0}

    def _fake_info_fetch(t, rl, sf=None):
        info_calls["n"] += 1
        return {"info": {}}

    monkeypatch.setattr(runner, "_fetch_info_with_retry", _fake_info_fetch)

    results: dict = {}
    deleted: set = set()
    ok = runner._analyze_one(
        "CW8.PA", results, _FakeCacheMiss(), object(), deleted, threading.Lock()
    )
    assert ok is True
    assert info_calls["n"] == 1


def test_analyze_one_non_etf_still_uses_fetch_path(monkeypatch, tmp_path):
    """Non-regression : un ticker non-ETF sur cache-froid continue de passer
    par le telechargement (le court-circuit ne doit s'appliquer qu'aux ETF)."""
    from app.services.finance.buffett import runner

    monkeypatch.setattr(runner, "_check_is_etf", lambda t, data=None: False)
    monkeypatch.setattr(runner, "load_local_data", lambda t: None)
    monkeypatch.setattr(runner.Config, "FOLDER_PATH", str(tmp_path))

    fetch_called = {"n": 0}
    income = pd.DataFrame({"Total Revenue": [1.0]}, index=pd.to_datetime(["2024-01-01"]))

    def _fake_fetch(t, rl, sf=None):
        fetch_called["n"] += 1
        return {"income": income, "balance": income, "cashflow": income,
                "info": {"quoteType": "EQUITY", "longName": "Some Corp"}}

    monkeypatch.setattr(runner, "_fetch_with_retry", _fake_fetch)
    monkeypatch.setattr(runner, "analyze_financials", lambda t, d: (77.0, {"Nom": t, "Achat": True}))
    monkeypatch.setattr(runner, "save_local_data", lambda t, d: True)

    results: dict = {}
    deleted: set = set()
    ok = runner._analyze_one(
        "AAPL", results, _FakeCacheMiss(), object(), deleted, threading.Lock()
    )

    assert ok is True
    assert fetch_called["n"] == 1
    assert results["AAPL"][0] == 77.0


# ── Fix #3 : save_local_data doit persister quand seul .info est non-vide ──


def test_save_local_data_persists_when_only_info_nonempty(monkeypatch, tmp_path):
    """Un vrai ETF yfinance renvoie income/balance/cashflow VIDES (ce n'est
    pas une entreprise) -- seul `.info` est peuple. save_local_data doit quand
    meme persister un fichier local (pour permettre le court-circuit 'fichier
    local' en amont du fetch complet)."""
    from app.services.finance.buffett import data_fetch

    monkeypatch.setattr(data_fetch.Config, "FOLDER_PATH", str(tmp_path))

    data = {
        "income": pd.DataFrame(),
        "balance": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "info": {"longName": "Amundi MSCI World", "quoteType": "ETF", "currentPrice": 42.0},
    }
    saved = data_fetch.save_local_data("CW8.PA", data)
    assert saved is True
    assert (tmp_path / "CW8.PA.xlsx").exists()


def test_save_and_load_local_data_roundtrip_for_info_only_etf(monkeypatch, tmp_path):
    """Un fichier local persiste avec SEULEMENT une feuille `info` (aucune
    feuille income/balance/cashflow, cas d'un ETF via le fetch allege) doit
    pouvoir etre relu par load_local_data sans erreur -- sinon le fix #3
    (persister un fichier local pour un ETF) ne sert a rien : le fichier ne
    serait jamais rechargeable et le court-circuit 'fichier local' de
    _analyze_one (etape 2) ne pourrait jamais s'activer pour un vrai ETF."""
    from app.services.finance.buffett import data_fetch

    monkeypatch.setattr(data_fetch.Config, "FOLDER_PATH", str(tmp_path))

    data = {
        "income": pd.DataFrame(),
        "balance": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "info": {"longName": "Amundi MSCI World", "quoteType": "ETF", "currentPrice": 42.0},
    }
    assert data_fetch.save_local_data("CW8.PA", data) is True

    loaded = data_fetch.load_local_data("CW8.PA")
    assert loaded is not None
    assert loaded["info"]["longName"] == "Amundi MSCI World"


def test_save_local_data_still_rejects_fully_empty_data(monkeypatch, tmp_path):
    """Non-regression : si income/balance/cashflow ET info sont vides (rien
    d'exploitable -- ex. ticker delisté sans réponse), on ne persiste rien."""
    from app.services.finance.buffett import data_fetch

    monkeypatch.setattr(data_fetch.Config, "FOLDER_PATH", str(tmp_path))

    data = {
        "income": pd.DataFrame(),
        "balance": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "info": {},
    }
    saved = data_fetch.save_local_data("DEADXYZ", data)
    assert saved is False
    assert not (tmp_path / "DEADXYZ.xlsx").exists()
