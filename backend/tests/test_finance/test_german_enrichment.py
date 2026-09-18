"""Tests des fonctions pures d'enrichissement des instruments allemands."""
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.services.finance.buffett import german_enrichment as ge


def _write_official(tmp_path, name, rows):
    # Reproduit le format Deutsche Börse : 2 lignes d'en-tête ignorées puis header ';'
    p = tmp_path / name
    header = "Instrument;ISIN;WKN;Mnemonic;Instrument Type"
    body = "\n".join(";".join(r) for r in rows)
    p.write_text(f"Market:;X\nDate:;01.01.2026\n{header}\n{body}\n", encoding="latin-1")
    return str(p)


# ── Task 1 ────────────────────────────────────────────────────────────────
def test_load_and_classify_etf_and_stock_and_drop(tmp_path):
    xetra = _write_official(tmp_path, "x.csv", [
        ["ISHARES CORE MSCI WORLD", "IE00B4L5Y983", "A0RPWH", "EUNL", "ETF"],
        ["SAP SE", "DE0007164600", "716460", "SAP", "CS"],
        ["SOME BOND 5%", "DE000BONDXXX", "BONDXX", "BND1", "BOND"],
    ])
    frankfurt = _write_official(tmp_path, "f.csv", [
        ["APPLE INC.", "US0378331005", "865985", "APC", "CS"],
    ])
    xm, fm = ge.load_official_maps(xetra, frankfurt)
    assert xm["EUNL"].instrument_type == "ETF"
    assert fm["APC"].isin == "US0378331005"

    etf = ge.classify_ticker("EUNL.DE", xm, fm)
    assert etf.is_etf and etf.kind == "Tracker/ETF" and etf.market == "Xetra"
    assert etf.isin == "IE00B4L5Y983"
    assert etf.secteur2 == "Actions"  # MSCI World -> classe actions
    assert etf.secteur4 == "Monde"

    stock = ge.classify_ticker("SAP.DE", xm, fm)
    assert not stock.is_etf and stock.kind == "Action" and stock.secteur2 == "Actions"

    apple = ge.classify_ticker("APC.F", xm, fm)
    assert apple.kind == "Action" and apple.market == "Börse Frankfurt"

    assert ge.classify_ticker("BND1.DE", xm, fm) is None      # BOND écarté
    assert ge.classify_ticker("ZZZZ.DE", xm, fm) is None      # non apparié


