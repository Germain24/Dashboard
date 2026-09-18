"""Trading212 = pie en % ENTIERS sommant à 100 (1% d'incrément) DANS le broker ;
autres brokers = nombre d'actions entières."""

import numpy as np
import pandas as pd
import pytest


def test_cardinality_penalty_is_disabled_by_default():
    from app.services.finance.buffett.config import Config

    assert Config.STARR_CARD_BETA == 0.0


def test_t212_pie_integer_pct_sums_to_100(monkeypatch):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    tickers = ["A", "B", "C"]
    W = np.array([[0.5], [0.3], [0.2]])           # 1 broker -> tout sur T212
    prices = {"A": 100.0, "B": 50.0, "C": 25.0}
    alloc = discretize_allocation(tickers, W, ["Trading212"], prices, 1000.0)

    assert alloc, "allocation non vide"
    assert all(a["type"] == "pie" for a in alloc)
    pies = {a["Ticker"]: a["pie_pct"] for a in alloc}
    assert all(isinstance(p, int) for p in pies.values())
    assert sum(pies.values()) == 100                # somme = 100% DANS T212
    # ordre de grandeur respecté (A>B>C)
    assert pies["A"] > pies["B"] > pies["C"]


def test_other_broker_returns_whole_shares(monkeypatch):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    tickers = ["A", "B"]
    W = np.array([[0.6], [0.4]])
    prices = {"A": 100.0, "B": 200.0}
    alloc = discretize_allocation(tickers, W, ["BoursDirect2"], prices, 1000.0)
    assert all(a["type"] == "shares" for a in alloc)
    assert all(isinstance(a["shares"], int) and a["shares"] >= 1 for a in alloc)
    # pas de pie_pct pour les actions entières (ou None)
    assert all(a.get("pie_pct") in (None, 0) for a in alloc)


def test_secondary_execution_quote_uses_its_price_but_keeps_analysis_identity(
    monkeypatch,
):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    alloc = discretize_allocation(
        ["FGR.PA"],
        np.array([[1.0]]),
        ["BoursDirect2"],
        {"FGR.PA": 100.0},
        1000.0,
        execution_routes={("FGR.PA", "BoursDirect2"): "EF3.DE"},
        execution_prices={("FGR.PA", "BoursDirect2"): 80.0},
    )
    assert alloc == [{
        "Ticker": "EF3.DE",
        "AnalysisTicker": "FGR.PA",
        "Broker": "BoursDirect2",
        "shares": 12,
        "eur": 960.0,
        "prix": 80.0,
        "type": "shares",
        "pie_pct": None,
        "Poids total (%)": 96.0,
    }]


def test_orphan_budget_redeployed_when_a_line_has_no_price(monkeypatch):
    """Un titre alloué mais SANS prix (absent de close_df) ne doit pas laisser son
    budget en cash : le reliquat déborde sur les lignes achetables. Reste final <
    prix le moins cher (ici < 100 €)."""
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    tickers = ["A", "B"]
    W = np.array([[0.5], [0.5]])      # B vise 500 € mais n'a pas de prix
    prices = {"A": 100.0}             # B absent -> non achetable
    alloc = discretize_allocation(tickers, W, ["BoursDirect2"], prices, 1000.0)
    spent = sum(a["eur"] for a in alloc)
    assert spent >= 1000.0 - 100.0, f"cash orphelin non redeploye: depense {spent}"


def test_integer_rounding_leftover_below_cheapest_share(monkeypatch):
    """Même quand tous les titres ont un prix, le cash résiduel après arrondi en
    actions entières doit rester sous le prix de l'action la moins chère."""
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config
    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    tickers = ["A", "B", "C"]
    W = np.array([[0.34], [0.33], [0.33]])
    prices = {"A": 130.0, "B": 170.0, "C": 90.0}
    alloc = discretize_allocation(tickers, W, ["BoursDirect2"], prices, 1000.0)
    spent = sum(a["eur"] for a in alloc)
    assert 1000.0 - spent < 90.0, f"reste {1000.0 - spent} >= prix le moins cher"


