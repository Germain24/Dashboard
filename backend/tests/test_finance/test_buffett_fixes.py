"""Tests des correctifs Buffett : encodeur JSON numpy (#3) et détection ETF (#7)."""

import json

import numpy as np
import pandas as pd

from app.services.finance.buffett.cache_manager import json_default
from app.services.finance.buffett.runner import _check_is_etf
from app.services.finance.buffett.broker_availability import aggregate_weights


# ── #3 : encodeur JSON tolérant numpy ────────────────────────────────────────

def test_json_default_numpy_int():
    assert json_default(np.int32(42)) == 42
    assert isinstance(json_default(np.int32(42)), int)


def test_json_default_numpy_float():
    assert json_default(np.float64(3.5)) == 3.5
    assert isinstance(json_default(np.float64(3.5)), float)


def test_json_default_numpy_bool():
    assert json_default(np.bool_(True)) is True


def test_json_default_numpy_array():
    assert json_default(np.array([1, 2, 3])) == [1, 2, 3]


def test_json_dump_with_numpy_metrics_does_not_crash():
    payload = {
        "AAPL": {
            "score": np.float64(85.0),
            "latest_year": np.int32(2025),
            "volume": np.int64(1_000_000),
            "achat": np.bool_(True),
        }
    }
    # Sans default=json_default, ceci lèverait "Object of type int32 is not JSON serializable".
    s = json.dumps(payload, default=json_default)
    assert "85.0" in s and "2025" in s


# ── #7 : REIT/holdings ne sont pas des ETF ───────────────────────────────────

def _df_nonempty():
    return pd.DataFrame({"2024": [1.0]}, index=["Revenue"])


def test_reit_with_financials_is_not_etf():
    # quoteType peut dire ETF par erreur, mais des comptes existent -> pas ETF.
    data = {
        "info": {"quoteType": "ETF", "longName": "VICI Properties Inc."},
        "income": _df_nonempty(),
        "balance": _df_nonempty(),
    }
    assert _check_is_etf("VICI", data) is False


def test_etf_without_financials_is_etf():
    data = {"info": {"quoteType": "ETF", "longName": "iShares Core MSCI"}, "income": None, "balance": None}
    assert _check_is_etf("CBSM.PA", data) is True


def test_etf_detected_by_name_when_no_financials():
    data = {"info": {"quoteType": "", "longName": "Amundi MSCI World ETF"}, "income": None, "balance": None}
    assert _check_is_etf("CW8.PA", data) is True


def test_secondary_listing_with_etf_quotetype_is_not_etf():
    # Cotation secondaire / CDR : yfinance renvoie quoteType="ETF" sur une ACTION,
    # financials vides. Le nom (entreprise) ne ressemble pas à un fonds → PAS ETF
    # (sinon Score=200, pollution de l'analyse + contournement du dédoublonnage).
    data = {"info": {"quoteType": "ETF", "longName": "Chevron Corporation"},
            "income": None, "balance": None}
    assert _check_is_etf("CHEV.TO", data) is False


def test_real_etf_detected_by_name_despite_no_quotetype():
    data = {"info": {"quoteType": "", "longName": "Amundi MSCI World UCITS ETF"},
            "income": None, "balance": None}
    assert _check_is_etf("CW8.PA", data) is True


def test_company_named_with_etf_substring_but_has_financials():
    # Mot "ETF" au milieu d'un nom ne doit pas suffire, et comptes présents = pas ETF.
    data = {
        "info": {"quoteType": "EQUITY", "longName": "Global Net Lease, Inc."},
        "income": _df_nonempty(),
        "balance": _df_nonempty(),
    }
    assert _check_is_etf("GNL", data) is False


# ── #1 : agrégation des poids par ticker (colonne Poids) ─────────────────────

def test_aggregate_weights_sums_per_ticker():
    alloc = [
        {"Ticker": "AAPL", "Broker": "T212", "Poids total (%)": 3.0},
        {"Ticker": "AAPL", "Broker": "IBKR", "Poids total (%)": 2.0},
        {"Ticker": "MSFT", "Broker": "IBKR", "Poids total (%)": 5.0},
    ]
    w = aggregate_weights(alloc)
    assert w["AAPL"] == 5.0
    assert w["MSFT"] == 5.0


def test_aggregate_weights_empty():
    assert aggregate_weights([]) == {}
    assert aggregate_weights(None) == {}


# ── Colonne Score du détail de run : le front lit `score`, pas `chance_moat` ──

def test_buffett_result_out_exposes_score_from_chance_moat():
    """L'API doit exposer `score` (= chance_moat) sinon la colonne Score du
    détail de run reste vide ("—") côté front (qui lit r.score)."""
    from app.api.schemas_finance import BuffettResultOut
    from app.models.finance import BuffettRunResult

    row = BuffettRunResult(id=1, run_id=1, ticker="AAPL", nom="Apple",
                           chance_moat=87.5, secteur="Tech", allocation_pct=12.0)
    out = BuffettResultOut.model_validate(row)
    assert out.score == 87.5
    assert out.model_dump()["score"] == 87.5


# ── Suppression d'un ticker delisté même avec un cache local périmé (#) ────────

def test_delisted_ticker_with_stale_local_data_is_deleted(monkeypatch):
    """Un ticker dont yfinance ne renvoie plus rien doit être supprimé même
    s'il a un fichier local périmé. Avant le fix, merge_data réinjectait les
    vieilles données -> data non vide -> jamais supprimé (relances inutiles)."""
    import threading

    from app.services.finance.buffett import runner

    nonempty = pd.DataFrame({"2019": [1.0]}, index=["Total Revenue"])
    local = {"income": nonempty, "balance": nonempty,
             "info": {"quoteType": "EQUITY", "longName": "Old Co"}}
    fresh_empty = {"income": pd.DataFrame(), "balance": pd.DataFrame(),
                   "cashflow": pd.DataFrame(), "info": {}}

    class FakeCache:
        def get_cached_result(self, t):
            return None

        def get_status(self, t, fp):
            return "too_old"

        def update(self, *a, **k):
            pass

    monkeypatch.setattr(runner, "load_local_data", lambda t: local)
    monkeypatch.setattr(runner, "_fetch_with_retry", lambda t, rl, sf=None: fresh_empty)

    results: dict = {}
    deleted: set = set()
    ok = runner._analyze_one("DEADXYZ", results, FakeCache(), object(),
                             deleted, threading.Lock())
    assert ok is False
    assert "DEADXYZ" in deleted
