"""Source de cours avec cache quotidien."""

from __future__ import annotations

import datetime as dt

from app.services.finance import prices


def test_cache_hits_same_day_fetches_once():
    prices.clear_cache()
    calls: list[list[str]] = []

    def fake_fetch(tickers):
        calls.append(list(tickers))
        return {"AAPL": 100.0, "MSFT": 200.0}

    day = dt.date(2026, 6, 3)
    r1 = prices.get_prices(["AAPL", "MSFT"], fetcher=fake_fetch, today=day)
    assert r1 == {"AAPL": 100.0, "MSFT": 200.0}

    # 2e appel le même jour : aucun nouvel appel réseau
    r2 = prices.get_prices(["AAPL", "MSFT"], fetcher=fake_fetch, today=day)
    assert r2 == {"AAPL": 100.0, "MSFT": 200.0}
    assert len(calls) == 1  # une seule récupération


def test_refetch_next_day():
    prices.clear_cache()
    calls: list[list[str]] = []

    def fake_fetch(tickers):
        calls.append(list(tickers))
        return {"AAPL": 100.0}

    prices.get_prices(["AAPL"], fetcher=fake_fetch, today=dt.date(2026, 6, 3))
    prices.get_prices(["AAPL"], fetcher=fake_fetch, today=dt.date(2026, 6, 4))
    assert len(calls) == 2  # nouveau jour -> nouvelle récupération


def test_fetch_failure_keeps_last_known_price():
    prices.clear_cache()

    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0}, today=dt.date(2026, 6, 3))
    # Le lendemain le fetch échoue (rien renvoyé) -> on garde l'ancien prix
    r = prices.get_prices(["AAPL"], fetcher=lambda t: {}, today=dt.date(2026, 6, 4))
    assert r["AAPL"] == 150.0


def test_unknown_ticker_is_zero():
    prices.clear_cache()
    r = prices.get_prices(["ZZZZ"], fetcher=lambda t: {}, today=dt.date(2026, 6, 3))
    assert r["ZZZZ"] == 0.0