# ── Task 2 ────────────────────────────────────────────────────────────────
def test_parse_quote_response_and_chunk():
    payload = {"quoteResponse": {"result": [
        {"symbol": "EUNL.DE", "quoteType": "ETF", "regularMarketPrice": 126.0,
         "currency": "EUR", "longName": "iShares Core MSCI World"},
        {"symbol": "SAP.DE", "quoteType": "EQUITY", "regularMarketPrice": 132.0,
         "currency": "EUR", "shortName": "SAP SE"},
    ]}}
    q = ge.parse_quote_response(payload)
    assert set(q) == {"EUNL.DE", "SAP.DE"}
    assert q["EUNL.DE"].quote_type == "ETF" and q["EUNL.DE"].price == 126.0
    assert q["SAP.DE"].long_name == "SAP SE"  # repli shortName
    assert list(ge.chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


class _FakeResp:
    status_code = 200

    def __init__(self, syms):
        self._syms = syms

    def json(self):
        return {"quoteResponse": {"result": [
            {"symbol": s, "quoteType": "ETF", "regularMarketPrice": 1.0,
             "currency": "EUR", "longName": s} for s in self._syms if s != "BAD.DE"]}}


class _FakeSession:
    def get(self, url, params=None, **kw):
        if "getcrumb" in url:
            r = _FakeResp([])
            r.text = "crumbXYZ"
            return r
        syms = (params or {}).get("symbols", "").split(",")
        return _FakeResp(syms)


def test_probe_symbols_drops_unresolved():
    q = ge.probe_symbols(["EUNL.DE", "BAD.DE", "SAP.DE"],
                         session=_FakeSession(), chunk_size=2)
    assert set(q) == {"EUNL.DE", "SAP.DE"}   # BAD.DE non résolu -> absent


# ── Task 3 ────────────────────────────────────────────────────────────────
def test_build_rows_etf_stock_and_invalid():
    kept = [
        ge.Classified("EUNL.DE", "Tracker/ETF", True, "IE00B4L5Y983",
                      "iShares Core MSCI World", "Xetra", "ETF",
                      "Actions", "Diversifié", "Monde", ""),
        ge.Classified("SAP.DE", "Action", False, "DE0007164600",
                      "SAP SE", "Xetra", "CS", "Actions", "", "", ""),
        ge.Classified("GHOST.DE", "Action", False, "DE000GHOST0",
                      "Ghost AG", "Xetra", "CS", "Actions", "", "", ""),
    ]
    quotes = {
        "EUNL.DE": ge.Quote("EUNL.DE", "ETF", 126.0, "EUR", "iShares Core MSCI World"),
        "SAP.DE": ge.Quote("SAP.DE", "EQUITY", 132.0, "EUR", "SAP SE"),
        # GHOST.DE absent -> invalide
    }
    existing = {"SAP SE": ("Technology", "Technologie")}
    rows, invalid = ge.build_rows(kept, quotes, existing)
    assert invalid == ["GHOST.DE"]
    by_t = {r["Ticker Yahoo Finance"]: r for r in rows}
    assert set(by_t) == {"EUNL.DE", "SAP.DE"}
    assert by_t["EUNL.DE"]["Secteur 1"] == "ETF"
    assert by_t["EUNL.DE"]["Secteur 4"] == "Monde"
    assert by_t["EUNL.DE"]["ISIN"] == "IE00B4L5Y983"
    assert by_t["EUNL.DE"]["Prix"] == 126.0
    # action : secteur GICS recopié du doublon exact de nom
    assert by_t["SAP.DE"]["Secteur"] == "Technology"
    assert by_t["SAP.DE"]["Secteur 1"] == "Technologie"
    assert by_t["SAP.DE"]["Secteur 2"] == "Actions"


# ── Task 4 ────────────────────────────────────────────────────────────────
def test_write_tickers_csv_updates_and_drops(tmp_path):
    p = tmp_path / "tickers.csv"
    p.write_text("EUNL.DE;;;\nSAP.DE;;;\nBOND1.DE;;;\nAAPL;Apple;Nasdaq;Action\n",
                 encoding="utf-8")
    n_maj, n_del = ge.write_tickers_csv(
        str(p),
        kind_by_ticker={"EUNL.DE": ("Xetra", "Tracker/ETF"),
                        "SAP.DE": ("Xetra", "Action")},
        drop={"BOND1.DE"},
    )
    assert (n_maj, n_del) == (2, 1)
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
    rows = dict((l.split(";")[0], l.split(";")) for l in lines)
    assert "BOND1.DE" not in rows
    assert rows["EUNL.DE"][2] == "Xetra" and rows["EUNL.DE"][3] == "Tracker/ETF"
    assert rows["AAPL"][3] == "Action"          # ligne non allemande intacte
    backup_dir = Path(settings.backup_dir) / "files" / "runtime" / "finance-buffett"
    assert any(backup_dir.glob("tickers.csv.bak-*"))


def test_upsert_toutbroker_preserves_and_upserts(tmp_path):
    p = tmp_path / "ToutBroker.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        pd.DataFrame({"Ticker Yahoo Finance": ["EUNL.DE", "OLD.DE"],
                      "Nom": ["old name", "keep"],
                      "Secteur 1": ["", ""]}).to_excel(w, sheet_name="Sheet1", index=False)
        pd.DataFrame({"x": [1]}).to_excel(w, sheet_name="ETF_Pays", index=False)
    n = ge.upsert_toutbroker(str(p), [
        {"Ticker Yahoo Finance": "EUNL.DE", "Nom": "iShares Core MSCI World",
         "Secteur 1": "ETF"},
        {"Ticker Yahoo Finance": "SAP.DE", "Nom": "SAP SE", "Secteur 1": "Technologie"},
    ])
    assert n == 2
    xls = pd.ExcelFile(p)
    assert "ETF_Pays" in xls.sheet_names          # feuille préservée
    df = pd.read_excel(p, sheet_name="Sheet1")
    idx = df.set_index("Ticker Yahoo Finance")
    assert idx.loc["EUNL.DE", "Secteur 1"] == "ETF"     # existant mis à jour
    assert idx.loc["EUNL.DE", "Nom"] == "iShares Core MSCI World"
    assert idx.loc["SAP.DE", "Nom"] == "SAP SE"          # nouveau ajouté
    assert "OLD.DE" in idx.index                          # ligne existante conservée
