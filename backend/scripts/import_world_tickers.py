"""Complète tickers.csv avec l'univers mondial coté chez Yahoo Finance.

Le catalogue legacy ne couvrait que l'Allemagne, la Chine, le Japon, les États-Unis
et les composants des grands indices ailleurs. Ce script interroge le screener
Yahoo (`/v1/finance/screener`) place par place pour récupérer *tous* les symboles
EQUITY et ETF, puis fusionne les nouveaux dans le CSV legacy.

Les symboles proviennent de Yahoo : ils sont donc directement exploitables par le
pipeline Buffett, sans mapping depuis les codes locaux.

Le screener plafonne l'offset à ~9 800. Au-delà, la collecte est segmentée
récursivement par tranches de prix (`intradayprice`), le seul champ presque
toujours renseigné — la capitalisation est nulle sur la plupart des cotations
secondaires.

Format CSV legacy inchangé : UTF-8, LF, `Ticker;Nom;Bourse;Type`, sans en-tête.

Usage (depuis backend/) :
  .venv/Scripts/python.exe scripts/import_world_tickers.py --collect          # collecte -> cache
  .venv/Scripts/python.exe scripts/import_world_tickers.py --merge            # aperçu fusion
  .venv/Scripts/python.exe scripts/import_world_tickers.py --merge --apply    # écrit le CSV
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.backup_storage import backup_file  # noqa: E402

ROOT = _BACKEND.parent
_VARS = ROOT / "data/imports/Finances/variables"
TICKERS = _VARS / "tickers.csv"
CACHE = _VARS / ".world_tickers_cache.jsonl"
STATE = _VARS / ".world_tickers_state.json"
REPORT = ROOT / "data/world_tickers_import_report.json"

SCREENER = "https://query2.finance.yahoo.com/v1/finance/screener"
PAGE = 250
# Le screener refuse les offsets élevés ; on segmente bien avant la coupure.
OFFSET_CAP = 9500

# Codes d'échange Yahoo effectivement peuplés (sondés le 2026-08-05). Les places
# de la liste de référence absentes de Yahoo (Pakistan, Vietnam, Dhaka, Colombo,
# Nigeria, Casablanca, Ukraine, Oman, Luxembourg…) ne figurent pas ici : Yahoo ne
# les cote pas, donc le pipeline ne pourrait rien en faire.
EXCHANGES = [
    "NMS", "NYQ", "ASE", "PCX", "NCM", "NGM", "PNK", "OQB", "OQX",
    "FRA", "GER", "DUS", "HAM", "MUN", "STU",
    "LSE", "IOB", "AQS",
    "TOR", "VAN", "CNQ", "NEO",
    "MEX", "SAO", "BUE", "SGO", "BVC", "CCS",
    "NSI", "BSE",
    "TAI", "TWO", "KSC", "KOE", "SES", "KLS", "JKT", "SET",
    "HKG", "SHH", "SHZ", "JPX",
    "ASX", "NZE",
    "TLV", "SAU", "DFM", "DOH", "KUW", "CAI", "JNB",
    "PAR", "AMS", "BRU", "LIS", "EBS", "MIL", "MCE", "VIE",
    "STO", "CPH", "HEL", "OSL", "ICE", "RIS", "TAL", "LIT",
    "PRA", "BUD", "WSE", "BVB", "ATH", "IST",
]

QUOTE_TYPES = ("EQUITY", "ETF")
# `intradaymarketcap` n'est pas un champ triable pour les ETF.
SORT_FIELD = {"EQUITY": "intradaymarketcap", "ETF": "fundnetassets"}
CSV_TYPE = {"EQUITY": "Action", "ETF": "Tracker/ETF"}


class Screener:
    """Client screener avec crumb renouvelable et retries."""

    def __init__(self) -> None:
        from app.services.finance.yf_session import yf_session

        self._session = yf_session()
        self._crumb = self._new_crumb()

    def _new_crumb(self) -> str:
        from yfinance.data import YfData

        return YfData(session=self._session)._get_crumb_basic()

    def query(self, operands: list[dict], quote_type: str, offset: int,
              size: int = PAGE, sort_type: str = "DESC",
              sort_field: str | None = None) -> dict:
        body = {
            "size": size,
            "offset": offset,
            "sortField": sort_field or SORT_FIELD[quote_type],
            "sortType": sort_type,
            "quoteType": quote_type,
            "query": {"operator": "AND", "operands": operands},
            "userId": "",
            "userIdType": "guid",
        }
        last = ""
        for attempt in range(4):
            url = f"{SCREENER}?crumb={self._crumb}&lang=en-US&region=US&formatted=false"
            try:
                resp = self._session.post(
                    url, json=body, headers={"Content-Type": "application/json"}
                )
            except Exception as exc:  # réseau : on retente
                last = f"{type(exc).__name__}: {exc}"
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code in (401, 403):
                self._crumb = self._new_crumb()
                continue
            if resp.status_code != 200:
                last = f"HTTP {resp.status_code}"
                time.sleep(2 * (attempt + 1))
                continue
            payload = resp.json().get("finance", {})
            if not payload.get("result"):
                raise RuntimeError(f"screener: {payload.get('error')}")
            return payload["result"][0]
        raise RuntimeError(f"screener injoignable ({last})")


def _exchange_filter(code: str) -> dict:
    return {"operator": "EQ", "operands": ["exchange", code]}


def _price_filter(low: float, high: float) -> dict:
    return {"operator": "BTWN", "operands": ["intradayprice", low, high]}


def _harvest(api: Screener, operands: list[dict], quote_type: str,
             total: int, sink: dict[str, dict]) -> int:
    """Pagine une requête dont le total tient sous le plafond d'offset."""
    got = 0
    for offset in range(0, min(total, OFFSET_CAP), PAGE):
        block = api.query(operands, quote_type, offset)
        quotes = block.get("quotes") or []
        if not quotes:
            break
        for quote in quotes:
            symbol = (quote.get("symbol") or "").strip()
            if not symbol or symbol in sink:
                continue
            sink[symbol] = {
                "symbol": symbol,
                "name": (quote.get("longName") or quote.get("shortName") or "").strip(),
                "market": (quote.get("fullExchangeName") or "").strip(),
                "exchange": (quote.get("exchange") or "").strip(),
                "type": quote_type,
            }
        got += len(quotes)
    return got


