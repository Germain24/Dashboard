"""Enrichit tickers.csv avec les listings boursiers complets.

Utilise Wikipedia + BeautifulSoup4 pour extraire les tableaux de
tickers par bourse (actions individuelles uniquement).

Exécution :
  python scripts/enrich_all_exchanges.py --dry-run
  python scripts/enrich_all_exchanges.py
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent.parent
TICKERS_CSV = REPO / "data" / "imports" / "Finances" / "variables" / "tickers.csv"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
TIMEOUT = 30


def load_existing() -> set[str]:
    if not TICKERS_CSV.exists():
        return set()
    existing = set()
    with open(TICKERS_CSV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ticker = line.split(";")[0].strip().upper()
            if ticker:
                existing.add(ticker)
    return existing


def save_tickers(tickers: list[tuple[str, str, str, str]], dry: bool = False) -> int:
    existing = load_existing()
    added = 0
    if not dry:
        with open(TICKERS_CSV, "a", encoding="utf-8") as f:
            for ticker, name, market, typ in tickers:
                if ticker.upper() in existing:
                    continue
                if not re.match(r"^[A-Z0-9.-]+$", ticker.upper()):
                    continue
                f.write(f"{ticker};{name};{market};{typ}\n")
                existing.add(ticker.upper())
                added += 1
    else:
        added = sum(
            1 for t, _, _, _ in tickers
            if t.upper() not in existing and re.match(r"^[A-Z0-9.-]+$", t.upper())
        )
    return added


def clean_name(name) -> str:
    if not name or not str(name).strip():
        return ""
    n = str(name).strip()
    n = re.sub(r"[\r\n;]+", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n[:120]


def fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = SESSION.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERREUR] {url}: {e}")
        return None


def extract_wikitable(soup: BeautifulSoup, col_ticker: int, col_name: int,
                       suffix: str, market: str, skip_header: bool = True) -> list[tuple[str, str, str, str]]:
    """Extrait les tickers d'un tableau Wikipedia (classe wikitable)."""
    tickers = []
    tables = soup.find_all("table", class_="wikitable")
    if not tables:
        tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for tr in (rows[1:] if skip_header else rows):
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(col_ticker, col_name):
                continue
            code = cells[col_ticker].get_text(strip=True).upper()
            name = clean_name(cells[col_name].get_text(strip=True))
            # Ignorer les lignes non-actions
            if not code or not name:
                continue
            if any(kw in name.upper() for kw in ("ETF", "ETN", "ETC", "FUND", "TRUST", "REIT")):
                continue
            tickers.append((f"{code}{suffix}", name, market, "Action"))
    return tickers


# ═══════════════════════════════════════════════════════════════════════════════
# Wikipedia sources — chaque bourse majeure a une page "List of companies..."
# ═══════════════════════════════════════════════════════════════════════════════

