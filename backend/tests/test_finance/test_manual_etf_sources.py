import datetime as dt

import pandas as pd

from app.services.finance.buffett.manual_etf_sources import (
    INPUT_COLUMNS,
    INPUT_SHEET,
    STATUS_SHEET,
    ensure_manual_sheets,
    manual_physical_proxy,
    merge_manual_etfs,
)


def test_manual_sheet_adds_an_etf_without_constituent_rows(tmp_path):
    workbook = tmp_path / "etf.xlsx"
    row = {column: "" for column in INPUT_COLUMNS}
    row.update({
        "Actif": "VRAI", "ETF_ISIN": "FR0013411980",
        "ETF_Ticker": "PTPXE.PA", "Nom": "Amundi PEA Japon TOPIX",
        "MIC": "XPAR", "BoursDirect2": "VRAI", "Indice": "TOPIX",
        "Replication_declaree": "synthetic",
        "Mode_Composition": "SOURCE_OFFICIELLE",
        "URL_Composition": "https://example.com/topix.csv",
    })
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([{"Ticker Yahoo Finance": "CW8.PA"}]).to_excel(
            writer, sheet_name="ETF", index=False,
        )
        pd.DataFrame([row]).to_excel(writer, sheet_name=INPUT_SHEET, index=False)

    merged = merge_manual_etfs(
        pd.DataFrame([{"Ticker Yahoo Finance": "CW8.PA"}]), workbook,
    ).set_index("Ticker Yahoo Finance")

    assert merged.loc["PTPXE.PA", "ISIN"] == "FR0013411980"
    assert merged.loc["PTPXE.PA", "Secteur 1"] == "ETF"
    assert bool(merged.loc["PTPXE.PA", "BoursDirect2"]) is True
    assert "constituent" not in " ".join(INPUT_COLUMNS).casefold()


def test_manual_sheets_are_created_without_replacing_input(tmp_path):
    workbook = tmp_path / "etf.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame([{"Ticker Yahoo Finance": "CW8.PA"}]).to_excel(
            writer, sheet_name="ETF", index=False,
        )
        pd.DataFrame([{"Actif": "VRAI", "ETF_Ticker": "PTPXE.PA"}]).to_excel(
            writer, sheet_name=INPUT_SHEET, index=False,
        )

    ensure_manual_sheets(workbook)

    assert pd.read_excel(workbook, sheet_name=INPUT_SHEET).iloc[0]["ETF_Ticker"] == "PTPXE.PA"
    assert STATUS_SHEET in pd.ExcelFile(workbook).sheet_names


def test_named_proxy_must_be_physical_and_follow_exact_index(tmp_path):
    today = dt.date.today().isoformat()
    registry = {
        "_storage_path": str(tmp_path / "registry.json"),
        "indices": {"TOPIX": {"name": "TOPIX"}},
        "funds": {
            "ISIN:FR0013411998": {
                "isin": "FR0013411998", "tickers": ["PTOJ.PA"],
                "replication": "physical", "index_name": "TOPIX",
                "composition": {
                    "source": "issuer_fund_holdings", "updated_at": today,
                    "coverage": 1.0, "source_url": "https://issuer.test/holdings.csv",
                    "holdings": [{"ticker": "7203.T", "weight": 1.0,
                                  "sector": "Transportation Equipment", "country": "Japan"}],
                },
            }
        },
    }
    route = {
        "Mode_Composition": "PROXY_PHYSIQUE", "Proxy_ISIN": "FR0013411998",
        "Proxy_Ticker": "PTOJ.PA", "URL_Composition": "https://issuer.test/holdings.csv",
        "Indice": "TOPIX",
    }

    result = manual_physical_proxy(
        "PTPXE.PA", {"index_name": "TOPIX", "replication": "synthetic"},
        registry, route,
    )

    assert result["source"] == "manual_physical_tracker_proxy"
    assert result["proxy_isin"] == "FR0013411998"
    assert len(result["holdings"]) == 1
