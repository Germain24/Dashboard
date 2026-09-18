import datetime as dt

import pandas as pd
import pytest

from app.services.finance.buffett import (
    broker_availability, equity_lookthrough, etf_index_registry,
    manual_etf_sources, official_etf_enrichment, official_index_enrichment,
)
from app.services.finance.buffett.config import Config


@pytest.mark.parametrize("cached,forced,backing", [
    (False, False, "none"), (True, False, "none"), (True, True, "none"),
    (False, False, "fund"), (False, False, "proxy"), (False, True, "fund"),
    (False, False, "synthetic"),
])
def test_normal_preparation_respects_caches_and_limits_metadata(monkeypatch, cached, forced, backing):
    calls = {"funds": [], "indices": [], "resolved": [], "network_tickers": []}
    metadata = {"ETF": {"index_id": "INDEX", "identity_key": "FUND"}}
    if backing == "synthetic":
        metadata["ETF"]["replication"] = "synthetic"
    composition = {"source": "official_index_constituents", "holdings": [{"weight": 1.0}]}
    monkeypatch.setattr(Config, "ETF_OFFICIAL_ENRICHMENT_ENABLED", True)
    monkeypatch.setattr(Config, "ETF_OFFICIAL_INDEX_ENRICHMENT_ENABLED", True)
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: pd.DataFrame())
    monkeypatch.setattr(equity_lookthrough, "load_etf_replication_metadata", lambda wanted: {})
    def resolve(wanted, **kwargs):
        calls["resolved"].append(list(wanted))
        return metadata
    monkeypatch.setattr(etf_index_registry, "resolve_index_registry", resolve)
    monkeypatch.setattr(etf_index_registry, "load_registry", lambda: {"indices": {}, "funds": {}})
    monkeypatch.setattr(etf_index_registry, "cached_index_composition", lambda _, **k: composition if cached else None)
    monkeypatch.setattr(etf_index_registry, "cached_fund_composition", lambda _, **k: composition if backing in {"fund", "synthetic"} else None)
    monkeypatch.setattr(etf_index_registry, "cached_physical_index_proxy", lambda *a, **k: composition if backing == "proxy" else None)
    monkeypatch.setattr(manual_etf_sources, "prepare_manual_official_sources", lambda *a, **k: {})
    def enrich_funds(wanted, **kwargs):
        calls["funds"].append(kwargs)
        calls["network_tickers"].extend(wanted)
    monkeypatch.setattr(official_etf_enrichment, "enrich_official_etfs", enrich_funds)
    monkeypatch.setattr(official_index_enrichment, "enrich_official_indices", lambda *a, **k: calls["indices"].append(k))
    stop = lambda: False
    result = equity_lookthrough.fetch_etf_holdings(
        ["etf", "ETF"], refresh_indices=True, force_refresh=forced, should_stop=stop,
    )
    assert list(result) == ["ETF"]
    assert all(wanted == ["ETF"] for wanted in calls["resolved"])
    assert calls["funds"][0].get("force", False) is forced
    assert calls["funds"][0]["should_stop"] is stop
    assert calls["network_tickers"] == (["ETF"] if forced or (not cached and backing in {"none", "synthetic"}) else [])
    assert len(calls["indices"]) == int((not cached and backing in {"none", "synthetic"}) or forced)
    if calls["indices"]:
        assert calls["indices"][0].get("force", False) is forced
        assert calls["indices"][0]["should_stop"] is stop


@pytest.mark.parametrize("status", ["complete", "partial", "index_constituents_required", "temporary_error"])
def test_missing_fee_does_not_bypass_recent_attempt(status):
    record = {"name": "Amundi World UCITS ETF", "official_enrichment": {
        "status": status, "last_attempt_at": dt.date.today().isoformat(),
    }}
    assert not official_etf_enrichment._attempt_due(record, force=False)
    assert official_etf_enrichment._attempt_due(record, force=True)


def test_failed_index_is_not_fetched_again_and_stop_is_reported(tmp_path, monkeypatch):
    path = tmp_path / "registry.json"
    etf_index_registry.save_registry({"version": 2, "funds": {}, "indices": {
        "INDEX": {"name": "Test", "provider": "unknown"},
    }}, path)
    attempts = []
    def fail(*args):
        attempts.append(1)
        return official_index_enrichment._status("temporary_error", provider="unknown", error="timeout")
    monkeypatch.setattr(official_index_enrichment, "_fetch_index", fail)
    for _ in range(2):
        official_index_enrichment.enrich_official_indices(["INDEX"], path=path, client=object())
    assert len(attempts) == 1
    events = []
    result = official_index_enrichment.enrich_official_indices(
        ["INDEX"], path=path, client=object(), force=True, should_stop=lambda: True,
        progress_cb=lambda *event: events.append(event),
    )
    assert result == {}
    assert events == [(0, 1, "")]
    assert len(attempts) == 1
