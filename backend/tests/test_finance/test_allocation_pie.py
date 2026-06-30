"""Trading212 = pie en % ENTIERS sommant à 100 (1% d'incrément) DANS le broker ;
autres brokers = nombre d'actions entières."""

import numpy as np


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
