from __future__ import annotations

import io

import pandas as pd

from app.services.finance.buffett.etf_index_registry import (
    cached_index_composition,
    load_registry,
    save_registry,
)
from app.services.finance.buffett.official_index_enrichment import (
    _holdings_from_ftse_text,
    _response_json,
    detect_index_provider,
    enrich_official_indices,
    holdings_from_weight_frame,
)


class _Response:
    def __init__(
        self,
        url: str,
        *,
        text: str = "",
        content: bytes | None = None,
        status_code: int = 200,
    ):
        self.url = url
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = {}
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        import json

        return json.loads(self.text)


class _Client:
    def __init__(self, responses: dict[str, _Response]):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        if kwargs.get("params"):
            url = f"{url}?s={kwargs['params']['s']}"
        self.calls.append(url)
        return self.responses[url]


def _registry(path, index_id: str, name: str):
    save_registry(
        {
            "version": 2,
            "funds": {},
            "indices": {index_id: {"name": name, "funds": []}},
        },
        path,
    )


def test_provider_detection_is_conservative():
    assert detect_index_provider("MSCI World Net Return") == "msci"
    assert detect_index_provider("EURO STOXX Quality Dividend") == "stoxx"
    assert detect_index_provider("TOPIX") == "jpx"
    assert detect_index_provider("Nikkei 225") == "nikkei"
    assert detect_index_provider("Solactive Water Index") == "solactive"
    assert detect_index_provider("FTSE All-World") == "ftse_russell"
    assert detect_index_provider("ICE U.S. Treasury 1-3 Year Bond Index") == "ice"
    assert detect_index_provider("Markit iBoxx EUR Liquid High Yield") == "iboxx"
    assert detect_index_provider("J.P. Morgan EMBI Global Core Index") == "jpmorgan"
    assert detect_index_provider("Morningstar Global Wide Moat") == "morningstar"
    assert detect_index_provider("BNP Paribas Quality Europe (EUR) NR") == "bnp"
    assert detect_index_provider("Global Equity Basket") == "unknown"


def test_official_json_accepts_mislabeled_windows_1252_payload():
    response = _Response(
        "https://www.lseg.com/catalog.json",
        content=b'{"Data":[{"IndexName":"FTSE\xa0World"}]}',
    )

    assert _response_json(response)["Data"][0]["IndexName"] == "FTSE\u00a0World"


def test_weight_frame_requires_at_least_ninety_percent():
    complete = pd.DataFrame(
        {"ISIN": ["A", "B"], "Name": ["A", "B"], "Weight": [60.0, 40.0]}
    )
    partial = pd.DataFrame(
        {"ISIN": ["A", "B"], "Name": ["A", "B"], "Weight": [20.0, 10.0]}
    )

    assert [row["weight"] for row in holdings_from_weight_frame(complete)] == [0.6, 0.4]
    assert holdings_from_weight_frame(partial) == []


def test_licensed_provider_is_recorded_without_scraping(tmp_path):
    path = tmp_path / "indices.json"
    _registry(path, "MSCI-WORLD", "MSCI World")
    client = _Client({})

    result = enrich_official_indices(["MSCI-WORLD"], path=path, client=client)

    assert result["MSCI-WORLD"]["status"] == "licence_required"
    assert result["MSCI-WORLD"]["provider"] == "msci"
    assert client.calls == []
    stored = load_registry(path)["indices"]["MSCI-WORLD"]
    assert stored["official_enrichment"]["status"] == "licence_required"


def test_unknown_cached_provider_is_redetected_from_exact_index_name(tmp_path):
    path = tmp_path / "indices.json"
    save_registry(
        {
            "version": 2,
            "funds": {},
            "indices": {
                "JPM-EMBI": {
                    "name": "J.P. Morgan EMBI Global Core Index",
                    "provider": "unknown",
                    "funds": [],
                }
            },
        },
        path,
    )

    result = enrich_official_indices(
        ["JPM-EMBI"], path=path, client=_Client({}), force=True
    )

    assert result["JPM-EMBI"]["status"] == "licence_required"
    assert result["JPM-EMBI"]["provider"] == "jpmorgan"


