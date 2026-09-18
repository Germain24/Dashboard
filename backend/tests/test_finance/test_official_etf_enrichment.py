import datetime as dt
import json

import httpx
import pandas as pd
import pytest

from app.services.finance.buffett import official_etf_enrichment as enrichment
from app.services.finance.buffett.official_etf_enrichment import (
    _attempt_due,
    _discover_vanguard_port_id,
    _fee_from_text,
    _fee_rate,
    _fetch_bnp_replication,
    _fetch_franklin,
    _fetch_global_x,
    _fetch_invesco,
    _fetch_ishares_page,
    _fetch_jpmorgan,
    _fetch_spdr,
    _fetch_ubs_replication,
    _fetch_vanguard,
    _holdings_from_frame,
    _issuer,
    _official_marginal_exposures,
    _official_replication,
    _replications_from_text_pages,
    enrich_official_etfs,
    enrich_unknown_etf_replications,
)


def _broker(*rows):
    return pd.DataFrame(rows)


def test_official_management_fees_are_normalized_to_annual_fraction():
    assert _fee_rate("0.20%") == 0.002
    assert _fee_rate(0.002) == 0.002
    assert _fee_from_text("Ongoing charges 0,35 % per year") == pytest.approx(0.0035)


def test_invesco_api_resolves_exact_isin_metadata_and_index_holdings():
    isin = "IE00BLCH1X54"

    def handler(request):
        if request.url.path.endswith(f"/{isin}"):
            return httpx.Response(200, json={
                "aliases": {"isin": isin},
                "replicationMethod": "Physical",
                "investmentStrategy": {"assetType": "Fixed Income"},
                "shareclassCharges": {"fundManagementCharge": "0.10%"},
                "benchmarkRelationships": [{
                    "benchmarkFullName": "Bloomberg US Treasury &amp; Coupons Index",
                }],
            })
        if request.url.path.endswith(f"/{isin}/holdings/index"):
            return httpx.Response(200, json={"holdings": [
                {"name": "US Treasury", "isin": "US912828Z781", "weight": 99.5},
                {"name": "Cash and/or Derivatives", "weight": 0.5},
            ]})
        raise AssertionError(str(request.url))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = _fetch_invesco(client, isin)

    assert result["index_name"] == "Bloomberg US Treasury & Coupons Index"
    assert result["replication"] == "physical"
    assert result["asset_class"] == "Fixed Income"
    assert result["management_fee_rate"] == pytest.approx(0.001)
    assert result["index_holdings"] == [{
        "ticker": "",
        "isin": "US912828Z781",
        "name": "US Treasury",
        "weight": 0.995,
    }]


def test_official_country_and_sector_margins_are_parsed_without_cross_product():
    parsed = _official_marginal_exposures("""
    Country breakdown
    United States 60.0%
    Japan 25.0%
    France 15.0%
    Sector breakdown
    Information Technology 55.0%
    Financials 30.0%
    Industrials 15.0%
    """)

    assert parsed["countries"] == {
        "United States": 0.60, "Japan": 0.25, "France": 0.15,
    }
    assert parsed["sectors"]["Information Technology"] == pytest.approx(0.55)
    assert "sector_country" not in parsed


def test_collateral_breakdown_is_never_accepted_as_economic_exposure():
    parsed = _official_marginal_exposures("""
    Country breakdown
    Collateral substitute basket
    France 100.0%
    Sector breakdown
    Technology 100.0%
    """)

    assert parsed.get("countries") in (None, {})
    assert _fee_from_text("unrelated return 12.5 %") is None


def test_new_issuer_connector_retries_old_unsupported_cache_immediately():
    assert _attempt_due({
        "name": "Vanguard FTSE All-World UCITS ETF",
        "official_enrichment": {
            "status": "unsupported_issuer",
            "last_attempt_at": "2026-08-21",
        },
    }, force=False)


