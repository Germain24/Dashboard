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


# ── ETF = AUTORITAIRE depuis ToutBroker.xlsx ('Secteur 1' == 'ETF') ──────────

def test_check_is_etf_uses_broker_secteur1(monkeypatch):
    """_check_is_etf ne regarde plus le nom/quoteType : seul compte l'appartenance
    à l'ensemble ETF de ToutBroker ('Secteur 1' == 'ETF')."""
    from app.services.finance.buffett import broker_availability as ba
    from app.services.finance.buffett.runner import _check_is_etf
    monkeypatch.setattr(ba, "_ETF_CACHE", {"CW8.PA", "SEGA.L"})
    assert _check_is_etf("CW8.PA") is True
    assert _check_is_etf("AAPL") is False
    # quoteType='ETF' + nom de fonds n'a plus AUCUNE influence
    assert _check_is_etf("BA.TO", {"info": {"quoteType": "ETF", "longName": "iShares"}}) is False


def test_analyze_financials_etf_only_if_in_broker_set():
    """analyze_financials : Score=200/Secteur=ETF UNIQUEMENT si le ticker est dans
    l'ensemble ETF fourni — peu importe le quoteType/nom."""
    from app.services.finance.buffett.scoring import analyze_financials
    boeing = {"info": {"quoteType": "ETF", "longName": "The Boeing Company",
                       "sector": "Industrials"}, "income": None, "balance": None}
    # absent du set -> PAS ETF (même si quoteType='ETF')
    score, metrics = analyze_financials("BA.TO", boeing, etf_tickers=set())
    assert metrics["Secteur"] != "ETF"
    assert score != 200.0
    # présent dans le set -> ETF / 200
    score2, metrics2 = analyze_financials("CW8.PA", boeing, etf_tickers={"CW8.PA"})
    assert metrics2["Secteur"] == "ETF"
    assert score2 == 200.0


# ── 'ETF' comme MOT (utilisé par le pré-remplissage ToutBroker) ──────────────

def test_looks_like_fund_no_etf_substring_false_positive():
    """'ETF' à l'intérieur d'un mot (nETFlix, nETFonds, rockETFuel) ne doit PAS
    matcher : ce sont des actions, pas des fonds."""
    from app.services.finance.buffett.etf_detect import looks_like_fund
    assert looks_like_fund("NETFLIX, INC.") is False
    assert looks_like_fund("NETFONDS AG") is False
    assert looks_like_fund("ROCKETFUEL BLOCKCHAIN, INC.") is False
    # vrais fonds : toujours détectés
    assert looks_like_fund("ISHARES CORE MSCI WORLD UCITS ETF") is True
    assert looks_like_fund("INVESCO BLOOMBERG COMMODITY UCITS ETF") is True
    assert looks_like_fund("FXI ISHARES CHINA LARGE-CAP ETF") is True


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


def test_buffett_result_out_exposes_per_broker_allocations():
    """Le front a besoin du détail par broker (pie % T212 / nb actions) pour
    afficher l'allocation actionnable, sans exposer tout secteurs_extra."""
    from app.api.schemas_finance import BuffettResultOut
    from app.models.finance import BuffettRunResult
    row = BuffettRunResult(
        id=1, run_id=1, ticker="CW8.PA", nom="Amundi", chance_moat=200.0,
        secteur="ETF", allocation_pct=3.1, broker_cible="Trading212",
        secteurs_extra={"allocations": [
            {"broker": "Trading212", "type": "pie", "pie_pct": 40,
             "shares": None, "eur": 361.5, "pct": 1.2},
            {"broker": "BoursDirect2", "type": "shares", "pie_pct": None,
             "shares": 3, "eur": 540.0, "pct": 1.9},
        ]},
    )
    out = BuffettResultOut.model_validate(row)
    dumped = out.model_dump()
    assert dumped["allocations"][0]["pie_pct"] == 40
    assert dumped["allocations"][1]["shares"] == 3
    assert "secteurs_extra" not in dumped  # détail brut non exposé


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