def test_dense_micro_targets_are_pruned_and_redeployed(monkeypatch):
    """Une projection dense peut matérialiser les lignes achetables.

    Une action entière est la granularité minimale ; le seuil global de 1 % ne
    doit plus supprimer une ligne avant cette conversion.
    """
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 10_000.0})
    monkeypatch.setattr(Config, "MIN_ALLOCATION_THRESHOLD", 0.01)
    monkeypatch.setattr(Config, "STARR_MAX_LINES_PER_BROKER", 20)

    tickers = ["CORE"] + [f"DUST{i:03d}" for i in range(100)]
    weights = np.array([[0.60]] + [[0.004]] * 100)  # somme 1, dust a 0,4 %
    prices = {ticker: 10.0 for ticker in tickers}

    alloc = discretize_allocation(
        tickers,
        weights,
        ["BoursDirect2"],
        prices,
        total_cap=10_000.0,
    )

    broker_lines = [row for row in alloc if row["Broker"] == "BoursDirect2"]
    assert len(broker_lines) == len(tickers)
    assert all(row["shares"] >= 1 for row in broker_lines)
    assert sum(row["eur"] for row in broker_lines) <= 10_000.0


def test_whole_share_allocation_reserves_broker_fees(monkeypatch):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"BoursDirect2": 1000.0})
    alloc = discretize_allocation(
        ["CORE.PA"],
        np.array([[1.0]]),
        ["BoursDirect2"],
        {"CORE.PA": 100.0},
        total_cap=1000.0,
        fee_reserve_eur_by_broker={"BoursDirect2": 15.0},
    )

    invested = sum(row["eur"] for row in alloc)
    investable_budget = 1000.0 - 15.0
    assert invested <= investable_budget + 1e-9
    assert investable_budget - invested < 100.0


def test_fractional_pie_allocation_reserves_broker_fees(monkeypatch):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(Config, "BUDGET_BROKERS", {"Trading212": 1000.0})
    alloc = discretize_allocation(
        ["US_STOCK"],
        np.array([[1.0]]),
        ["Trading212"],
        {"US_STOCK": 100.0},
        total_cap=1000.0,
        fee_reserve_eur_by_broker={"Trading212": 15.0},
    )

    invested = sum(row["eur"] for row in alloc)
    investable_budget = 1000.0 - 15.0
    pie_point_eur = 1000.0 / 100.0
    assert invested <= investable_budget + 1e-9
    assert investable_budget - invested < pie_point_eur
    assert sum(int(row["pie_pct"]) for row in alloc) == 98


def test_small_broker_line_count_remains_bounded_by_budget(monkeypatch):
    """Les pies utilisent 1 % local, sans créer plus de 100 points."""
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(
        Config,
        "BUDGET_BROKERS",
        {"BoursDirect2": 96_500.0, "Trading212": 3_500.0},
    )
    monkeypatch.setattr(Config, "MIN_ALLOCATION_THRESHOLD", 0.01)
    monkeypatch.setattr(Config, "STARR_MAX_LINES_PER_BROKER", 20)

    tickers = [f"T212_{index:02d}" for index in range(15)]
    weights = np.full((15, 1), 0.035 / 15.0)
    alloc = discretize_allocation(
        tickers,
        weights,
        ["Trading212"],
        {ticker: 10.0 for ticker in tickers},
        total_cap=100_000.0,
    )

    assert len(alloc) == 15
    assert sum(int(row["pie_pct"]) for row in alloc) == 100
    assert all(int(row["pie_pct"]) >= 1 for row in alloc)


def test_t212_integer_pie_rounding_preserves_local_minimum(monkeypatch):
    from app.services.finance.buffett.allocation import discretize_allocation
    from app.services.finance.buffett.config import Config

    monkeypatch.setattr(
        Config,
        "BUDGET_BROKERS",
        {"BoursDirect2": 96_453.0, "Trading212": 3_547.0},
    )
    monkeypatch.setattr(Config, "MIN_ALLOCATION_THRESHOLD", 0.01)
    alloc = discretize_allocation(
        ["A", "B", "C"],
        np.array([[0.01], [0.01], [0.01547]]),
        ["Trading212"],
        {"A": 10.0, "B": 10.0, "C": 10.0},
        total_cap=100_000.0,
    )

    assert len(alloc) == 3
    assert sum(int(row["pie_pct"]) for row in alloc) == 100
    assert all(int(row["pie_pct"]) >= 1 for row in alloc)
    pies = {row["AnalysisTicker"]: int(row["pie_pct"]) for row in alloc}
    assert pies == {"A": 28, "B": 28, "C": 44}