def test_recent_official_failure_obeys_retry_delay_even_without_fee():
    assert not _attempt_due({
        "name": "Invesco Test UCITS ETF",
        "official_enrichment": {
            "status": "temporary_error",
            "last_attempt_at": enrichment.dt.date.today().isoformat(),
        },
    }, force=False)


def test_repaired_missing_isin_retries_immediately():
    assert _attempt_due({
        "isin": "LU1681043599",
        "name": "Amundi MSCI World Swap UCITS ETF",
        "official_enrichment": {
            "status": "missing_catalog_isin",
            "last_attempt_at": enrichment.dt.date.today().isoformat(),
        },
    }, force=False)


def test_broker_priority_issuer_variants_are_recognized():
    assert _issuer("BNP Paribas Easy S&P 500 UCITS ETF") == "bnp"
    assert _issuer("UBS MSCI Japan UCITS ETF") == "ubs"
    assert _issuer("JPM Global Research Enhanced ETF") == "jpmorgan"
    assert _issuer("Xtr.IE Xtrackers NASDAQ Swap ETF") == "xtrackers"
    assert _official_replication("Replication: physical stratified sampling") == "physical"
    assert _official_replication("Replication Method: Synthetic") == "synthetic"


def test_bnp_range_is_cached_while_product_exposure_is_checked_per_isin(monkeypatch):
    enrichment._BNP_RANGE_CACHE.clear()
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"%PDF mocked")

    monkeypatch.setattr(
        enrichment,
        "_pdf_replications_by_isin",
        lambda _content: {
            "FR0011550185": "synthetic",
            "FR0012739431": "physical",
        },
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    first = _fetch_bnp_replication(client, "FR0011550185")
    second = _fetch_bnp_replication(client, "FR0012739431")

    assert first and first["replication"] == "synthetic"
    assert second and second["replication"] == "physical"
    # un catalogue de gamme +, par ISIN, une fiche produit et un appel à l'API
    # push d'exposition (la fiche mockée en PDF fait échouer le JSON proprement).
    assert calls == 5


def test_same_isin_is_only_enriched_once_per_pass(tmp_path, monkeypatch):
    path = tmp_path / "indices.json"
    broker = _broker(
        {
            "Ticker Yahoo Finance": "BNP1.PA",
            "ISIN": "FR0011550185",
            "Nom": "BNP Paribas Easy Test UCITS ETF",
            "Secteur 1": "ETF",
        },
        {
            "Ticker Yahoo Finance": "BNP1.DE",
            "ISIN": "FR0011550185",
            "Nom": "BNP Paribas Easy Test UCITS ETF",
            "Secteur 1": "ETF",
        },
    )
    calls = 0

    def fake_fetch(_http, _isin):
        nonlocal calls
        calls += 1
        return {
            "url": "https://official.example/fund",
            "replication": "synthetic",
            "management_fee_rate": None,
        }

    monkeypatch.setattr(enrichment, "_fetch_bnp_replication", fake_fetch)

    results = enrich_official_etfs(
        ["BNP1.PA", "BNP1.DE"],
        broker_table=broker,
        path=path,
    )

    assert calls == 1
    assert results["BNP1.PA"]["status"] == "metadata_complete"
    assert results["BNP1.DE"]["status"] == "metadata_complete"


def test_bnp_merged_replication_cells_are_inherited_without_crossing_funds():
    methods = _replications_from_text_pages(["""
      MSCI Japan Accumulating LU3086269894 ticker EUR Physical 6
      MSCI ACWI Accumulating
      LU3086265710 ticker USD
      Synthetic 6
      LU3243907741 ticker EUR
      MSCI EMU Accumulating LU3215536486 ticker EUR Physical 6
    """])

    assert methods["LU3086269894"] == "physical"
    assert methods["LU3086265710"] == "synthetic"
    assert methods["LU3243907741"] == "synthetic"
    assert methods["LU3215536486"] == "physical"


def test_ubs_official_tables_resolve_exact_fund_name():
    enrichment._UBS_RANGE_CACHE.clear()
    html = """
      <table><tr><th>Fund name</th><th>UBS MSCI Japan UCITS ETF</th></tr>
      <tr><td>ISIN</td><td>LU0000000001</td></tr>
      <tr><td>Replication</td><td>Physical sampling</td></tr></table>
    """
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, text=html)
    ))

    result = _fetch_ubs_replication(
        client,
        "LU0000000001",
        fund_name="UBS MSCI Japan UCITS ETF EUR Acc",
    )

    assert result and result["replication"] == "physical"


