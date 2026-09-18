import datetime as dt
import io
import json

import httpx
import pandas as pd
import pytest

from app.services.finance.buffett import official_etf_enrichment as enrichment


def test_vanguard_directory_discovers_alphanumeric_ids_once(monkeypatch):
    monkeypatch.setattr(enrichment, "_VANGUARD_DIRECTORY_CACHE", {})
    calls = []
    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, text='{"portIds":"E039,9679,E039"}')
        payload = json.loads(request.content)
        assert payload["variables"]["portIds"] == ["E039", "9679"]
        return httpx.Response(200, json={"data": {"funds": [
            {"portId": key, "profile": {"identifiers": [{"altIdCode": "ISIN", "altIdValue": isin}]}}
            for key, isin in [("E039", "IE0001VXZTV7"), ("9679", "IE00BK5BQT80")]
        ]}})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert enrichment._discover_vanguard_port_id(client, "IE0001VXZTV7")["port_id"] == "E039"
        assert enrichment._discover_vanguard_port_id(client, "IE00BK5BQT80")["port_id"] == "9679"
        assert enrichment._discover_vanguard_port_id(client, "IE00UNKNOWN0") is None
    assert calls == ["GET", "POST"]


@pytest.mark.parametrize("method", ["Physical-Full", "Synthetic"])
def test_hsbc_uses_exact_isin_and_does_not_download_collateral(monkeypatch, method):
    isin = "IE00BMWXKN31"
    monkeypatch.setattr(enrichment, "_pdf_text", lambda _: f"""
        ISIN {isin}
        May invest up to 10% in total return swaps.
        Replication method {method}
        Index name 100% Hang Seng TECH Index
        Index currency HKD
        Ongoing charge figure 0.50%
    """)
    calls = []
    def download(client, url):
        calls.append(url)
        return [{"isin": "KYG875721634", "weight": 0.99}]
    monkeypatch.setattr(enrichment, "_download_table", download)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"%PDF-test"))) as client:
        result = enrichment._fetch_hsbc(client, isin)
    assert result["index_name"] == "Hang Seng TECH Index"
    assert result["management_fee_rate"] == 0.005
    assert result["replication"] == ("physical" if method == "Physical-Full" else "synthetic")
    assert bool(calls) is (method == "Physical-Full")
    assert bool(result["holdings"]) is (method == "Physical-Full")


def test_hsbc_rejects_wrong_share_class(monkeypatch):
    monkeypatch.setattr(enrichment, "_pdf_text", lambda _: "ISIN IE00B4X9L533 Replication method Physical-Full")
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"%PDF-test"))) as client:
        assert enrichment._fetch_hsbc(client, "IE00BMWXKN31") is None


@pytest.mark.parametrize("values,expected", [
    ([99.0, 0.2], [0.99, 0.002]), ([0.99, 0.002], [0.99, 0.002]),
])
def test_weight_unit_is_consistent_for_entire_column(values, expected):
    frame = pd.DataFrame([
        ["ISIN", "SecurityName", "Weight"],
        ["US0000000001", "Large", values[0]],
        ["US0000000002", "Small", values[1]],
        [None, None, None],
    ])
    result = enrichment._holdings_from_frame(frame)
    assert [row["weight"] for row in result] == pytest.approx(expected)
    assert [row["name"] for row in result] == ["Large", "Small"]


def test_small_percentages_and_nonfinite_rows_are_handled():
    frame = pd.DataFrame([
        ["ISIN", "SecurityName", "Weighting", "Ticker"],
        ["US0000000001", "Small", 0.2, None],
        [None, "Cash", 99.8, None],
        ["US0000000002", "Invalid", float("inf"), None],
    ])
    result = enrichment._holdings_from_frame(frame)
    assert len(result) == 1
    assert result[0]["weight"] == 0.002
    assert result[0]["ticker"] == ""


def test_binary_excel_without_extension_is_read():
    buffer = io.BytesIO()
    pd.DataFrame([
        ["ISIN", "SecurityName", "Weighting"], ["US0000000001", "A", 99.5],
    ]).to_excel(buffer, index=False, header=False)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, content=buffer.getvalue(), headers={"Content-Type": "application/octet-stream"},
    ))) as client:
        result = enrichment._download_table(client, "https://example.test/holdings")
    assert result[0]["weight"] == 0.995