def test_index_enrichment_reports_each_item_and_completion(tmp_path):
    path = tmp_path / "indices.json"
    _registry(path, "MSCI-WORLD", "MSCI World")
    events = []

    enrich_official_indices(
        ["MSCI-WORLD"],
        path=path,
        client=_Client({}),
        progress_cb=lambda done, total, item: events.append((done, total, item)),
    )

    assert events == [(0, 1, "MSCI-WORLD"), (1, 1, "")]


def test_topix_is_downloaded_once_and_stored_by_exact_index(tmp_path):
    path = tmp_path / "indices.json"
    _registry(path, "TOPIX", "TOPIX")
    buffer = io.BytesIO()
    pd.DataFrame(
        {
            "Local Code": [7203, 6758],
            "Name": ["Toyota", "Sony"],
            "Weight": [60.0, 40.0],
        }
    ).to_excel(buffer, index=False)
    page = "<a href='/files/topix_weight.xlsx'>TOPIX Component Stocks Weight</a>"
    client = _Client(
        {
            "https://www.jpx.co.jp/english/markets/indices/topix/": _Response(
                "https://www.jpx.co.jp/english/markets/indices/topix/", text=page
            ),
            "https://www.jpx.co.jp/files/topix_weight.xlsx": _Response(
                "https://www.jpx.co.jp/files/topix_weight.xlsx", content=buffer.getvalue()
            ),
        }
    )

    first = enrich_official_indices(["TOPIX"], path=path, client=client)
    second = enrich_official_indices(["TOPIX"], path=path, client=client)

    assert first["TOPIX"]["status"] == "complete"
    assert second["TOPIX"]["status"] == "complete_cached"
    assert len(client.calls) == 2
    composition = cached_index_composition("TOPIX", path=path)
    assert composition is not None
    assert composition["provider"] == "jpx"
    assert composition["holdings"][0]["ticker"] == "7203.T"
    assert sum(row["weight"] for row in composition["holdings"]) == 1.0


def test_stoxx_uses_exact_catalog_name_and_close_composition(tmp_path):
    path = tmp_path / "indices.json"
    _registry(path, "EURO-STOXX-QUALITY-DIVIDEND", "EURO STOXX Quality Dividend")
    landing_url = "https://www.stoxx.com/data-vendor-codes"
    catalog_url = "https://www.stoxx.com/files/index_reports_links.csv"
    close_url = "https://www.stoxx.com/files/close_quality.csv"
    landing = f"<a href='{catalog_url}'>Index Reports Links CSV</a>"
    catalog = (
        "Symbol;ISIN;Index Full Name;Close Composition\n"
        "QDIV;CH0000000001;EURO STOXX Quality Dividend;"
        f"{close_url}\n"
    )
    close = (
        "ISIN;Instrument_Name;Country;Sector;Weight\n"
        "FR0001;AXA;France;Financial Services;55\n"
        "DE0001;Munich Re;Germany;Financial Services;45\n"
    )
    client = _Client(
        {
            landing_url: _Response(landing_url, text=landing),
            catalog_url: _Response(catalog_url, text=catalog),
            close_url: _Response(close_url, text=close),
        }
    )

    result = enrich_official_indices(
        ["EURO-STOXX-QUALITY-DIVIDEND"], path=path, client=client
    )

    assert result["EURO-STOXX-QUALITY-DIVIDEND"]["status"] == "complete"
    stored = load_registry(path)["indices"]["EURO-STOXX-QUALITY-DIVIDEND"]
    assert stored["provider_index_id"] == "QDIV"
    assert stored["index_isin"] == "CH0000000001"
    assert stored["composition"]["coverage"] == 1.0