def test_jpmorgan_connector_reads_official_factsheet(monkeypatch):
    product = """
      <html><body>IE00BF4G6Y48
      <script>documents={"IE00BF4G6Y48":[{"documentType":"Fact Sheet (US EMEA)",
      "docURL":"https://official.example/jpm-factsheet.pdf"}]};</script>
      </body></html>
    """

    def handler(request):
        if str(request.url).endswith("jpm-factsheet.pdf"):
            return httpx.Response(200, content=b"%PDF mocked")
        return httpx.Response(200, text=product)

    monkeypatch.setattr(
        enrichment,
        "_pdf_text",
        lambda _content: (
            "Investment Method Physically Invested\n"
            "Benchmark MSCI World Index\nTotal Expense Ratio (TER) 0.25%"
        ),
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = _fetch_jpmorgan(
        client,
        "IE00BF4G6Y48",
        fund_name=(
            "JPMorgan ETFs (Ireland) ICAV - Global Research Enhanced Index "
            "Equity Active UCITS ETF USD Acc"
        ),
    )

    assert result and result["replication"] == "physical"
    assert result["management_fee_rate"] == pytest.approx(0.0025)


def test_global_x_connector_resolves_directory_isin_and_product_page():
    enrichment._GLOBAL_X_CACHE.clear()
    directory = r'''<script>self.__next_f.push([1,
      "{\"ETF_NAME\":\"Copper Miners UCITS ETF\",\"PRIMARY_TICKER\":\"COPX\",
      \"PRIMARY_ISIN\":\"IE0003Z9E2Y3\"}"])</script>'''
    product = """
      <html><body>Primary ISIN IE0003Z9E2Y3
      Management Style Physical - Full Replication - Passively Managed
      Underlying Index Solactive Global Copper Miners v2 Index
      Total Expense Ratio 0.55%</body></html>
    """

    def handler(request):
        return httpx.Response(
            200,
            text=product if "/funds/copx/" in str(request.url) else directory,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = _fetch_global_x(client, "IE0003Z9E2Y3")

    assert result and result["replication"] == "physical"
    assert result["management_fee_rate"] == pytest.approx(0.0055)


def test_global_x_connector_reads_full_official_holdings_table():
    enrichment._GLOBAL_X_CACHE.clear()
    directory = r'''{"ETF_NAME":"Cybersecurity UCITS ETF","PRIMARY_TICKER":"BUG",
      "PRIMARY_ISIN":"IE00BMH5Y871"}'''
    product = """
      <html><body>Primary ISIN IE00BMH5Y871
      Management Style Physical - Full Replication - Passively Managed
      Underlying Index Indxx Cybersecurity v2 Index
      <table><tr><th>Ticker</th><th>Name</th><th>Weight</th></tr>
      <tr><td>AAA</td><td>Alpha</td><td>55%</td></tr>
      <tr><td>BBB</td><td>Beta</td><td>45%</td></tr></table></body></html>
    """

    def handler(request):
        return httpx.Response(
            200,
            text=product if "/funds/bug/" in str(request.url) else directory,
        )

    result = _fetch_global_x(
        httpx.Client(transport=httpx.MockTransport(handler)),
        "IE00BMH5Y871",
    )

    assert result["index_name"] == "Indxx Cybersecurity v2 Index"
    assert sum(item["weight"] for item in result["holdings"]) == pytest.approx(1.0)


def test_franklin_connector_resolves_sitemap_isin_and_product_page():
    enrichment._FRANKLIN_CACHE.clear()
    product_url = (
        "https://www.franklintempleton.co.uk/our-funds/etf/price-and-performance/"
        "products/40163/SINGLCLASS/franklin-ftse-emerging-markets-ucits-etf/"
        "IE000GTF7GF4"
    )
    sitemap = (
        '<?xml version="1.0"?><urlset><url><loc>'
        f"{product_url}</loc></url>"
        "<url><loc>https://www.franklintempleton.co.uk/our-funds/price-and-performance/"
        "products/1/A/not-an-etf/LU0000000001</loc></url></urlset>"
    )
    product = """
      <html><body>ISIN Code IE000GTF7GF4
      Underlying Index FTSE Emerging Index-NR
      Methodology Optimised Product Structure Physical
      Total Expense Ratio 0.19%</body></html>
    """
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        url = str(request.url)
        if "en-gb_product.xml" in url:
            return httpx.Response(200, text=sitemap)
        if "/ETA/" in url:
            assert request.headers["user-agent"].startswith("Googlebot/")
            return httpx.Response(200, text=product)
        return httpx.Response(200, text="<html><body>Angular shell</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = _fetch_franklin(client, "IE000GTF7GF4")
    second = _fetch_franklin(client, "IE000GTF7GF4")

    assert first and first["replication"] == "physical"
    assert first["index_name"] == "FTSE Emerging Index-NR"
    assert first["management_fee_rate"] == pytest.approx(0.0019)
    assert second and second["replication"] == "physical"
    # un sitemap en cache +, par résolution SINGLCLASS -> ETA, la requête
    # GraphQL ProductLookup des positions complètes (l'endpoint non mocké
    # répond une coquille Angular qui fait échouer le JSON sans planter).
    assert calls == 7


def test_every_optimization_can_resume_all_unknown_replications(tmp_path, monkeypatch):
    path = tmp_path / "indices.json"
    broker = _broker(
        {
            "Ticker Yahoo Finance": "SWAP.PA",
            "ISIN": "FR001400U5Q4",
            "Nom": "Amundi S&P 500 Swap UCITS ETF",
            "Indice": "S&P 500",
            "Réplication": "",
        },
        {
            "Ticker Yahoo Finance": "NET.DE",
            "ISIN": "IE00B4L5Y983",
            "Nom": "iShares Test UCITS ETF",
            "Indice": "Test Index",
            "Réplication": "",
        },
    )
    attempted = []
    progress = []

    def fake_enrich(tickers, *, broker_table, path, progress_cb):
        attempted.extend(tickers)
        registry = json.loads(path.read_text(encoding="utf-8"))
        registry["funds"]["ISIN:IE00B4L5Y983"]["replication"] = "physical"
        path.write_text(json.dumps(registry), encoding="utf-8")
        progress_cb(0, len(tickers), tickers[0])
        progress_cb(len(tickers), len(tickers), "")
        return {"NET.DE": {"status": "metadata_complete"}}

    monkeypatch.setattr(enrichment, "enrich_official_etfs", fake_enrich)

    diagnostics = enrich_unknown_etf_replications(
        {"SWAP.PA", "NET.DE"},
        broker_table=broker,
        path=path,
        progress_cb=lambda done, total, ticker: progress.append((done, total, ticker)),
    )

    assert attempted == ["NET.DE"]
    assert diagnostics["known_before"] == 1
    assert diagnostics["unknown_before"] == 1
    assert diagnostics["resolved_now"] == 1
    assert diagnostics["unknown_after"] == 0
    assert progress == [(0, 1, "NET.DE"), (1, 1, "")]


def test_recent_unknown_replication_is_not_walked_again(tmp_path, monkeypatch):
    from app.services.finance.buffett.etf_index_registry import resolve_index_registry

    path = tmp_path / "indices.json"
    broker = _broker({
        "Ticker Yahoo Finance": "UNKNOWN.DE",
        "ISIN": "IE00B4L5Y983",
        "Nom": "Unknown Issuer Test UCITS ETF",
        "Indice": "Test Index",
        "Réplication": "",
    })
    resolve_index_registry(
        ["UNKNOWN.DE"],
        broker_table=broker,
        path=path,
    )
    registry = json.loads(path.read_text(encoding="utf-8"))
    fund = next(iter(registry["funds"].values()))
    fund["official_enrichment"] = {
        "status": "unsupported_issuer",
        "last_attempt_at": dt.date.today().isoformat(),
    }
    path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        enrichment,
        "enrich_official_etfs",
        lambda *_args, **_kwargs: pytest.fail("un échec récent ne doit pas être reparcouru"),
    )

    diagnostics = enrich_unknown_etf_replications(
        {"UNKNOWN.DE"},
        broker_table=broker,
        path=path,
    )

    assert diagnostics["due_now"] == 0
    assert diagnostics["cached_recent"] == 1
    assert diagnostics["unknown_after"] == 1


def test_physical_issuer_page_fills_only_its_own_fund_composition(tmp_path):
    path = tmp_path / "indices.json"
    broker = _broker({
        "Ticker Yahoo Finance": "ONE.PA",
        "ISIN": "FR001400U5Q4",
        "Nom": "Amundi CAC 40 UCITS ETF",
        "Indice": "CAC 40",
        "Réplication": "Physique",
    })
    html = """
      <html><body>ISIN FR001400U5Q4 Benchmark Index CAC 40
      Product Structure Physical ISIN FR001400U5Q4
      <table><tr><th>Ticker</th><th>Name</th><th>ISIN</th><th>Weight (%)</th></tr>
      <tr><td>AAA</td><td>A</td><td>FR0000000010</td><td>50</td></tr>
      <tr><td>BBB</td><td>B</td><td>FR0000000020</td><td>45</td></tr></table>
      </body></html>
    """
    client = httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, text=html)
    ))

    result = enrich_official_etfs(
        {"ONE.PA"}, broker_table=broker, path=path, client=client,
    )

    assert result["ONE.PA"]["status"] == "complete"
    stored = json.loads(path.read_text(encoding="utf-8"))
    composition = stored["funds"]["ISIN:FR001400U5Q4"]["composition"]
    assert composition["source"] == "issuer_fund_holdings"
    assert composition["coverage"] == 0.95
    assert len(composition["holdings"]) == 2
    assert "composition" not in stored["indices"]["CAC-40"]


