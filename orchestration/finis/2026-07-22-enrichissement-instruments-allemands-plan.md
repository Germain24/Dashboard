# Enrichissement des instruments allemands (Xetra + Francfurt) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classer et valider les ~27 803 tickers allemands de `tickers.csv`, remplir leur `Type`/`Marché`, et injecter les ETF + actions retenus dans `ToutBroker.xlsx` avec `Secteur 1-5`.

**Architecture :** Classification 100 % hors-ligne par jointure aux CSV officiels Deutsche Börse (mnémonique → `Instrument Type`, ISIN, nom), puis sonde Yahoo bornée (endpoint `quote` v7 groupé, crumb + `yf_session`) pour valider la résolution et récupérer prix/devise. Les fonctions pures (parsing, classification, construction de lignes) sont dans un module testable ; l'orchestration I/O (sonde, écritures, backups, rapport) est dans un script CLI.

**Tech Stack :** Python 3.13, pandas, openpyxl, `curl_cffi` via `app.services.finance.yf_session`, pytest.

## Global Constraints

- Rate-limit Yahoo : **2000 req/h lissées** — TOUJOURS passer par `yf_session()` (throttle global + rotation d'IP déjà câblés). Ne jamais contourner le throttle. Cf. mémoire `buffett-rate-limit-smoothing`.
- Source de vérité ETF/action = **`Instrument Type` officiel Deutsche Börse**, jamais le `quoteType` Yahoo (faux « ETF » sur les cotations `.F`). Cf. `etf_detect.py`.
- `Secteur 1 == "ETF"` (casse exacte, majuscules) est le signal autoritaire ETF pour l'optimiseur (`broker_availability.load_etf_tickers`). Après toute écriture de ToutBroker → `reset_etf_cache()`.
- Périmètre retenu (décision utilisateur 2026-07-22) : **ETF + ETN + ETC + CS (actions)**. On ÉCARTE BOND, FUN, OTHER, WAR et les non-appariés.
- Toute écriture d'un fichier utilisateur (`tickers.csv`, `ToutBroker.xlsx`) est précédée d'un **backup horodaté**. Les autres feuilles de ToutBroker (`ETF_Defensif`, `ETF_Pays`) sont préservées.
- `tickers.csv` : sans en-tête, séparateur `;`, colonnes `Ticker;Nom;Marché;Type`. `ToutBroker.xlsx` : colonne ticker = `Ticker Yahoo Finance`.
- Chemins (absolus depuis la racine du repo) :
  - tickers : `data/imports/Finances/variables/tickers.csv`
  - broker : `data/imports/Finances/tableur/ToutBroker.xlsx`
  - CSV officiels : `backend/.codex-xetra-instruments.csv`, `backend/.codex-frankfurt-instruments.csv` (lus avec `sep=';', skiprows=2, dtype=str, on_bad_lines='skip', encoding='latin-1'`).

---

## File Structure

- **Create** `backend/app/services/finance/buffett/german_enrichment.py` — fonctions pures + sonde (session injectable).
- **Create** `backend/scripts/enrich_german_instruments.py` — orchestration CLI (`--dry-run` / `--apply`), backups, rapport.
- **Create** `backend/tests/test_finance/test_german_enrichment.py` — tests unitaires des fonctions pures.
- **Reuse** `backend/scripts/classify_etf_sectors.py::classify` (Secteur 2-5 depuis le nom), `backend/app/services/finance/buffett/broker_availability.py` (`_save_main_sheet`, `_find_ticker_col`, `reset_etf_cache`), `app.services.finance.yf_session.yf_session`.

---

### Task 1: Chargeur d'instruments officiels + classifieur de tickers

**Files:**
- Create: `backend/app/services/finance/buffett/german_enrichment.py`
- Test: `backend/tests/test_finance/test_german_enrichment.py`

**Interfaces:**
- Produces:
  - `@dataclass Official(mnemonic, isin, name, instrument_type, market)`
  - `load_official_maps(xetra_path, frankfurt_path) -> tuple[dict[str, Official], dict[str, Official]]` — (xetra_by_mnemonic, frankfurt_by_mnemonic), clés en MAJUSCULES.
  - `@dataclass Classified(ticker, kind, is_etf, isin, official_name, market, instrument_type, secteur2, secteur3, secteur4, secteur5)`
  - `KEEP_TYPES = {"ETF","ETN","ETC","CS"}`, `ETF_TYPES = {"ETF","ETN","ETC"}`
  - `classify_ticker(ticker: str, xetra: dict, frankfurt: dict) -> Classified | None` — None si non apparié ou type hors `KEEP_TYPES`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_finance/test_german_enrichment.py
import pandas as pd
from app.services.finance.buffett import german_enrichment as ge


def _write_official(tmp_path, name, rows):
    # Reproduit le format Deutsche Börse : 2 lignes d'en-tête ignorées puis header ';'
    p = tmp_path / name
    header = "Instrument;ISIN;WKN;Mnemonic;Instrument Type"
    body = "\n".join(";".join(r) for r in rows)
    p.write_text(f"Market:;X\nDate:;01.01.2026\n{header}\n{body}\n", encoding="latin-1")
    return str(p)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -q`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError: load_official_maps`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/finance/buffett/german_enrichment.py
"""Classification hors-ligne + validation Yahoo des instruments allemands
(Xetra `.DE` / Francfurt `.F`) à partir des CSV de référence Deutsche Börse.

Voir orchestration/a-faire/2026-07-22-enrichissement-instruments-allemands-plan.md.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Réutilise la classification ETF par mots-clés du nom (Secteur 2-5).
from scripts.classify_etf_sectors import classify as _classify_etf_name

KEEP_TYPES = {"ETF", "ETN", "ETC", "CS"}
ETF_TYPES = {"ETF", "ETN", "ETC"}


@dataclass
class Official:
    mnemonic: str
    isin: str
    name: str
    instrument_type: str
    market: str  # "Xetra" | "Börse Frankfurt"


@dataclass
class Classified:
    ticker: str
    kind: str          # "Tracker/ETF" | "Action"
    is_etf: bool
    isin: str
    official_name: str
    market: str
    instrument_type: str
    secteur2: str
    secteur3: str
    secteur4: str
    secteur5: str


def _read_official(path: str, market: str) -> dict[str, Official]:
    df = pd.read_csv(path, sep=";", skiprows=2, dtype=str,
                     on_bad_lines="skip", encoding="latin-1")
    out: dict[str, Official] = {}
    for _, r in df.iterrows():
        mn = str(r.get("Mnemonic") or "").strip().upper()
        if not mn or mn == "NAN":
            continue
        out.setdefault(mn, Official(
            mnemonic=mn,
            isin=str(r.get("ISIN") or "").strip(),
            name=str(r.get("Instrument") or "").strip(),
            instrument_type=str(r.get("Instrument Type") or "").strip().upper(),
            market=market,
        ))
    return out


def load_official_maps(xetra_path: str, frankfurt_path: str):
    return (_read_official(xetra_path, "Xetra"),
            _read_official(frankfurt_path, "Börse Frankfurt"))


def _lookup(ticker: str, xetra: dict, frankfurt: dict) -> Official | None:
    tu = ticker.strip().upper()
    if tu.endswith(".DE"):
        return xetra.get(tu[:-3])
    if tu.endswith(".F"):
        base = tu[:-2]
        return frankfurt.get(base) or xetra.get(base)
    return None


def classify_ticker(ticker: str, xetra: dict, frankfurt: dict) -> Classified | None:
    off = _lookup(ticker, xetra, frankfurt)
    if off is None or off.instrument_type not in KEEP_TYPES:
        return None
    is_etf = off.instrument_type in ETF_TYPES
    if is_etf:
        s2, s3, s4, s5 = _classify_etf_name(off.name)
        kind = "Tracker/ETF"
    else:
        s2, s3, s4, s5 = "Actions", "", "", ""
        kind = "Action"
    return Classified(
        ticker=ticker.strip(), kind=kind, is_etf=is_etf, isin=off.isin,
        official_name=off.name, market=off.market,
        instrument_type=off.instrument_type,
        secteur2=s2, secteur3=s3, secteur4=s4, secteur5=s5,
    )
```

> Note : `from scripts.classify_etf_sectors import classify` suppose que `backend/` est sur le `sys.path` (cas des tests pytest lancés depuis `backend/` et du script). Si l'import échoue au runtime du script, ajouter `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` en tête du script orchestrateur (Task 5), pas dans le module.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/german_enrichment.py backend/tests/test_finance/test_german_enrichment.py
git commit -m "feat(buffett): classifieur hors-ligne des instruments allemands (Xetra/Francfurt)"
```

---

### Task 2: Sonde Yahoo groupée (crumb + quote v7)

**Files:**
- Modify: `backend/app/services/finance/buffett/german_enrichment.py`
- Test: `backend/tests/test_finance/test_german_enrichment.py`

**Interfaces:**
- Produces:
  - `@dataclass Quote(symbol, quote_type, price, currency, long_name)`
  - `chunked(seq, n) -> Iterator[list]`
  - `parse_quote_response(payload: dict) -> dict[str, Quote]`
  - `fetch_crumb(session) -> str | None`
  - `probe_symbols(symbols, session=None, chunk_size=50, sleep=0.0) -> dict[str, Quote]` — les symboles absents de la réponse sont invalides (non résolus).

- [ ] **Step 1: Write the failing test**

```python
# append to test_german_enrichment.py
from app.services.finance.buffett import german_enrichment as ge


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
    def __init__(self, syms): self._syms = syms
    def json(self):
        return {"quoteResponse": {"result": [
            {"symbol": s, "quoteType": "ETF", "regularMarketPrice": 1.0,
             "currency": "EUR", "longName": s} for s in self._syms if s != "BAD.DE"]}}


class _FakeSession:
    def get(self, url, params=None, **kw):
        if "getcrumb" in url:
            r = _FakeResp([]); r.text = "crumbXYZ"; return r
        syms = (params or {}).get("symbols", "").split(",")
        return _FakeResp(syms)


def test_probe_symbols_drops_unresolved():
    q = ge.probe_symbols(["EUNL.DE", "BAD.DE", "SAP.DE"],
                         session=_FakeSession(), chunk_size=2)
    assert set(q) == {"EUNL.DE", "SAP.DE"}   # BAD.DE non résolu -> absent
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k "quote or probe" -q`
Expected: FAIL (`AttributeError: parse_quote_response`).

- [ ] **Step 3: Write minimal implementation**

```python
# append to german_enrichment.py
import time
from collections.abc import Iterator

_QUOTE_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


@dataclass
class Quote:
    symbol: str
    quote_type: str
    price: float | None
    currency: str | None
    long_name: str | None


def chunked(seq, n: int) -> Iterator[list]:
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def parse_quote_response(payload: dict) -> dict[str, Quote]:
    res = ((payload or {}).get("quoteResponse") or {}).get("result") or []
    out: dict[str, Quote] = {}
    for r in res:
        sym = r.get("symbol")
        if not sym:
            continue
        out[sym] = Quote(
            symbol=sym,
            quote_type=str(r.get("quoteType") or ""),
            price=r.get("regularMarketPrice"),
            currency=r.get("currency"),
            long_name=r.get("longName") or r.get("shortName"),
        )
    return out


def fetch_crumb(session) -> str | None:
    try:
        session.get("https://fc.yahoo.com")
    except Exception:
        pass
    for host in _QUOTE_HOSTS:
        try:
            r = session.get(f"https://{host}/v1/test/getcrumb")
            txt = getattr(r, "text", "") or ""
            if getattr(r, "status_code", 0) == 200 and txt and "html" not in txt.lower():
                return txt.strip()
        except Exception:
            continue
    return None


def probe_symbols(symbols, session=None, chunk_size: int = 50,
                  sleep: float = 0.0) -> dict[str, Quote]:
    """Valide/typifie une liste de symboles via l'endpoint quote v7 groupé.

    Symbole absent de la réponse = non résolu par Yahoo (invalide/délisté).
    `session=None` -> `yf_session()` (throttle + rotation du projet).
    """
    if session is None:
        from app.services.finance.yf_session import yf_session
        session = yf_session()
    crumb = fetch_crumb(session)
    out: dict[str, Quote] = {}
    for batch in chunked(symbols, chunk_size):
        params = {"symbols": ",".join(batch)}
        if crumb:
            params["crumb"] = crumb
        payload = None
        for host in _QUOTE_HOSTS:
            try:
                r = session.get(f"https://{host}/v7/finance/quote", params=params)
                if getattr(r, "status_code", 0) == 401:
                    crumb = fetch_crumb(session)      # crumb périmé -> rafraîchir
                    if crumb:
                        params["crumb"] = crumb
                    r = session.get(f"https://{host}/v7/finance/quote", params=params)
                if getattr(r, "status_code", 0) == 200:
                    payload = r.json()
                    break
            except Exception:
                continue
        if payload:
            out.update(parse_quote_response(payload))
        if sleep:
            time.sleep(sleep)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k "quote or probe" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/german_enrichment.py backend/tests/test_finance/test_german_enrichment.py
git commit -m "feat(buffett): sonde Yahoo groupée (quote v7 + crumb) pour valider les tickers"
```

---

### Task 3: Construction des lignes ToutBroker + tri validité

**Files:**
- Modify: `backend/app/services/finance/buffett/german_enrichment.py`
- Test: `backend/tests/test_finance/test_german_enrichment.py`

**Interfaces:**
- Consumes: `Classified` (Task 1), `Quote` (Task 2).
- Produces:
  - `build_rows(kept: list[Classified], quotes: dict[str, Quote], existing_sector_by_name: dict[str, tuple[str, str]]) -> tuple[list[dict], list[str]]`
    → `(rows, invalid_tickers)`. `rows` = dicts prêts pour ToutBroker (clés = noms de colonnes exacts). `invalid_tickers` = retenus mais absents de `quotes`.
  - `existing_sector_map(df) -> dict[str, tuple[str, str]]` : nom normalisé → (`Secteur`, `Secteur 1`) des lignes existantes non vides (recopie best-effort du secteur GICS pour un doublon exact de nom).

- [ ] **Step 1: Write the failing test**

```python
# append to test_german_enrichment.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k build_rows -q`
Expected: FAIL (`AttributeError: build_rows`).

- [ ] **Step 3: Write minimal implementation**

```python
# append to german_enrichment.py

def _norm_name(s) -> str:
    return " ".join(str(s or "").strip().upper().split())


def existing_sector_map(df) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    if df is None or "Nom" not in df.columns:
        return out
    sec = df["Secteur"] if "Secteur" in df.columns else [None] * len(df)
    sec1 = df["Secteur 1"] if "Secteur 1" in df.columns else [None] * len(df)
    for nom, s, s1 in zip(df["Nom"], sec, sec1):
        key = _norm_name(nom)
        if not key:
            continue
        sv = "" if s is None or str(s) == "nan" else str(s).strip()
        s1v = "" if s1 is None or str(s1) == "nan" else str(s1).strip()
        if sv or s1v:
            out.setdefault(key, (sv, s1v))
    return out


def build_rows(kept, quotes, existing_sector_by_name):
    rows: list[dict] = []
    invalid: list[str] = []
    for c in kept:
        if c.ticker not in quotes:
            invalid.append(c.ticker)
            continue
        q = quotes[c.ticker]
        row = {
            "Ticker Yahoo Finance": c.ticker,
            "Nom": q.long_name or c.official_name,
            "ISIN": c.isin,
            "Prix": q.price,
            "Secteur 2": c.secteur2,
            "Secteur 3": c.secteur3,
            "Secteur 4": c.secteur4,
            "Secteur 5": c.secteur5,
        }
        if c.is_etf:
            row["Secteur 1"] = "ETF"
        else:
            # Action : recopie best-effort du secteur GICS d'un doublon exact de nom.
            gics, gics_fr = existing_sector_by_name.get(_norm_name(c.official_name), ("", ""))
            if gics:
                row["Secteur"] = gics
            if gics_fr:
                row["Secteur 1"] = gics_fr
        rows.append(row)
    return rows, invalid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k build_rows -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/german_enrichment.py backend/tests/test_finance/test_german_enrichment.py
git commit -m "feat(buffett): construction des lignes ToutBroker + tri des tickers invalides"
```

---

### Task 4: Écritures fichiers (tickers.csv + ToutBroker) avec backups

**Files:**
- Modify: `backend/app/services/finance/buffett/german_enrichment.py`
- Test: `backend/tests/test_finance/test_german_enrichment.py`

**Interfaces:**
- Produces:
  - `write_tickers_csv(path, kind_by_ticker: dict[str, tuple[str, str]], drop: set[str]) -> tuple[int, int]`
    → met à jour `Marché`/`Type` (`kind_by_ticker[ticker] = (marché, type)`), SUPPRIME les lignes de `drop`. Retourne `(n_maj, n_suppr)`. Backup `.bak-<ts>` avant écriture.
  - `upsert_toutbroker(path, rows: list[dict]) -> int` — upsert par `Ticker Yahoo Finance`, préserve les autres feuilles (via `broker_availability._save_main_sheet`), backup avant écriture. Retourne le nombre de lignes traitées.

- [ ] **Step 1: Write the failing test**

```python
# append to test_german_enrichment.py
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
    assert any(p.parent.glob("tickers.csv.bak-*"))


def test_upsert_toutbroker_preserves_and_upserts(tmp_path):
    import pandas as pd
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k "tickers_csv or toutbroker" -q`
Expected: FAIL (`AttributeError: write_tickers_csv`).

- [ ] **Step 3: Write minimal implementation**

```python
# append to german_enrichment.py
import datetime
import shutil
from pathlib import Path


def _backup(path: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    shutil.copy2(path, bak)
    return bak


def write_tickers_csv(path: str, kind_by_ticker, drop) -> tuple[int, int]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    _backup(path)
    out: list[str] = []
    n_maj = n_del = 0
    for line in lines:
        if not line.strip():
            continue
        parts = (line.split(";") + ["", "", "", ""])[:4]
        tk = parts[0].strip()
        if tk in drop:
            n_del += 1
            continue
        if tk in kind_by_ticker:
            marche, typ = kind_by_ticker[tk]
            parts[2], parts[3] = marche, typ
            n_maj += 1
        out.append(";".join(parts))
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return n_maj, n_del


def upsert_toutbroker(path: str, rows: list[dict]) -> int:
    from .broker_availability import _find_ticker_col, _save_main_sheet, reset_etf_cache
    df = pd.read_excel(path)
    tcol = _find_ticker_col(df.columns, "Ticker Yahoo Finance") or "Ticker Yahoo Finance"
    # Colonnes écrites -> object (évite un rejet de dtype à l'écriture).
    for col in {k for r in rows for k in r} - {tcol}:
        if col in df.columns:
            df[col] = df[col].astype(object)
    index: dict[str, int] = {}
    for i, k in df[tcol].astype(str).str.strip().items():
        index.setdefault(k, i)
    new_rows: list[dict] = []
    n = 0
    for r in rows:
        tk = str(r.get(tcol, "")).strip()
        if not tk:
            continue
        payload = {k: v for k, v in r.items() if k != tcol}
        if tk in index:
            for col, val in payload.items():
                if col not in df.columns:
                    df[col] = pd.NA
                    df[col] = df[col].astype(object)
                df.at[index[tk], col] = val
        else:
            new_rows.append(r)
        n += 1
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    _backup(path)
    _save_main_sheet(df, path)
    reset_etf_cache()
    return n
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -k "tickers_csv or toutbroker" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/buffett/german_enrichment.py backend/tests/test_finance/test_german_enrichment.py
git commit -m "feat(buffett): écritures tickers.csv + upsert ToutBroker avec backups"
```

---

### Task 5: Script orchestrateur CLI (dry-run) + rapport

**Files:**
- Create: `backend/scripts/enrich_german_instruments.py`

**Interfaces:**
- Consumes: tout `german_enrichment` (Tasks 1-4).
- CLI : `--dry-run` (défaut, aucune écriture, imprime le rapport) / `--apply` (sonde Yahoo + écritures). `--limit N` (borne la sonde pour un essai). `--chunk-size` (défaut 50).

- [ ] **Step 1: Écrire le script**

```python
# backend/scripts/enrich_german_instruments.py
"""Enrichit tickers.csv + ToutBroker.xlsx pour les instruments allemands.

Usage (depuis backend/):
  .venv/Scripts/python.exe scripts/enrich_german_instruments.py --dry-run
  .venv/Scripts/python.exe scripts/enrich_german_instruments.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pandas as pd

from app.services.finance.buffett import german_enrichment as ge

ROOT = _BACKEND.parent
TICKERS = ROOT / "data/imports/Finances/variables/tickers.csv"
BROKER = ROOT / "data/imports/Finances/tableur/ToutBroker.xlsx"
XETRA = _BACKEND / ".codex-xetra-instruments.csv"
FRANKFURT = _BACKEND / ".codex-frankfurt-instruments.csv"


def load_unprocessed_german(path: Path) -> list[str]:
    df = pd.read_csv(path, sep=";", header=None, dtype=str,
                     keep_default_na=False, names=["Ticker", "Nom", "Marche", "Type"])
    df["Ticker"] = df["Ticker"].str.strip()
    unp = df[df["Type"].str.strip() == ""]
    mask = unp["Ticker"].str.upper().str.endswith((".DE", ".F"))
    return unp.loc[mask, "Ticker"].tolist()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--chunk-size", type=int, default=50)
    args = ap.parse_args()

    xm, fm = ge.load_official_maps(str(XETRA), str(FRANKFURT))
    tickers = load_unprocessed_german(TICKERS)
    if args.limit:
        tickers = tickers[: args.limit]

    kept, dropped = [], 0
    for t in tickers:
        c = ge.classify_ticker(t, xm, fm)
        (kept.append(c) if c else None)
        dropped += 0 if c else 1
    n_etf = sum(c.is_etf for c in kept)
    print(f"Tickers allemands non traités : {len(tickers)}")
    print(f"  Retenus : {len(kept)}  (ETF/ETN/ETC={n_etf}, actions={len(kept)-n_etf})")
    print(f"  Écartés (BOND/FUN/non-appariés) : {dropped}")

    if not args.apply:
        print("\n[DRY-RUN] Aucune écriture. Relancer avec --apply pour sonder Yahoo et écrire.")
        return

    print(f"\nSonde Yahoo de {len(kept)} symboles (lots de {args.chunk_size})…")
    quotes = ge.probe_symbols([c.ticker for c in kept], chunk_size=args.chunk_size)
    df_broker = pd.read_excel(BROKER)
    rows, invalid = ge.build_rows(kept, quotes, ge.existing_sector_map(df_broker))
    print(f"  Valides : {len(rows)}   Invalides (non résolus Yahoo) : {len(invalid)}")

    kind_by_ticker = {c.ticker: (c.market, c.kind) for c in kept
                      if c.ticker not in set(invalid)}
    n_maj, n_del = ge.write_tickers_csv(str(TICKERS), kind_by_ticker, set(invalid))
    n_up = ge.upsert_toutbroker(str(BROKER), rows)
    print(f"tickers.csv : {n_maj} mis à jour, {n_del} supprimés (invalides).")
    print(f"ToutBroker  : {n_up} lignes upsertées. reset_etf_cache() OK.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Lancer le dry-run sur les vraies données**

Run: `cd backend && .venv/Scripts/python.exe scripts/enrich_german_instruments.py`
Expected (ordres de grandeur) : `non traités ≈ 27803`, `Retenus ≈ 22955` (ETF/ETN/ETC ≈ 7106, actions ≈ 15849), `Écartés ≈ 4848`. Vérifier qu'aucune écriture n'a eu lieu (`git status` propre sur tickers.csv / ToutBroker).

- [ ] **Step 3: Essai borné de la sonde (petit lot réel)**

Run: `cd backend && .venv/Scripts/python.exe scripts/enrich_german_instruments.py --apply --limit 40`
Expected : la sonde renvoie des `Valides`/`Invalides` cohérents ; tickers.csv/ToutBroker modifiés uniquement pour ces ≤40 tickers. **Puis restaurer** les fichiers depuis le backup `.bak-*` (ou `git checkout --`) avant le run complet, pour repartir propre.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/enrich_german_instruments.py
git commit -m "feat(buffett): script d'enrichissement des instruments allemands (dry-run + apply)"
```

---

### Task 6: Exécution complète + vérification

**Files:** aucun nouveau (exécution).

- [ ] **Step 1: Run complet (sonde ~15-40 min)**

Run: `cd backend && .venv/Scripts/python.exe scripts/enrich_german_instruments.py --apply`
Expected : rapport final avec `Valides`/`Invalides`, `tickers.csv` et `ToutBroker` mis à jour. Noter les compteurs.

- [ ] **Step 2: Vérifier ToutBroker**

```bash
cd backend && .venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_excel(r'../data/imports/Finances/tableur/ToutBroker.xlsx')
print('lignes', len(df))
print('ETF (Secteur 1==ETF)', (df['Secteur 1'].astype(str).str.strip()=='ETF').sum())
print('ISIN remplis', df['ISIN'].astype(str).str.strip().replace('nan','').ne('').sum())
"
```
Expected : hausse du nombre de lignes et d'ETF cohérente avec le rapport ; colonne ISIN largement remplie.

- [ ] **Step 3: Vérifier tickers.csv**

```bash
cd backend && .venv/Scripts/python.exe -c "
import pandas as pd
df = pd.read_csv(r'../data/imports/Finances/variables/tickers.csv', sep=';', header=None,
                 dtype=str, keep_default_na=False, names=['T','N','M','Ty'])
g = df[df['T'].str.upper().str.endswith(('.DE','.F'))]
print('allemands avec Type rempli', (g['Ty'].str.strip()!='').sum(), '/', len(g))
print(g['Ty'].value_counts().to_string())
"
```
Expected : quasi tous les tickers allemands restants ont un `Type` ; plus de lignes invalides.

- [ ] **Step 4: Lancer toute la suite de tests du module**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_finance/test_german_enrichment.py -q`
Expected : PASS.

- [ ] **Step 5: Commit des données enrichies**

```bash
git add data/imports/Finances/variables/tickers.csv data/imports/Finances/tableur/ToutBroker.xlsx
git commit -m "data(buffett): enrichissement Xetra/Francfurt — ETF classés + actions validées"
```

---

## Self-Review (à remplir après rédaction)

- **Couverture spec :** classification hors-ligne (T1) · sonde Yahoo bornée (T2) · validité + ISIN + prix (T2-T3) · Secteur 1-5 ETF & « Actions » (T1, T3) · écritures tickers.csv + ToutBroker + backups + reset cache (T4) · rapport + dry-run (T5) · exécution + vérif (T6). ✔
- **Limites assumées (non-objectifs) :** secteur GICS par action non sondé (rempli par le runner, sauf doublon exact de nom) ; disponibilité broker laissée vide ; BOND/FUN/OTHER/WAR écartés.
- **Risque Yahoo :** si blocage prolongé pendant la sonde, `probe_symbols` continue (symboles du lot en échec = comptés invalides). Option de repli : relancer `--apply` (les déjà-traités ont un `Type` en tickers.csv et sont ré-analysables).