def test_stoxx_accepts_return_variants_with_one_main_constituent_set(tmp_path):
    path = tmp_path / "indices.json"
    name = "STOXX Europe 600 Industry Industrials 30-15 Index"
    _registry(path, "STOXX-INDUSTRIALS-30-15", name)
    landing_url = "https://www.stoxx.com/data-vendor-codes"
    catalog_url = "https://www.stoxx.com/files/index_reports_links.csv"
    close_url = "https://www.stoxx.com/files/close_industrials.csv"
    landing = f"<a href='{catalog_url}'></a>"
    catalog = (
        "Symbol;ISIN;Index Full Name;Main Symbol;Components P000;Close Composition\n"
        "S60050CR;CH1;STOXX Europe 600 Industry Industrials 30-15;S60050CP;"
        "components_P000_s60050cp_YYYYMMDD.csv;ignored.csv\n"
        "S60050CP;CH2;STOXX Europe 600 Industry Industrials 30-15;S60050CP;"
        f"components_P000_s60050cp_YYYYMMDD.csv;{close_url}\n"
    )
    close = "ISIN;Instrument_Name;Weight\nFR1;Alpha;60\nDE1;Beta;40\n"
    client = _Client(
        {
            landing_url: _Response(landing_url, text=landing),
            catalog_url: _Response(catalog_url, text=catalog),
            close_url: _Response(close_url, text=close),
        }
    )

    result = enrich_official_indices(
        ["STOXX-INDUSTRIALS-30-15"], path=path, client=client
    )

    assert result["STOXX-INDUSTRIALS-30-15"]["status"] == "complete"
    assert result["STOXX-INDUSTRIALS-30-15"]["provider_index_id"] == "S60050CP"


def test_stoxx_records_protected_composition_instead_of_temporary_error(tmp_path):
    path = tmp_path / "indices.json"
    name = "STOXX Europe 600 Industry Consumer Staples 30-15"
    index_id = "STOXX-CONSUMER-STAPLES-30-15"
    _registry(path, index_id, name)
    landing_url = "https://www.stoxx.com/data-vendor-codes"
    catalog_url = "https://www.stoxx.com/files/index_reports_links.csv"
    close_url = "https://www.stoxx.com/files/close_staples.csv"
    catalog = (
        "Symbol;ISIN;Index Full Name;Main Symbol;Close Composition\n"
        f"S60045CP;CH1169656779;{name};S60045CP;{close_url}\n"
    )
    client = _Client(
        {
            landing_url: _Response(
                landing_url,
                text=f"<a href='{catalog_url}'>Index Reports Links CSV</a>",
            ),
            catalog_url: _Response(catalog_url, text=catalog),
            close_url: _Response(close_url, status_code=403),
        }
    )

    result = enrich_official_indices([index_id], path=path, client=client)

    assert result[index_id]["status"] == "licence_required"
    assert result[index_id]["provider_index_id"] == "S60045CP"
    stored = load_registry(path)["indices"][index_id]
    assert stored["provider_index_id"] == "S60045CP"
    assert stored["index_isin"] == "CH1169656779"


def test_bnp_public_portal_stores_complete_current_composition(tmp_path):
    path = tmp_path / "indices.json"
    index_id = "BNP-PARIBAS-QUALITY-EUROPE-EUR-NR"
    name = "BNP Paribas Quality Europe (EUR) NR"
    _registry(path, index_id, name)
    source_url = (
        "https://indx.bnpparibas.com/api/bnpp-indx/index/"
        "composition/EU_BNPIFEQE"
    )
    payload = (
        '[{"formattedCompDate":"2026-08-27","Underlying":"Alpha SA",'
        '"BbgCode":"ALP FP Equity","Weight":60},'
        '{"formattedCompDate":"2026-08-27","Underlying":"Beta AG",'
        '"BbgCode":"BET GY Equity","Weight":40}]'
    )
    client = _Client({source_url: _Response(source_url, text=payload)})

    result = enrich_official_indices([index_id], path=path, client=client)

    assert result[index_id]["status"] == "complete"
    assert result[index_id]["provider_index_id"] == "EU_BNPIFEQE"
    composition = cached_index_composition(index_id, path=path)
    assert composition is not None
    assert composition["as_of"] == "2026-08-27"
    assert composition["holdings"][0]["ticker"] == "ALP FP"