def test_another_issuer_reuses_index_cache_without_http_request(tmp_path):
    path = tmp_path / "indices.json"
    path.write_text(json.dumps({
        "version": 1,
        "funds": {},
        "indices": {
            "CAC-40": {
                "name": "CAC 40",
                "funds": [],
                "composition": {
                    "source": "official_index_constituents",
                    "source_url": "https://official.example/cac40",
                    "updated_at": dt.date.today().isoformat(),
                    "coverage": 1.0,
                    "holdings": [{"ticker": "AAA", "weight": 1.0}],
                },
            },
        },
    }), encoding="utf-8")
    broker = _broker({
        "Ticker Yahoo Finance": "TWO.DE",
        "ISIN": "DE0000000002",
        "Nom": "iShares CAC 40 UCITS ETF",
        "Indice": "CAC 40",
        "Réplication": "Synthétique",
        "TER": "0.20%",
    })

    def forbidden(_request):
        raise AssertionError("aucune requête émetteur ne devait être faite")

    client = httpx.Client(transport=httpx.MockTransport(forbidden))
    result = enrich_official_etfs(
        {"TWO.DE"}, broker_table=broker, path=path, client=client,
    )

    assert result["TWO.DE"]["status"] == "complete_shared_index"
    assert result["TWO.DE"]["shared_index_id"] == "CAC-40"