def _collect_segment(api: Screener, code: str, quote_type: str,
                     bounds: tuple[float, float] | None,
                     sink: dict[str, dict], depth: int = 0) -> None:
    """Collecte une place, en subdivisant par prix tant que l'offset sature."""
    operands = [_exchange_filter(code)]
    if bounds is not None:
        operands.append(_price_filter(*bounds))
    head = api.query(operands, quote_type, 0, size=1)
    total = int(head.get("total") or 0)
    if total == 0:
        return
    label = f"{code}/{quote_type}" + (f" [{bounds[0]:g}-{bounds[1]:g}]" if bounds else "")
    if total <= OFFSET_CAP or depth >= 16:
        if total > OFFSET_CAP:
            print(f"  ! {label}: {total} titres, tronqué à {OFFSET_CAP} "
                  f"(profondeur max atteinte)", flush=True)
        _harvest(api, operands, quote_type, total, sink)
        print(f"  {label}: {total} -> cumul {len(sink)}", flush=True)
        return
    low, high = bounds if bounds else (0.0, 1e9)
    # Découpage géométrique : les cotations se concentrent dans les bas prix.
    mid = (low + high) / 2 if low > 0 else max(high / 100, 1e-4)
    print(f"  {label}: {total} titres > {OFFSET_CAP}, split à {mid:g}", flush=True)
    _collect_segment(api, code, quote_type, (low, mid), sink, depth + 1)
    _collect_segment(api, code, quote_type, (mid, high), sink, depth + 1)


