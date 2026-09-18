"""Importe l'univers éligible PEA de Bourse Direct dans tickers.csv + ToutBroker.

Source : l'API publique derrière https://www.boursedirect.fr/fr/marches/recherche?pea=true
(`/api/instrument/v3/search`), qui renvoie nom, ISIN, mnémonique, place (MIC),
devise et nature de chaque instrument.

Deux pièges de cette API, traités ici :

1. **Pagination non déterministe.** Le tri n'a pas de départage stable : des
   pages adjacentes se recouvrent et ~13 % des instruments restent invisibles
   sur un passage. Les réponses étant en cache par URL, un paramètre anti-cache
   (`_cb`) permet de rejouer les passes jusqu'à couvrir le total annoncé par
   nature. Sans lui, les passes suivantes renvoient la même page à l'identique.

2. **Mnémonique ≠ symbole Yahoo.** Le mnémonique est résolu en ticker Yahoo par
   le suffixe de place (`TTE`/XPAR -> `TTE.PA`), validé via l'endpoint quote v7.
   Les places sans équivalent Yahoo (« LSE - MTF », qui cote des valeurs
   nordiques et d'Europe de l'Est) passent par une recherche par ISIN, qui
   ramène la cotation native (`STR.VI`, `AMAG.VI`…).

Les OPCVM/fonds sont écartés : Yahoo ne les connaît que par un code Morningstar
(`0P00000BGK.F`) dont le faux suffixe `.F` les ferait passer pour des lignes de
Francfort, et ils ne sont pas des « actions disponibles » exploitables par le
pipeline.

Usage (depuis backend/) :
  .venv/Scripts/python.exe scripts/import_boursedirect_pea.py --scrape     # collecte -> JSON
  .venv/Scripts/python.exe scripts/import_boursedirect_pea.py --resolve    # tickers Yahoo
  .venv/Scripts/python.exe scripts/import_boursedirect_pea.py --merge      # aperçu
  .venv/Scripts/python.exe scripts/import_boursedirect_pea.py --merge --apply
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.backup_storage import backup_file  # noqa: E402

ROOT = _BACKEND.parent
_VARS = ROOT / "data/imports/Finances/variables"
TICKERS = _VARS / "tickers.csv"
RAW = _VARS / "boursedirect_pea.json"
RESOLVED = _VARS / "boursedirect_pea_resolved.json"
ETF_CACHE = _VARS / "boursedirect_pea_etfs.json"
BROKER_ACTIONS = ROOT / "data/imports/Finances/tableur/ToutBroker_Actions.xlsx"
BROKER_ETF = ROOT / "data/imports/Finances/tableur/ToutBroker_ETF.xlsx"
REPORT = ROOT / "data/boursedirect_pea_import_report.json"
COL = "BoursDirect2"

SEARCH = "https://www.boursedirect.fr/api/instrument/v3/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.boursedirect.fr/fr/marches/recherche?pea=true",
    "Cache-Control": "no-cache",
}
SIZE = 150
MAX_PASSES = 12

# MIC Bourse Direct -> suffixe Yahoo ("" = place US, sans suffixe).
MIC2SUF = {
    "XPAR": "PA", "ALXP": "PA", "XMLI": "PA",
    "XAMS": "AS", "XBRU": "BR", "ALXB": "BR", "MLXB": "BR",
    "XLIS": "LS", "ENXL": "LS", "ALXL": "LS",
    "XMAD": "MC", "XETR": "DE", "XFRA": "F", "XSWX": "SW",
    "XLON": "L", "AIMX": "L", "ETFP": "MI", "XOSL": "OL",
    "XNYS": "", "XNGS": "", "XNCM": "", "XNMS": "", "OOTC": "",
}
# Place Yahoo préférée selon la devise, pour choisir parmi les cotations d'un ISIN.
EXCH_PREF_BY_CCY = {
    "SEK": ("STO",), "NOK": ("OSL",), "DKK": ("CPH",), "PLN": ("WSE",),
    "RON": ("BVB",), "HUF": ("BUD",), "ISK": ("ICE",), "CZK": ("PRA",),
    "CHF": ("EBS", "VTX"), "GBX": ("LSE",), "GBP": ("LSE",),
    "EUR": ("GER", "FRA", "PAR", "AMS", "BRU", "MIL", "MCE", "LIS", "HEL", "VIE"),
    "USD": ("NMS", "NYQ", "PNK", "NCM", "NGM", "ASE"),
}
TYPE_LABEL = {"EQUITY": "Action", "ETF": "Tracker/ETF", "MUTUALFUND": "Fonds"}


# ── Collecte ────────────────────────────────────────────────────────────────

def _get(params: dict, page: int, size: int = SIZE, cb: str | None = None) -> dict:
    query = dict(params, pea="true", page=page, size=size)
    if cb is not None:
        query["_cb"] = cb                      # casse le cache par URL
    url = SEARCH + "?" + urllib.parse.urlencode(query)
    last: Exception | None = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"échec {url}: {last}")


def scrape() -> dict:
    """Collecte l'univers PEA, nature par nature, jusqu'au total annoncé."""
    root = _get({}, 0, size=1)
    total = root["count"]
    store: dict[str, dict] = {}
    print(f"total annoncé = {total}")
    for nat in root["aggregations"]["instrument"]["nature"]["values"]:
        nature, attendu = nat["value"], nat["count"]
        vus: set[str] = set()
        pages = (attendu + SIZE - 1) // SIZE
        for run in range(MAX_PASSES):
            for page in range(pages):
                for it in _get({"nature": nature}, page,
                               cb=f"{nature}-{run}-{page}")["instruments"]:
                    store[it["slug"]] = it
                    vus.add(it["slug"])
                time.sleep(0.1)
            print(f"  [{nature}] passe {run + 1} : {len(vus)}/{attendu}")
            if len(vus) >= attendu:
                break
        if len(vus) < attendu:
            print(f"  !! {nature} incomplet : {len(vus)}/{attendu}")

    rows = [{
        "isin": i.get("isin"), "ticker": i.get("ticker"), "name": i.get("name"),
        "type": (i.get("type") or {}).get("label"),
        "type_ref": (i.get("type") or {}).get("reference"),
        "market": (i.get("market") or {}).get("name"),
        "mic": (i.get("market") or {}).get("mic"),
        "currency": (i.get("currency") or {}).get("code"),
        "slug": i.get("slug"), "url": i.get("url"),
    } for i in store.values()]
    rows.sort(key=lambda r: (r["isin"] or "", r["mic"] or "", r["ticker"] or ""))
    payload = {"count_annonce": total, "count_recupere": len(rows),
               "instruments": rows}
    RAW.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)}/{total} instruments -> {RAW}")
    return payload


def scrape_etfs() -> dict:
    """Collecte seulement les trackers PEA avec ISIN et symbole Yahoo direct.

    Cette passe courte est rejouable avant une optimisation. Elle sert de source
    locale à l'enrichissement ISIN sans relancer la résolution Yahoo des milliers
    d'actions du catalogue complet.
    """
    root = _get({"nature": "tracker"}, 0, size=1)
    expected = int(root.get("count") or 0)
    pages = (expected + SIZE - 1) // SIZE
    store: dict[str, dict] = {}
    for run in range(MAX_PASSES):
        for page in range(pages):
            for item in _get(
                {"nature": "tracker"}, page,
                cb=f"tracker-{run}-{page}-{datetime.date.today().isoformat()}",
            ).get("instruments", []):
                store[item["slug"]] = item
            time.sleep(0.1)
        print(f"  [tracker] passe {run + 1} : {len(store)}/{expected}")
        if len(store) >= expected:
            break
    rows = [{
        "isin": item.get("isin"),
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "mic": (item.get("market") or {}).get("mic"),
        "currency": (item.get("currency") or {}).get("code"),
        "slug": item.get("slug"),
        "yahoo": _candidate({
            "ticker": item.get("ticker"),
            "mic": (item.get("market") or {}).get("mic"),
        }),
    } for item in store.values()]
    rows.sort(key=lambda row: (row.get("isin") or "", row.get("mic") or ""))
    payload = {
        "count_annonce": expected,
        "count_recupere": len(rows),
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "instruments": rows,
    }
    ETF_CACHE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8",
    )
    print(f"{len(rows)}/{expected} trackers -> {ETF_CACHE}")
    return payload


# ── Résolution vers Yahoo ───────────────────────────────────────────────────

def _candidate(inst: dict) -> str | None:
    suffix = MIC2SUF.get(inst.get("mic"))
    mnemo = (inst.get("ticker") or "").strip().upper().replace(" ", "-")
    if suffix is None or not mnemo:
        return None
    return f"{mnemo}.{suffix}" if suffix else mnemo


def _search_isin(isin: str, session) -> list[dict]:
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            r = session.get(f"https://{host}/v1/finance/search",
                            params={"q": isin, "quotesCount": 10, "newsCount": 0})
            if getattr(r, "status_code", 0) != 200:
                continue
            return [q for q in ((r.json() or {}).get("quotes") or []) if q.get("symbol")]
        except Exception:
            continue
    return []


def resolve() -> dict:
    """Associe un ticker Yahoo à chaque instrument (mnémonique puis ISIN)."""
    from app.services.finance.buffett import german_enrichment as ge
    from app.services.finance.yf_session import yf_session

    data = json.loads(RAW.read_text(encoding="utf-8"))
    inst = data["instruments"]

    quotes = ge.probe_symbols(
        sorted({c for i in inst if (c := _candidate(i))}), session=yf_session())
    resolved: dict[str, dict] = {}
    restants: list[dict] = []
    for i in inst:
        q = quotes.get(_candidate(i) or "")
        if q:
            resolved[i["slug"]] = {"yahoo": q.symbol, "voie": "mnemo+mic",
                                   "quote_type": q.quote_type, "yahoo_name": q.long_name}
        else:
            restants.append(i)
    print(f"voie mnémonique : {len(resolved)} | restants : {len(restants)}")

    session = yf_session()
    par_isin: dict[str, list[dict]] = {}
    for n, isin in enumerate(sorted({i["isin"] for i in restants if i.get("isin")}), 1):
        par_isin[isin] = _search_isin(isin, session)
        if n % 200 == 0:
            print(f"  ISIN {n}")
        time.sleep(0.05)

    for i in restants:
        hits = [h for h in par_isin.get(i.get("isin") or "", [])
                if h.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")]
        if not hits:
            continue
        pref = EXCH_PREF_BY_CCY.get(i.get("currency") or "", ())
        hits.sort(key=lambda h: pref.index(h["exchange"])
                  if h.get("exchange") in pref else 99)
        best = hits[0]
        resolved[i["slug"]] = {
            "yahoo": best["symbol"], "voie": "isin",
            "quote_type": best.get("quoteType"),
            "yahoo_name": best.get("longname") or best.get("shortname"),
        }

    rows = [dict(i, **resolved.get(i["slug"], {})) for i in inst]
    payload = {"count": len(rows), "resolus": len(resolved), "instruments": rows}
    RESOLVED.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"résolus {len(resolved)}/{len(inst)} -> {RESOLVED}")
    return payload


# ── Fusion ──────────────────────────────────────────────────────────────────

def _backup(path: Path) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return backup_file(
        path,
        category="maintenance/import_boursedirect_pea",
        filename=path.name + f".bak-boursedirect-{stamp}",
    )


def merge(apply: bool) -> None:
    data = json.loads(RESOLVED.read_text(encoding="utf-8"))

    pea: dict[str, dict] = {}
    ecartes = 0
    for i in data["instruments"]:
        y = (i.get("yahoo") or "").strip().upper()
        if not y:
            continue
        if i.get("type_ref") in ("opcvm", "fund") or y.startswith("0P"):
            ecartes += 1
            continue
        pea.setdefault(y, i)
    print(f"{len(pea)} tickers PEA exploitables ({ecartes} OPCVM/fonds écartés)")

    rows: list[list[str]] = []
    connus: set[str] = set()
    places = collections.defaultdict(collections.Counter)
    with TICKERS.open(encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.reader(fh, delimiter=";"):
            if not row or not row[0].strip():
                continue
            row = (row + ["", "", "", ""])[:4]
            connus.add(row[0].strip().upper())
            suf = row[0].rsplit(".", 1)[1].upper() if "." in row[0] else ""
            if row[2].strip():
                places[suf][row[2].strip()] += 1
            rows.append(row)
    place_par_suffixe = {s: c.most_common(1)[0][0] for s, c in places.items()}

    nouveaux = []
    for sym in sorted(set(pea) - connus):
        i = pea[sym]
        suf = sym.rsplit(".", 1)[1].upper() if "." in sym else ""
        nouveaux.append([
            sym, (i.get("yahoo_name") or i.get("name") or "").replace(";", ",").strip(),
            place_par_suffixe.get(suf, ""),
            TYPE_LABEL.get(str(i.get("quote_type") or "").upper(), ""),
        ])
    print(f"tickers.csv : {len(rows)} lignes, {len(nouveaux)} à ajouter")

    import pandas as pd

    from app.services.finance.buffett.broker_availability import (
        _find_ticker_col,
        _save_main_sheet,
        read_broker_excel,
        reset_etf_cache,
    )
    df = read_broker_excel(str(BROKER_ACTIONS))
    tcol = _find_ticker_col(df.columns, "Ticker Yahoo Finance")
    if COL not in df.columns:
        sys.exit(f"[ERREUR] colonne {COL!r} absente de ToutBroker")
    index: dict[str, int] = {}
    for pos, key in df[tcol].astype(str).str.strip().str.upper().items():
        index.setdefault(key, pos)
    a_marquer = [s for s in pea if s in index]
    a_creer = [s for s in pea if s not in index]
    print(f"ToutBroker : {len(df)} lignes, {len(a_marquer)} à marquer, "
          f"{len(a_creer)} à créer")

    if not apply:
        print("[dry-run] rien écrit — relancer avec --apply")
        return

    if nouveaux:
        print("backup", _backup(TICKERS).name)
        with TICKERS.open("a", encoding="utf-8", newline="") as fh:
            for row in nouveaux:
                fh.write(";".join(row) + "\n")

    df[COL] = df[COL].astype(object)
    from app.services.finance.buffett.etf_index_registry import valid_isin

    isin_conflicts = []
    isin_filled = 0
    for sym in a_marquer:
        df.at[index[sym], COL] = 1
        source_isin = valid_isin(pea[sym].get("isin"))
        current_isin = valid_isin(df.at[index[sym], "ISIN"])
        if source_isin and not current_isin:
            df.at[index[sym], "ISIN"] = source_isin
            isin_filled += 1
        elif source_isin and source_isin != current_isin:
            isin_conflicts.append({
                "ticker": sym, "catalog": current_isin, "bourse_direct": source_isin,
            })
    if a_creer:
        df = pd.concat([df, pd.DataFrame([
            {tcol: s, "Nom": pea[s].get("yahoo_name") or pea[s].get("name"),
             "ISIN": pea[s].get("isin"), COL: 1} for s in a_creer
        ])], ignore_index=True)
    print("backup", _backup(BROKER_ACTIONS).name)
    _save_main_sheet(df, str(BROKER_ACTIONS))
    reset_etf_cache()
    from app.services.finance.catalog.repository import sync_local_broker_catalog_metadata
    sync_local_broker_catalog_metadata()
    print(f"ToutBroker -> {len(df)} lignes")
    print(f"ISIN complétés : {isin_filled}; conflits conservés : {len(isin_conflicts)}")

    REPORT.write_text(json.dumps({
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "https://www.boursedirect.fr/fr/marches/recherche?pea=true",
        "tickers_yahoo": len(pea), "opcvm_fonds_ecartes": ecartes,
        "tickers_csv_ajoutes": len(nouveaux),
        "toutbroker_marques": len(a_marquer), "toutbroker_ajoutes": len(a_creer),
        "isin_completes": isin_filled,
        "isin_conflits": isin_conflicts,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def merge_etfs(apply: bool) -> dict:
    """Complète les ETF Bourse Direct déjà présents, sans résolution Yahoo.

    Le symbole construit depuis mnémonique+MIC n'est utilisé que s'il existe
    déjà dans ToutBroker. Les autres lignes attendent la résolution Yahoo du
    pipeline complet afin de ne jamais créer un faux ticker.
    """
    from app.services.finance.buffett.broker_availability import (
        _find_ticker_col,
        _save_main_sheet,
        read_broker_excel,
        reset_etf_cache,
    )
    from app.services.finance.buffett.etf_index_registry import valid_isin
    from app.services.finance.buffett.etf_reference import reference_for

    payload = json.loads(ETF_CACHE.read_text(encoding="utf-8"))
    instruments = payload.get("instruments", [])
    df = read_broker_excel(str(BROKER_ETF))
    ticker_col = _find_ticker_col(df.columns, "Ticker Yahoo Finance")
    if ticker_col is None:
        raise RuntimeError("colonne ticker absente de ToutBroker")
    for required in ("ISIN", "Secteur 1", COL):
        if required not in df.columns:
            df[required] = ""
    # Les exports SQLite portent des états TRUE/FALSE sous forme de chaînes ;
    # pandas 3 interdit sinon d'y écrire les marqueurs numériques historiques.
    df[COL] = df[COL].astype(object)

    ticker_index: dict[str, list[int]] = collections.defaultdict(list)
    isin_index: dict[str, list[int]] = collections.defaultdict(list)
    for index, row in df.iterrows():
        ticker = str(row.get(ticker_col) or "").strip().upper()
        isin = valid_isin(row.get("ISIN"))
        if ticker:
            ticker_index[ticker].append(index)
        if isin:
            isin_index[isin].append(index)

    matched: set[int] = set()
    rejected_without_isin: set[int] = set()
    conflicts: list[dict] = []
    for instrument in instruments:
        isin = valid_isin(instrument.get("isin"))
        yahoo = str(instrument.get("yahoo") or "").strip().upper()
        if not isin and yahoo:
            isin = valid_isin(reference_for(ticker=yahoo).get("isin"))
        exact_indices = list(ticker_index.get(yahoo, []))
        # Un résultat OTC au libellé générique, sans ISIN vérifiable, n'est pas
        # une preuve suffisante qu'une ligne est un ETF réellement négociable.
        # Il a pu être marqué par une ancienne version du script : on le purge.
        if not isin:
            for index in exact_indices:
                rejected_without_isin.add(index)
                df.at[index, COL] = 0
                if str(df.at[index, "Secteur 1"] or "").strip().upper() == "ETF":
                    df.at[index, "Secteur 1"] = ""
            continue
        indices = list(exact_indices)
        indices.extend(isin_index.get(isin, []))
        for index in dict.fromkeys(indices):
            matched.add(index)
            current = valid_isin(df.at[index, "ISIN"])
            if isin and current and current != isin:
                conflicts.append({
                    "ticker": str(df.at[index, ticker_col]),
                    "catalog": current,
                    "bourse_direct": isin,
                })
                continue
            if isin and not current:
                df.at[index, "ISIN"] = isin
            df.at[index, "Secteur 1"] = "ETF"
            # Une autre cotation du même ISIN est bien un ETF, mais elle n'est
            # pas nécessairement négociable chez Bourse Direct. La disponibilité
            # broker n'est affirmée que pour le mnémonique+MIC exact de l'API.
            if index in exact_indices:
                df.at[index, COL] = 1
            if not str(df.at[index, "Nom"] or "").strip():
                df.at[index, "Nom"] = instrument.get("name") or ""

    diagnostics = {
        "source_rows": len(instruments),
        "distinct_isins": len({
            valid_isin(item.get("isin")) for item in instruments
            if valid_isin(item.get("isin"))
        }),
        "matched_workbook_rows": len(matched),
        "rejected_without_valid_isin": len(rejected_without_isin),
        "unmatched_source_rows": sum(
            not ticker_index.get(str(item.get("yahoo") or "").strip().upper())
            and not isin_index.get(valid_isin(item.get("isin")))
            for item in instruments
        ),
        "conflicts": conflicts,
    }
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    if apply and (matched or rejected_without_isin):
        print("backup", _backup(BROKER_ETF).name)
        _save_main_sheet(df, str(BROKER_ETF))
        reset_etf_cache()
        from app.services.finance.catalog.repository import sync_local_broker_catalog_metadata
        diagnostics["sqlite"] = sync_local_broker_catalog_metadata()
    elif not apply:
        print("[dry-run] rien écrit — relancer avec --apply")
    return diagnostics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scrape", action="store_true", help="collecte l'univers PEA")
    ap.add_argument(
        "--scrape-etfs", action="store_true",
        help="collecte rapide des trackers PEA et de leurs ISIN",
    )
    ap.add_argument("--resolve", action="store_true", help="résout les tickers Yahoo")
    ap.add_argument("--merge", action="store_true", help="fusionne dans les fichiers")
    ap.add_argument(
        "--merge-etfs", action="store_true",
        help="complète ISIN/classe ETF des trackers déjà présents",
    )
    ap.add_argument("--apply", action="store_true", help="écrit (sinon dry-run)")
    args = ap.parse_args()
    if not (
        args.scrape or args.scrape_etfs or args.resolve or args.merge or args.merge_etfs
    ):
        ap.error("choisir au moins --scrape, --resolve ou --merge")
    if args.scrape:
        scrape()
    if args.scrape_etfs:
        scrape_etfs()
    if args.resolve:
        resolve()
    if args.merge:
        merge(args.apply)
    if args.merge_etfs:
        merge_etfs(args.apply)


if __name__ == "__main__":
    main()