WIKI_SOURCES = [
    # Indices majeurs (composants d'indice — source fiable)
    ("https://en.wikipedia.org/wiki/Nikkei_225",
     0, 1, ".T", "Tokyo Stock Exchange (Nikkei 225)"),
    ("https://en.wikipedia.org/wiki/Hang_Seng_Index",
     0, 1, ".HK", "Hong Kong Stock Exchange (Hang Seng)"),
    ("https://en.wikipedia.org/wiki/NIFTY_50",
     0, 1, ".NS", "National Stock Exchange India (Nifty 50)"),
    ("https://en.wikipedia.org/wiki/NIFTY_Next_50",
     0, 1, ".NS", "National Stock Exchange India (Nifty Next 50)"),
    ("https://en.wikipedia.org/wiki/BSE_SENSEX",
     0, 1, ".BO", "Bombay Stock Exchange (SENSEX)"),
    ("https://en.wikipedia.org/wiki/S%26P/TSX_60",
     0, 1, ".TO", "Toronto Stock Exchange (S&P/TSX 60)"),
    ("https://en.wikipedia.org/wiki/S%26P/ASX_200",
     0, 1, ".AX", "Australian Securities Exchange (S&P/ASX 200)"),
    ("https://en.wikipedia.org/wiki/FTSE_100_Index",
     0, 1, ".L", "London Stock Exchange (FTSE 100)"),
    ("https://en.wikipedia.org/wiki/FTSE_250_Index",
     0, 1, ".L", "London Stock Exchange (FTSE 250)"),
    ("https://en.wikipedia.org/wiki/KOSPI",
     0, 1, ".KS", "Korea Exchange (KOSPI)"),
    ("https://en.wikipedia.org/wiki/KOSDAQ",
     0, 1, ".KQ", "Korea Exchange (KOSDAQ)"),
    ("https://en.wikipedia.org/wiki/FTSE_Bursa_Malaysia_KLCI",
     0, 1, ".KL", "Bursa Malaysia (KLCI)"),
    ("https://en.wikipedia.org/wiki/IBOVESPA",
     0, 1, ".SA", "B3 (Ibovespa)"),
    ("https://en.wikipedia.org/wiki/FTSE_MIB",
     0, 1, ".MI", "Borsa Italiana (FTSE MIB)"),
    ("https://en.wikipedia.org/wiki/IBEX_35",
     0, 1, ".MC", "Bolsa de Madrid (IBEX 35)"),
    ("https://en.wikipedia.org/wiki/AEX_index",
     0, 1, ".AS", "Euronext Amsterdam (AEX)"),
    ("https://en.wikipedia.org/wiki/BEL_20",
     0, 1, ".BR", "Euronext Brussels (BEL 20)"),
    ("https://en.wikipedia.org/wiki/CAC_40",
     0, 1, ".PA", "Euronext Paris (CAC 40)"),
    ("https://en.wikipedia.org/wiki/CAC_Next_20",
     0, 1, ".PA", "Euronext Paris (CAC Next 20)"),
    ("https://en.wikipedia.org/wiki/DAX",
     0, 1, ".DE", "Xetra (DAX)"),
    ("https://en.wikipedia.org/wiki/MDAX",
     0, 1, ".DE", "Xetra (MDAX)"),
    ("https://en.wikipedia.org/wiki/SDAX",
     0, 1, ".DE", "Xetra (SDAX)"),
    ("https://en.wikipedia.org/wiki/OMX_Copenhagen_25",
     0, 1, ".CO", "Nasdaq Copenhagen (OMXC25)"),
    ("https://en.wikipedia.org/wiki/OMX_Stockholm_30",
     0, 1, ".ST", "Nasdaq Stockholm (OMXS30)"),
    ("https://en.wikipedia.org/wiki/OMX_Helsinki_25",
     0, 1, ".HE", "Nasdaq Helsinki (OMXH25)"),
    ("https://en.wikipedia.org/wiki/Swiss_Market_Index",
     0, 1, ".SW", "SIX Swiss Exchange (SMI)"),
    ("https://en.wikipedia.org/wiki/Swiss_Performance_Index",
     0, 1, ".SW", "SIX Swiss Exchange (SPI)"),
    ("https://en.wikipedia.org/wiki/WIG_20",
     0, 1, ".WA", "Warsaw Stock Exchange (WIG20)"),
    ("https://en.wikipedia.org/wiki/ATX_Index",
     0, 1, ".VI", "Vienna Stock Exchange (ATX)"),
    ("https://en.wikipedia.org/wiki/MOEX_Russia_Index",
     0, 1, ".ME", "Moscow Exchange (MOEX)"),
    ("https://en.wikipedia.org/wiki/BIST_100",
     0, 1, ".IS", "Borsa Istanbul (BIST 100)"),
    ("https://en.wikipedia.org/wiki/MERVAL",
     0, 1, ".BA", "Buenos Aires Stock Exchange (MERVAL)"),
    ("https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
     0, 1, "", "New York Stock Exchange (DJIA)"),
    ("https://en.wikipedia.org/wiki/NASDAQ-100",
     0, 1, "", "NASDAQ (NASDAQ-100)"),
    ("https://en.wikipedia.org/wiki/S%26P_100",
     0, 1, "", "S&P 100"),

    # Listes complètes par bourse (pages qui fonctionnent)
    ("https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Hong_Kong_Stock_Exchange",
     0, 1, ".HK", "Hong Kong Stock Exchange"),
    ("https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_National_Stock_Exchange_of_India",
     0, 1, ".NS", "National Stock Exchange India"),
    ("https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Singapore_Exchange",
     0, 1, ".SI", "Singapore Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(A)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(B)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(C)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(D)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(E)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(F)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(G)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(H)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(I)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(J)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(K)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(L)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(M)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(N)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(O)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(P)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(Q)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(R)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(S)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(T)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(U)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(V)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(W)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(X)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(Y)",
     0, 1, "", "New York Stock Exchange"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_New_York_Stock_Exchange_(Z)",
     0, 1, "", "New York Stock Exchange"),
    # NASDAQ A-Z
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(A)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(B)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(C)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(D)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(E)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(F)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(G)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(H)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(I)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(J)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(K)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(L)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(M)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(N)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(O)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(P)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(Q)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(R)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(S)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(T)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(U)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(V)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(W)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(X)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(Y)",
     0, 1, "", "NASDAQ"),
    ("https://en.wikipedia.org/wiki/Companies_listed_on_the_NASDAQ_(Z)",
     0, 1, "", "NASDAQ"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Limiter le nombre de pages Wikipedia")
    args = parser.parse_args()

    existing = load_existing()
    print(f"Tickers existants: {len(existing)}")
    total = 0
    pages_ok = 0
    pages_fail = 0

    sources = WIKI_SOURCES[:args.limit] if args.limit else WIKI_SOURCES
    for url, col_t, col_n, suffix, market in sources:
        # Dédupliquer par marché+suffixe
        market_short = market.split(" (")[0]
        print(f"\n[{suffix}] {market_short}...")
        soup = fetch_soup(url)
        if soup is None:
            pages_fail += 1
            continue
        tickers = extract_wikitable(soup, col_t, col_n, suffix, market)
        n = save_tickers(tickers, args.dry_run)
        print(f"  {n} ajoutes (candidats: {len(tickers)})")
        total += n
        if len(tickers) > 0:
            pages_ok += 1
        else:
            pages_fail += 1
        time.sleep(0.3)  # politesse

    print(f"\n{'='*60}")
    print(f"Total ajoutes: {total} ({pages_ok} pages OK, {pages_fail} echecs)")
    existing_after = load_existing() if not args.dry_run else existing
    print(f"Total final: {len(existing_after)} tickers")
    if args.dry_run:
        print("[DRY RUN] Aucune modification ecrite.")
    else:
        print(f"Fichier: {TICKERS_CSV}")


if __name__ == "__main__":
    main()