def collect(only: list[str] | None = None) -> None:
    api = Screener()
    done: dict[str, int] = {}
    if STATE.exists():
        done = json.loads(STATE.read_text(encoding="utf-8"))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    targets = [c for c in EXCHANGES if not only or c in only]
    with CACHE.open("a", encoding="utf-8") as out:
        for code in targets:
            for quote_type in QUOTE_TYPES:
                key = f"{code}:{quote_type}"
                if key in done:
                    print(f"{key}: déjà collecté ({done[key]})", flush=True)
                    continue
                sink: dict[str, dict] = {}
                started = time.time()
                try:
                    _collect_segment(api, code, quote_type, None, sink)
                except Exception as exc:
                    print(f"{key}: ECHEC {type(exc).__name__}: {exc}", flush=True)
                    continue
                for row in sink.values():
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                done[key] = len(sink)
                STATE.write_text(json.dumps(done, indent=2), encoding="utf-8")
                print(f"{key}: {len(sink)} symboles en {time.time()-started:.0f}s",
                      flush=True)


def _read_legacy(path: Path) -> "OrderedDict[str, list[str]]":
    rows: OrderedDict[str, list[str]] = OrderedDict()
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter=";"):
            if not row:
                continue
            row = (row + ["", "", "", ""])[:4]
            rows.setdefault(row[0].strip(), row)
    return rows


def merge(apply: bool) -> dict:
    if not CACHE.exists():
        sys.exit("[ERREUR] cache absent : lancer d'abord --collect")
    existing = _read_legacy(TICKERS)
    known = {t.upper() for t in existing}
    added: OrderedDict[str, list[str]] = OrderedDict()
    seen: set[str] = set()
    per_market: dict[str, int] = {}
    scanned = 0
    with CACHE.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            scanned += 1
            symbol = item["symbol"].strip()
            upper = symbol.upper()
            if not symbol or upper in known or upper in seen:
                continue
            seen.add(upper)
            market = item.get("market") or item.get("exchange") or ""
            added[symbol] = [symbol, item.get("name", ""), market,
                             CSV_TYPE[item["type"]]]
            per_market[market] = per_market.get(market, 0) + 1
    report = {
        "genere_le": datetime.now().isoformat(timespec="seconds"),
        "lignes_existantes": len(existing),
        "symboles_collectes": scanned,
        "ajouts": len(added),
        "total_apres": len(existing) + len(added),
        "par_marche": dict(sorted(per_market.items(), key=lambda kv: -kv[1])),
        "applique": apply,
    }
    if apply and added:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_file(
            TICKERS,
            category="maintenance/import_world_tickers",
            filename=f"tickers.backup-{stamp}.csv",
        )
        report["sauvegarde"] = str(backup)
        with TICKERS.open("a", encoding="utf-8", newline="") as out:
            writer = csv.writer(out, delimiter=";", lineterminator="\n")
            for row in added.values():
                writer.writerow(row)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true",
                        help="interroge Yahoo et alimente le cache")
    parser.add_argument("--merge", action="store_true",
                        help="fusionne le cache dans tickers.csv")
    parser.add_argument("--apply", action="store_true",
                        help="avec --merge : écrit réellement le CSV")
    parser.add_argument("--only", default="",
                        help="restreint la collecte à ces codes (séparés par ,)")
    args = parser.parse_args()
    if not (args.collect or args.merge):
        parser.error("préciser --collect et/ou --merge")
    if args.collect:
        only = [c.strip().upper() for c in args.only.split(",") if c.strip()]
        collect(only or None)
    if args.merge:
        report = merge(args.apply)
        print(json.dumps({k: v for k, v in report.items() if k != "par_marche"},
                         indent=2, ensure_ascii=False))
        print(f"marchés distincts ajoutés : {len(report['par_marche'])}")


if __name__ == "__main__":
    main()
