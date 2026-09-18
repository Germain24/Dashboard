from app.services.finance.buffett.country_normalization import (
    canonical_country,
    canonicalize_exposure,
)
from app.services.finance.buffett.optimizer import meets_optimization_score_threshold
from app.services.finance.buffett.reporting import (
    fundamental_mismatch_tickers,
    score_calibration,
)


def test_country_codes_and_names_are_merged():
    assert canonical_country("DE") == "Germany"
    assert canonical_country("Allemagne") == "Germany"
    assert canonicalize_exposure({"DE": 0.4, "Germany": 0.6}) == {"Germany": 1.0}


def test_model_and_mismatch_are_hard_purchase_guards_even_when_forced():
    common = dict(ticker="V", score=95, threshold=85, forced_tickers={"V"}, quality_score=95, confidence_pct=80)
    assert meets_optimization_score_threshold(**common, model_complete=True)
    assert not meets_optimization_score_threshold(**common, model_complete=False)
    assert not meets_optimization_score_threshold(**common, fundamental_mismatch=True)


def test_fundamental_mismatch_ignores_price_but_not_v3_scores():
    rows = {
        "ITX.MC": (90.0, {"ISIN": "ES0148396007", "score_model_version": 3, "buffett_quality_score": 90, "durability_score": 88, "dilution_discipline_score": 80, "Prix": 40}),
        "IXD1.DE": (90.0, {"ISIN": "ES0148396007", "score_model_version": 3, "buffett_quality_score": 90, "durability_score": 88, "dilution_discipline_score": 80, "Prix": 41}),
    }
    assert fundamental_mismatch_tickers(rows) == set()
    rows["IXD1.DE"][1]["buffett_quality_score"] = 81
    assert fundamental_mismatch_tickers(rows) == {"ITX.MC", "IXD1.DE"}


def test_score_calibration_is_global_and_by_model():
    rows = {
        "A": (80, {"buffett_quality_score": 80, "business_model": "standard"}),
        "B": (90, {"buffett_quality_score": 90, "business_model": "standard"}),
        "C": (95, {"buffett_quality_score": 95, "business_model": "payment_network"}),
        "ETF": (0, {"buffett_quality_score": None, "InstrumentType": "ETF"}),
    }
    result = score_calibration(rows)
    assert result["global"]["count"] == 3
    assert result["global"]["thresholds_pct"]["gte_90"] == 66.67
    assert result["by_business_model"]["standard"]["count"] == 2


def test_optimizer_keeps_a_quality_action_sleeve(monkeypatch):
    import numpy as np
    import pandas as pd

    from app.services.finance.buffett import optimizer
    from app.services.finance.buffett.config import Config

    tickers = ["CW8.PA", "ETF2", *[f"ACTION{i}" for i in range(12)]]
    monkeypatch.setattr(optimizer, "load_etf_tickers", lambda: {"CW8.PA", "ETF2"})
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"IBKR": 10_000.0})
    monkeypatch.setattr(Config, "MIN_DEFENSIVE_PCT", 0.0)
    monkeypatch.setattr(Config, "MAX_COUNTRY_PCT", 1.0)
    monkeypatch.setattr(Config, "STARR_DE_MIN_GENERATIONS", 2)
    monkeypatch.setattr(Config, "STARR_DE_POLISH_MAXITER", 2)
    rng = np.random.default_rng(20260829)
    returns = pd.DataFrame(
        rng.normal(0.0005, 0.012, (400, len(tickers))), columns=tickers
    )
    quality = {ticker: 90.0 + index / 10 for index, ticker in enumerate(tickers[2:])}
    weights, _, diagnostics = optimizer.optimize_portfolio_de(
        tickers,
        returns,
        [[True] for _ in tickers],
        ["IBKR"],
        n_sim=500,
        max_generations=3,
        quality_scores_by_ticker=quality,
        return_diagnostics=True,
    )
    assert weights.shape == (len(tickers), 1)
    assert diagnostics["direct_action_policy"]["mandatory"] is False
    assert diagnostics["best_action_candidate"]["found"] is True
    assert diagnostics["best_action_candidate"]["action_count"] >= 1