def test_latest_prices_eur_converts_native_quotes(monkeypatch):
    from app.services.finance import fx
    from app.services.finance.buffett import dedup
    from app.services.finance.buffett.allocation import latest_prices_eur

    currencies = {"US": "USD", "EU": "EUR"}
    monkeypatch.setattr(dedup, "ticker_currency_raw", lambda ticker: currencies[ticker])
    monkeypatch.setattr(
        fx,
        "get_rate",
        lambda base, quote, stale_ok=True: {("USD", "EUR"): 0.8, ("EUR", "EUR"): 1.0}[
            (base, quote)
        ],
    )
    close = pd.DataFrame({"US": [100.0, 110.0], "EU": [90.0, 95.0]})

    prices = latest_prices_eur(close, ["US", "EU"])

    assert prices["US"] == 88.0
    assert prices["EU"] == 95.0


# ── Lignes londoniennes : la LSE cote en GBP OU en pence (GBp) selon la ligne.
# Traiter des pence comme des livres multiplie le cours par 100, donc divise par
# 100 le nombre d'actions achetees.


def _patch_lse(monkeypatch, raw_currency):
    from app.services.finance import fx
    from app.services.finance.buffett import dedup

    calls = {"n": 0}

    def fake_raw(ticker):
        calls["n"] += 1
        return raw_currency

    monkeypatch.setattr(dedup, "ticker_currency_raw", fake_raw)
    monkeypatch.setattr(
        fx, "get_rate", lambda base, quote, stale_ok=True: 1.2 if base == "GBP" else 1.0
    )
    return calls


def test_latest_prices_eur_converts_pence_quotes(monkeypatch):
    from app.services.finance.buffett.allocation import latest_prices_eur

    _patch_lse(monkeypatch, "GBp")
    close = pd.DataFrame({"YU.L": [1700.0, 1720.0]})

    # 1720 pence = 17,20 GBP -> 20,64 EUR (et surtout PAS 2064 EUR).
    assert latest_prices_eur(close, ["YU.L"])["YU.L"] == pytest.approx(20.64)


def test_latest_prices_eur_keeps_pound_quotes_intact(monkeypatch):
    from app.services.finance.buffett.allocation import latest_prices_eur

    _patch_lse(monkeypatch, "GBP")
    close = pd.DataFrame({"BVA.L": [20.0, 20.5]})

    # 20,5 GBP -> 24,60 EUR : c'est bien le cas observe sur BVA.L.
    assert latest_prices_eur(close, ["BVA.L"])["BVA.L"] == pytest.approx(24.60)


def test_unknown_lse_currency_is_reported_instead_of_failing_silently(monkeypatch, capsys):
    """Sans devise, on garde 1,0 — mais on le DIT : l'erreur valait 100x."""
    from app.services.finance.buffett.allocation import latest_prices_eur

    _patch_lse(monkeypatch, None)
    close = pd.DataFrame({"HSBA.L": [600.0, 620.0]})

    latest_prices_eur(close, ["HSBA.L"])

    out = capsys.readouterr().out
    assert "HSBA.L" in out and "100x trop faible" in out


def test_lse_currency_is_fetched_once_per_ticker(monkeypatch):
    """Le bloc pence refaisait le meme appel reseau que _ticker_currency."""
    from app.services.finance.buffett.allocation import latest_prices_eur

    calls = _patch_lse(monkeypatch, "GBp")
    latest_prices_eur(pd.DataFrame({"YU.L": [1700.0, 1720.0]}), ["YU.L"])

    assert calls["n"] == 1