def test_bnp_identified_index_records_missing_public_composition(tmp_path):
    path = tmp_path / "indices.json"
    index_id = "BNP-PARIBAS-LOW-VOL-EUROPE-EUR-NR"
    _registry(path, index_id, "BNP Paribas Low Vol Europe (EUR) NR")
    source_url = (
        "https://indx.bnpparibas.com/api/bnpp-indx/index/"
        "composition/EU_BNPIFLVE"
    )
    # Le portail renvoie actuellement HTTP 200 avec un corps vide pour certains
    # indices identifiés mais dont le panier courant n'est pas publié.
    client = _Client({source_url: _Response(source_url, text="")})

    result = enrich_official_indices([index_id], path=path, client=client)

    assert result[index_id]["status"] == "composition_unavailable"
    assert result[index_id]["provider_index_id"] == "EU_BNPIFLVE"


def test_nikkei_225_uses_the_official_complete_weight_file(tmp_path):
    path = tmp_path / "indices.json"
    _registry(path, "NIKKEI-225", "Nikkei 225")
    source_url = (
        "https://indexes.nikkei.co.jp/nkave/archives/file/"
        "nikkei_stock_average_weight_en.csv"
    )
    weights = (
        "Code,Company Name,Sector,Weight\n"
        "9983,Fast Retailing,Consumer Goods,55\n"
        "6857,Advantest,Technology,45\n"
    )
    client = _Client({source_url: _Response(source_url, text=weights)})

    result = enrich_official_indices(["NIKKEI-225"], path=path, client=client)

    assert result["NIKKEI-225"]["status"] == "complete"
    composition = cached_index_composition("NIKKEI-225", path=path)
    assert composition is not None
    assert composition["provider"] == "nikkei"
    assert composition["holdings"][0]["ticker"] == "9983.T"


def test_ftse_pdf_text_ignores_rounded_small_weights_without_inventing_them():
    text = """
    Constituent Index weight (%) Country/Market
    Alpha Corporation 45.50 USA
    Very Long Company
    Holdings 45.00 UNITED KINGDOM
    Tiny Company <0.005 JAPAN
    Another Tiny Company
    <0.00 5 CANADA
    """

    holdings = _holdings_from_ftse_text(text)

    assert [item["name"] for item in holdings] == [
        "Alpha Corporation", "Very Long Company Holdings",
    ]
    assert sum(item["weight"] for item in holdings) == 0.905


def test_ftse_uses_exact_public_catalog_match_and_stores_composition(tmp_path):
    import json

    path = tmp_path / "indices.json"
    _registry(path, "FTSE-ALL-WORLD", "FTSE All-World Index")
    catalog_url = (
        "https://www.lseg.com/content/lseg/en_us/ftse-russell/index-resources/"
        "constituent-weights/jcr:content/root/container/page_content_region/"
        "page-content-region/section/section-fw/data_table.constituentsandweights.json"
    )
    source_url = "https://research.ftserussell.com/all-world.csv"
    catalog = {"Data": [
        {"IndexName": "FTSE All-World", "IndexId": "AWORLDS", "Url": source_url},
        {"IndexName": "FTSE All-World", "IndexId": "AWORLDS", "Url": source_url},
    ]}
    weights = "Name,Country,Weight\nCompany A,USA,60\nCompany B,Japan,40\n"
    client = _Client({
        catalog_url: _Response(catalog_url, text=json.dumps(catalog)),
        source_url: _Response(source_url, text=weights),
    })

    result = enrich_official_indices(["FTSE-ALL-WORLD"], path=path, client=client)

    assert result["FTSE-ALL-WORLD"]["status"] == "complete"
    assert result["FTSE-ALL-WORLD"]["provider_index_id"] == "AWORLDS"
    composition = cached_index_composition("FTSE-ALL-WORLD", path=path)
    assert composition is not None
    assert len(composition["holdings"]) == 2
