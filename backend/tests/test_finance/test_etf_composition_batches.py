import threading
import time

import pandas as pd

from app.services.finance.buffett import etf_composition_batches as batches
from app.services.finance.buffett import official_etf_enrichment as enrichment


def test_replacement_candidates_are_verified_in_two_large_batches(monkeypatch):
    tickers = [f"ETF{i:03d}.PA" for i in range(180)]
    returns = pd.DataFrame({ticker: [0.0, 0.01] for ticker in tickers})
    frame = pd.DataFrame({"Ticker": tickers})
    fetched_batches: list[list[str]] = []

    def fake_select(
        returns_pool,
        frame_pool,
        ticker_col,
        maximum=None,
        excluded_tickers=None,
        **_kwargs,
    ):
        excluded = set(excluded_tickers or ())
        selected = [ticker for ticker in tickers if ticker not in excluded][
            : int(maximum or 100)
        ]
        return (
            returns_pool[selected],
            frame_pool[frame_pool[ticker_col].isin(selected)].copy(),
            {
                "brokers": {
                    "BoursDirect2": {
                        "candidates_before": len(tickers) - len(excluded),
                        "selected": len(selected),
                        "selected_tickers": selected,
                    }
                }
            },
        )

    def fake_fetch(requested, **_kwargs):
        requested = list(requested)
        fetched_batches.append(requested)
        return {ticker: {"ticker": ticker} for ticker in requested}

    def fake_quality(payload, *_args, **_kwargs):
        number = int(payload["ticker"][3:6])
        return {
            "eligible": number >= 55,
            "reason": "complete" if number >= 55 else "missing",
            "coverage": 1.0 if number >= 55 else 0.0,
        }

    monkeypatch.setattr(batches, "select_etfs_per_broker", fake_select)
    monkeypatch.setattr(
        "app.services.finance.buffett.equity_lookthrough.fetch_etf_holdings",
        fake_fetch,
    )
    monkeypatch.setattr(
        "app.services.finance.buffett.equity_lookthrough.etf_composition_quality",
        fake_quality,
    )
    monkeypatch.setattr(batches.Config, "ETF_MAX_CANDIDATES_PER_BROKER", 100)
    monkeypatch.setattr(batches.Config, "ETF_COMPOSITION_BATCH_BUFFER_PER_BROKER", 50)

    result = batches.select_verified_etfs_per_broker(
        returns,
        frame,
        "Ticker",
        etf_tickers=set(tickers),
        metadata_by_ticker={},
        constituent_metadata={},
    )

    assert result.batches == 2
    assert [len(values) for values in fetched_batches] == [150, 30]
    assert len(result.returns.columns) == 100
    assert set(tickers[:55]).issubset(result.exclusions)


def test_official_fund_workers_respect_global_and_provider_limits(monkeypatch):
    tickers = [f"ETF{i}.PA" for i in range(8)]
    resolved = {
        ticker: {
            "identity_key": f"ISIN:{i}",
            "name": "Amundi Test UCITS ETF",
        }
        for i, ticker in enumerate(tickers)
    }
    active = 0
    maximum_active = 0
    serial_calls = 0
    resolved_seen: set[str] = set()
    guard = threading.Lock()

    monkeypatch.setattr(
        "app.services.finance.buffett.etf_index_registry.resolve_index_registry",
        lambda wanted, **_kwargs: {ticker: resolved[ticker] for ticker in wanted},
    )

    def fake_serial(requested, **_kwargs):
        nonlocal active, maximum_active, serial_calls
        requested = list(requested)
        with guard:
            serial_calls += 1
            active += 1
            maximum_active = max(maximum_active, active)
            resolved_seen.update((_kwargs.get("_resolved") or {}).keys())
        time.sleep(0.02)
        with guard:
            active -= 1
        return {ticker: {"status": "complete"} for ticker in requested}

    monkeypatch.setattr(enrichment, "_enrich_official_etfs_serial", fake_serial)
    monkeypatch.setattr(enrichment.Config, "ETF_ENRICHMENT_MAX_WORKERS", 4)
    monkeypatch.setattr(enrichment.Config, "ETF_ENRICHMENT_MAX_WORKERS_PER_PROVIDER", 2)

    result = enrichment.enrich_official_etfs(tickers)

    assert set(result) == set(tickers)
    assert maximum_active == 2
    assert serial_calls == 2
    assert resolved_seen == set(tickers)


def test_official_fund_batch_failure_is_retried_per_isin(monkeypatch):
    tickers = ["GOOD1.PA", "BAD.PA", "GOOD2.PA"]
    resolved = {
        ticker: {
            "identity_key": f"ISIN:{ticker}",
            "name": "Amundi Test UCITS ETF",
        }
        for ticker in tickers
    }
    monkeypatch.setattr(
        "app.services.finance.buffett.etf_index_registry.resolve_index_registry",
        lambda wanted, **_kwargs: {ticker: resolved[ticker] for ticker in wanted},
    )

    def fake_serial(requested, **_kwargs):
        requested = list(requested)
        if len(requested) > 1:
            raise ValueError("bad batch member")
        if requested == ["BAD.PA"]:
            raise TypeError("bad product payload")
        return {requested[0]: {"status": "complete"}}

    monkeypatch.setattr(enrichment, "_enrich_official_etfs_serial", fake_serial)
    monkeypatch.setattr(enrichment.Config, "ETF_ENRICHMENT_MAX_WORKERS", 2)
    monkeypatch.setattr(enrichment.Config, "ETF_ENRICHMENT_MAX_WORKERS_PER_PROVIDER", 1)

    result = enrichment.enrich_official_etfs(tickers)

    assert result["GOOD1.PA"]["status"] == "complete"
    assert result["GOOD2.PA"]["status"] == "complete"
    assert result["BAD.PA"]["status"] == "temporary_error"
    assert "bad product payload" in result["BAD.PA"]["error"]