def test_legacy_excel_uses_existing_calamine_dependency(monkeypatch):
    def read_excel(stream, **kwargs):
        assert kwargs["engine"] == "calamine"
        assert stream.read().startswith(b"\xd0\xcf\x11\xe0")
        return {"Report": pd.DataFrame([
            ["ISIN", "SecurityName", "Weighting"], ["US0000000001", "A", 99.5],
        ])}
    monkeypatch.setattr(pd, "read_excel", read_excel)
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        200, content=b"\xd0\xcf\x11\xe0test", headers={"Content-Type": "application/vnd.ms-excel"},
    ))) as client:
        assert enrichment._download_table(client, "https://example.test/holdings")[0]["weight"] == 0.995


def test_new_connector_revision_retries_failure_once_but_keeps_success():
    record = {"name": "HSBC MSCI World", "official_enrichment": {
        "status": "temporary_error", "last_attempt_at": dt.date.today().isoformat(),
    }}
    assert enrichment._attempt_due(record, False)
    record["official_enrichment"]["connector_revision"] = enrichment._CONNECTOR_REVISIONS["hsbc"]
    assert not enrichment._attempt_due(record, False)
    record["official_enrichment"].update(status="complete", connector_revision=0)
    assert not enrichment._attempt_due(record, False)


def test_vanguard_includes_bonds_but_not_cash():
    def handle(request):
        assert json.loads(request.content)["variables"]["securityTypes"] is None
        return httpx.Response(200, json={"data": {
            "funds": [{"profile": {"etfReplicationMethodology": "Physical"}}],
            "borHoldings": [{"holdings": {"items": [
                {"ticker": "FRTR", "issuerName": "French Republic Government Bond", "securityType": "FI.NONUS_GOV", "marketValuePercentage": 99.8, "bloombergIsoCountry": "FR"},
                {"ticker": "EUR", "securityType": "CRNY", "marketValuePercentage": 0.2},
            ], "totalHoldings": 2}}],
        }})
    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = enrichment._fetch_vanguard(client, "IE00004S2680", product_id="E068")
    assert len(result["holdings"]) == 1
    assert result["holdings"][0]["asset_class"] == "Fixed Income"
    assert result["holdings"][0]["weight"] == pytest.approx(0.998)


@pytest.mark.parametrize("coverage,expected_status", [(0.995, "complete"), (0.4, "partial")])
def test_recovered_physical_fund_can_back_only_an_exact_index_proxy(tmp_path, monkeypatch, coverage, expected_status):
    from app.services.finance.buffett.etf_index_registry import (
        cached_physical_index_proxy, load_registry, save_registry,
    )
    path = tmp_path / "registry.json"
    identity = "ISIN:IE00B4X9L533"
    save_registry({"funds": {identity: {
        "name": "HSBC MSCI World", "isin": "IE00B4X9L533", "tickers": ["PHYS"],
    }}, "indices": {
        "MSCI-WORLD": {"name": "MSCI World Index"},
        "MSCI-WORLD-ESG": {"name": "MSCI World ESG Screened"},
    }}, path)
    monkeypatch.setattr(enrichment, "_fetch_hsbc", lambda *args: {
        "replication": "physical", "index_name": "MSCI World Net",
        "url": "https://www.assetmanagement.hsbc.co.uk/factsheet",
        "holdings_url": "https://www.assetmanagement.hsbc.co.uk/holdings",
        "holdings": [{"isin": "US0000000001", "weight": coverage}],
    })
    result = enrichment._enrich_official_etfs_serial(
        ["PHYS"], path=path, client=object(),
        _resolved={"PHYS": {"identity_key": identity}},
    )
    assert result["PHYS"]["status"] == expected_status
    assert result["PHYS"]["connector_revision"] == enrichment._CONNECTOR_REVISIONS["hsbc"]
    assert load_registry(path)["funds"][identity]["replication"] == "physical"
    proxy = cached_physical_index_proxy("MSCI-WORLD", path=path)
    assert bool(proxy) is (coverage >= 0.9)
    if proxy:
        assert proxy["source"] == "physical_tracker_proxy"
        assert proxy["proxy_isin"] == "IE00B4X9L533"
    assert cached_physical_index_proxy("MSCI-WORLD-ESG", path=path) is None


@pytest.mark.parametrize("label,is_index", [("Fund constituents", False), ("Index constituents", True)])
def test_constituents_label_alone_does_not_prove_index_exposure(monkeypatch, label, is_index):
    from bs4 import BeautifulSoup
    holdings = [{"isin": "US0000000001", "weight": 1.0}]
    monkeypatch.setattr(enrichment, "_download_table", lambda *args: holdings)
    index, fund = enrichment._download_holdings_links(
        BeautifulSoup(f'<a href="/download">{label}</a>', "html.parser"),
        "https://example.test/fund", object(),
    )
    assert bool(index[0]) is is_index
    assert bool(fund[0]) is not is_index