def test_state_street_spreadsheet_columns_are_normalized():
    frame = pd.DataFrame([
        ["Fund Name:", "Example"],
        ["ISIN", "Security Name", "Percent of Fund", "Trade Country Name", "Sector Classification"],
        ["US0000000001", "Large", 7.5, "United States", "Technology"],
        ["US0000000002", "Small", 0.25, "United States", "Industrials"],
    ])

    holdings = _holdings_from_frame(frame)

    assert [item["weight"] for item in holdings] == [0.075, 0.0025]
    assert holdings[0]["country"] == "United States"
    assert holdings[1]["sector"] == "Industrials"


def test_kraneshares_csv_columns_are_normalized():
    frame = pd.DataFrame([
        ["Rank", "Company Name", "% of Net Assets", "Ticker", "Identifier"],
        [1, "Company A", 8.5, 688012, "CNE100003MM9"],
        [2, "Cash", 0.2, "", "–"],
    ])

    holdings = _holdings_from_frame(frame)

    assert holdings == [{
        "ticker": "688012",
        "isin": "CNE100003MM9",
        "name": "Company A",
        "weight": 0.085,
        "country": "",
        "sector": "",
    }]


def test_vanguard_discovers_port_id_from_official_isin(monkeypatch):
    from app.services.finance.buffett import official_etf_enrichment as enrichment
    monkeypatch.setattr(enrichment, "_VANGUARD_DIRECTORY_CACHE", {})
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, text='{"portIds":"9679,E001"}')
        payload = json.loads(request.content)
        assert request.headers["X-Consumer-ID"] == "uk2"
        if "9679" not in payload["variables"]["portIds"]:
            return httpx.Response(200, json={"data": {"funds": []}})
        return httpx.Response(200, json={"data": {"funds": [{
            "portId": "9679",
            "profile": {
                "portId": "9679",
                "fundFullName": "Vanguard FTSE All-World UCITS ETF",
                "identifiers": [{
                    "altIdCode": "ISIN",
                    "altIdValue": "IE00BK5BQT80",
                }],
            },
        }]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = _discover_vanguard_port_id(client, "IE00BK5BQT80")

    assert result is not None
    assert result["port_id"] == "9679"


def test_vanguard_fetches_all_official_holdings_pages():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        last_key = payload["variables"]["lastItemKey"]
        rows = [{
            "issuerName": "Company A" if last_key is None else "Company B",
            "securityLongDescription": "Company A" if last_key is None else "Company B",
            "gicsSectorDescription": "Technology" if last_key is None else "Financials",
            "marketValuePercentage": 60 if last_key is None else 40,
            "ticker": "AAA" if last_key is None else "BBB",
            "securityType": "EQ.STOCK",
            "effectiveDate": "2026-07-31",
            "bloombergIsoCountry": "US" if last_key is None else "GB",
        }]
        return httpx.Response(200, json={"data": {
            "funds": [{"profile": {
                "fundFullName": "Vanguard Test ETF",
                "assetClassificationLevel1": "Equity",
                "benchMarkNameFromECS": "FTSE Test Index",
                "etfReplicationMethodology": "Physical replication",
            }}],
            "borHoldings": [{"holdings": {
                "items": rows,
                "totalHoldings": 2,
                "lastItemKey": "next" if last_key is None else None,
            }}],
        }})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = _fetch_vanguard(client, "IE00BK5BQT80", product_id="9679")

    assert result is not None
    assert calls == 2
    assert result["index_name"] == "FTSE Test Index"
    assert result["replication"] == "physical"
    assert result["total_holdings"] == 2
    assert sum(item["weight"] for item in result["holdings"]) == 1.0


def test_amundi_rejects_a_full_paragraph_before_using_precise_index_pattern():
    text = (
        "Indice de référence : 100% "
        + "description très longue " * 20
        + "Données clés. The objective is to replicate the performance of "
        "the S&P 500 Index, while minimizing tracking error."
    )

    assert enrichment._amundi_index_name(text) == "S&P 500 Index"


def test_amundi_reads_explicit_english_benchmark_field():
    text = (
        "BOND FACTSHEET Benchmark :J.P. Morgan GBI Global Total Return Index "
        "Level Unhedged EUR Key Information (Source: Amundi) Objective and "
        "Investment Policy"
    )

    assert enrichment._amundi_index_name(text) == (
        "J.P. Morgan GBI Global Total Return Index Level Unhedged EUR"
    )


def test_amundi_api_keeps_only_economic_holdings_for_physical_proxy():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["productIds"] == ["IE000PEAJOT0"]
        return httpx.Response(200, json={"products": [{
            "characteristics": {
                "ISIN": "IE000PEAJOT0",
                "FUND_REPLICATION_METHODOLOGY": "Direct(Physical)",
                "BENCHMARK_NAME": "MSCI USA ESG Selection",
                "POSITION_AS_OF_DATE": "2026-08-26",
            },
            "composition": {"compositionData": [
                {"weight": 0.98, "compositionCharacteristics": {
                    "type": "EQUITY_ORDINARY", "bbg": "NVDA UW",
                    "isin": "US67066G1040", "name": "NVIDIA CORP",
                    "sector": "Information Technology",
                    "countryOfRisk": "United States",
                }},
                {"weight": 0.02, "compositionCharacteristics": {
                    "type": "CASH", "bbg": "", "name": "USD CASH",
                }},
            ]},
        }]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = enrichment._fetch_amundi_holdings(client, "IE000PEAJOT0")

    assert result is not None
    assert result["replication"] == "physical"
    assert result["index_name"] == (
        "MSCI USA ESG Selection P-Series 5% Issuer Capped Index"
    )
    assert result["as_of"] == "2026-08-26"
    assert result["holdings"] == [{
        "ticker": "NVDA",
        "isin": "US67066G1040",
        "name": "NVIDIA CORP",
        "weight": 0.98,
        "country": "United States",
        "sector": "Information Technology",
        "security_type": "EQUITY_ORDINARY",
    }]


def test_amundi_api_keeps_bonds_for_a_physical_bond_fund():
    def handler(_request):
        return httpx.Response(200, json={"products": [{
            "characteristics": {
                "ISIN": "LU1737653631",
                "FUND_REPLICATION_METHODOLOGY": "Direct(Physical)",
                "BENCHMARK_NAME": "J.P. Morgan GBI Global Total Return Index",
            },
            "composition": {"compositionData": [
                {"weight": 0.99, "compositionCharacteristics": {
                    "type": "BOND", "isin": "US912810TM09",
                    "name": "US TREASURY", "countryOfRisk": "United States",
                }},
                {"weight": 0.01, "compositionCharacteristics": {
                    "type": "CASH", "name": "USD CASH",
                }},
            ]},
        }]})

    result = enrichment._fetch_amundi_holdings(
        httpx.Client(transport=httpx.MockTransport(handler)), "LU1737653631"
    )

    assert result is not None
    assert result["holdings"] == [{
        "ticker": "",
        "isin": "US912810TM09",
        "name": "US TREASURY",
        "weight": 0.99,
        "country": "United States",
        "sector": "",
        "security_type": "BOND",
    }]


def test_amundi_api_never_promotes_synthetic_collateral():
    def handler(_request):
        return httpx.Response(200, json={"products": [{
            "characteristics": {
                "ISIN": "LU1681042864",
                "FUND_REPLICATION_METHODOLOGY": "Indirect(Synthetic)",
                "BENCHMARK_NAME": "MSCI USA ESG Selection",
            },
            "composition": {"compositionData": [{
                "weight": 1.0,
                "compositionCharacteristics": {
                    "type": "EQUITY_ORDINARY", "bbg": "FAKE FP",
                },
            }]},
        }]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = enrichment._fetch_amundi_holdings(client, "LU1681042864")

    assert result is not None
    assert result["replication"] == "synthetic"
    assert result["holdings"] == []


def test_spdr_resolves_isin_and_uses_complete_download(monkeypatch):
    product_url = "https://www.ssga.com/se/en_gb/institutional/etfs/example"
    html = """
      <html><body>IE00B6YX5C33
      <table>
        <tr><td>Benchmark</td><td>S&amp;P 500 Index</td></tr>
        <tr><td>Replication Method</td><td>Replicated</td></tr>
      </table>
      <a href="/daily-holdings.xlsx">Download Daily Holdings</a>
      </body></html>
    """

    def handler(request):
        if request.url.path.endswith("/suggest"):
            return httpx.Response(200, json={"suggests": {"Investments": [{"link": product_url}]}})
        if str(request.url) == product_url:
            return httpx.Response(200, text=html)
        raise AssertionError(str(request.url))

    expected = [{"isin": "US0000000001", "ticker": "", "name": "A", "weight": 1.0}]
    monkeypatch.setattr(enrichment, "_download_table", lambda _http, _url: expected)
    client = httpx.Client(transport=httpx.MockTransport(handler))

    result = _fetch_spdr(client, "IE00B6YX5C33")

    assert result is not None
    assert result["index_name"] == "S&P 500 Index"
    assert result["replication"] == "physical"
    assert result["holdings"] == expected


def test_ishares_local_catalog_reads_all_ajax_rows():
    product_url = "https://www.ishares.com/ch/individual/en/products/251931/x"
    ajax_url = "https://www.ishares.com/ch/individual/en/products/251931/holdings.ajax"
    html = """
      <html><body>DE0002635307
      <div class="product-data-item col-indexSeriesName"><div class="data">STOXX Europe 600</div></div>
      <div class="product-data-item col-productStructure"><div class="data">Physical</div></div>
      <div class="product-data-item col-assetClass"><div class="data">Equity</div></div>
      <div id="allHoldingsTab" data-ajaxuri="/ch/individual/en/products/251931/holdings.ajax"></div>
      </body></html>
    """
    rows = [
        ["AAA", "Company A", "Technology", "Equity", {}, {"raw": 60}, {}, {}, "FR0000000001", {}, "France"],
        ["BBB", "Company B", "Financials", "Equity", {}, {"raw": 39}, {}, {}, "DE0000000002", {}, "Germany"],
        ["EUR", "Cash", "Cash", "Cash", {}, {"raw": 1}, {}, {}, "-", {}, "European Union"],
    ]

    def handler(request):
        if str(request.url) == product_url:
            return httpx.Response(200, text=html)
        if str(request.url) == ajax_url:
            return httpx.Response(200, json={"aaData": rows})
        if "component=fundHeader" in str(request.url):
            return httpx.Response(200, json={"componentsByNameMap": {}})
        raise AssertionError(str(request.url))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = _fetch_ishares_page(client, {
        "url": "/ishares-ch/individual/en/products/251931/",
        "portfolioId": "251931",
    }, "DE0002635307")

    assert result is not None
    assert result["replication"] == "physical"
    assert sum(item["weight"] for item in result["holdings"]) == 0.99
    assert result["holdings"][0]["country"] == "France"
def test_temporary_enrichment_errors_are_retried_the_next_day(monkeypatch):
    import datetime as dt

    from app.services.finance.buffett import official_etf_enrichment as enrichment

    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    record = {
        "name": "Invesco ETF",
        "official_enrichment": {
            "status": "temporary_error", "last_attempt_at": yesterday,
        },
    }
    assert enrichment._attempt_due(record, force=False) is True
