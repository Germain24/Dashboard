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


# ── Cache NEGATIF : un ticker dont le fetch echoue (delisted, symbole invalide
# type ANTIN/LR sans suffixe .PA) ne doit PAS etre re-telecharge a chaque appel
# -- chaque poll de /finance/state relancait fast_info + history(1y) + history(5d)
# derriere le throttle global, affamant les endpoints interactifs (#ECONNRESET). ──

def test_failed_ticker_not_refetched_within_retry_window(monkeypatch):
    prices.clear_cache()
    calls: list[list[str]] = []

    def failing_fetch(tickers):
        calls.append(list(tickers))
        return {}

    day = dt.date(2026, 6, 3)
    monkeypatch.setattr(prices, "_now", lambda: 1000.0)
    prices.get_prices(["ANTIN"], fetcher=failing_fetch, today=day)
    # 10 minutes plus tard, meme jour : PAS de nouvelle tentative
    monkeypatch.setattr(prices, "_now", lambda: 1000.0 + 600.0)
    r = prices.get_prices(["ANTIN"], fetcher=failing_fetch, today=day)

    assert r["ANTIN"] == 0.0
    assert len(calls) == 1


def test_failed_ticker_refetched_after_retry_window(monkeypatch):
    prices.clear_cache()
    calls: list[list[str]] = []

    def fetch(tickers):
        calls.append(list(tickers))
        return {} if len(calls) == 1 else {"ANTIN": 12.0}

    day = dt.date(2026, 6, 3)
    monkeypatch.setattr(prices, "_now", lambda: 1000.0)
    prices.get_prices(["ANTIN"], fetcher=fetch, today=day)
    monkeypatch.setattr(prices, "_now", lambda: 1000.0 + prices.NEG_RETRY_S + 1.0)
    r = prices.get_prices(["ANTIN"], fetcher=fetch, today=day)

    assert len(calls) == 2
    assert r["ANTIN"] == 12.0


def test_failed_ticker_still_serves_last_known_price(monkeypatch):
    prices.clear_cache()
    monkeypatch.setattr(prices, "_now", lambda: 1000.0)
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0}, today=dt.date(2026, 6, 3))
    # Le lendemain le fetch echoue -> dernier cours connu, puis cache negatif
    calls: list[list[str]] = []

    def failing_fetch(tickers):
        calls.append(list(tickers))
        return {}

    day2 = dt.date(2026, 6, 4)
    r1 = prices.get_prices(["AAPL"], fetcher=failing_fetch, today=day2)
    r2 = prices.get_prices(["AAPL"], fetcher=failing_fetch, today=day2)
    assert r1["AAPL"] == 150.0
    assert r2["AAPL"] == 150.0
    assert len(calls) == 1  # 2e appel servi sans re-fetch (cache negatif)


def test_success_clears_negative_cache(monkeypatch):
    prices.clear_cache()
    monkeypatch.setattr(prices, "_now", lambda: 1000.0)
    day = dt.date(2026, 6, 3)
    prices.get_prices(["MSFT"], fetcher=lambda t: {}, today=day)
    monkeypatch.setattr(prices, "_now", lambda: 1000.0 + prices.NEG_RETRY_S + 1.0)
    prices.get_prices(["MSFT"], fetcher=lambda t: {"MSFT": 300.0}, today=day)
    # Succes -> plus de cache negatif, le prix vient du cache positif
    calls: list[list[str]] = []
    r = prices.get_prices(["MSFT"], fetcher=lambda t: calls.append(list(t)) or {}, today=day)
    assert r["MSFT"] == 300.0
    assert calls == []


# ── Pendant un run Buffett (throttle global sature par 10 workers), les
# endpoints interactifs ne doivent JAMAIS faire la queue pour un fetch live :
# on sert le dernier cours connu. Sans ca : /finance/state attendait plusieurs
# minutes -> proxy Next "socket hang up" (#ECONNRESET). ──

def test_no_fetch_while_analysis_running(monkeypatch):
    prices.clear_cache()
    calls: list[list[str]] = []
    monkeypatch.setattr(prices, "_analysis_running", lambda: True)

    r = prices.get_prices(["AAPL"], fetcher=lambda t: calls.append(list(t)) or {"AAPL": 1.0},
                          today=dt.date(2026, 6, 3))
    assert calls == []          # aucun fetch live pendant l'analyse
    assert r["AAPL"] == 0.0     # pas de cours connu -> 0


def test_serves_stale_price_while_analysis_running(monkeypatch):
    prices.clear_cache()
    monkeypatch.setattr(prices, "_analysis_running", lambda: False)
    prices.get_prices(["AAPL"], fetcher=lambda t: {"AAPL": 150.0}, today=dt.date(2026, 6, 3))

    monkeypatch.setattr(prices, "_analysis_running", lambda: True)
    calls: list[list[str]] = []
    r = prices.get_prices(["AAPL"], fetcher=lambda t: calls.append(list(t)) or {},
                          today=dt.date(2026, 6, 4))  # lendemain : cache "perime"
    assert calls == []
    assert r["AAPL"] == 150.0   # dernier cours connu servi tel quel
