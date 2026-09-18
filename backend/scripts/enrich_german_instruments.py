"""Enrichit tickers.csv + ToutBroker.xlsx pour les instruments allemands.

Classe hors-ligne les tickers .DE/.F non traités (via les CSV officiels
Deutsche Börse), sonde Yahoo pour valider, puis écrit Type/Marché dans
tickers.csv et upsert les lignes dans ToutBroker (Secteur 1-5, ISIN, Prix).

Usage (depuis backend/):
  .venv/Scripts/python.exe scripts/enrich_german_instruments.py            # dry-run
  .venv/Scripts/python.exe scripts/enrich_german_instruments.py --apply    # écrit
  .venv/Scripts/python.exe scripts/enrich_german_instruments.py --apply --limit 40
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import pandas as pd  # noqa: E402

from app.services.finance.buffett import german_enrichment as ge  # noqa: E402

ROOT = _BACKEND.parent
_VARS = ROOT / "data/imports/Finances/variables"
TICKERS = _VARS / "tickers.csv"
BROKER = ROOT / "data/imports/Finances/tableur/ToutBroker.xlsx"


def _first_existing(*paths: Path) -> Path:
    """Emplacement stable en priorité, repli sur les résidus `.codex-*`."""
    return next((p for p in paths if p.exists()), paths[0])


# CSV de référence Deutsche Börse (rafraîchissables : réexporter T7 instrument
# reference data). Emplacement stable d'abord ; repli sur les fichiers `.codex-*`
# de la session d'origine (voués au nettoyage, cf. audit §3.G).
XETRA = _first_existing(_VARS / "xetra_instruments.csv",
                        _BACKEND / ".codex-xetra-instruments.csv")
FRANKFURT = _first_existing(_VARS / "frankfurt_instruments.csv",
                            _BACKEND / ".codex-frankfurt-instruments.csv")


def load_unprocessed_german(path: Path) -> list[str]:
    df = pd.read_csv(path, sep=";", header=None, dtype=str,
                     keep_default_na=False, names=["Ticker", "Nom", "Marche", "Type"])
    df["Ticker"] = df["Ticker"].str.strip()
    unp = df[df["Type"].str.strip() == ""]
    mask = unp["Ticker"].str.upper().str.endswith((".DE", ".F"))
    return unp.loc[mask, "Ticker"].tolist()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="sonde Yahoo + écrit les fichiers")
    ap.add_argument("--limit", type=int, default=0, help="borne la sonde (essai)")
    ap.add_argument("--chunk-size", type=int, default=50)
    args = ap.parse_args()

    for p in (TICKERS, BROKER, XETRA, FRANKFURT):
        if not p.exists():
            sys.exit(f"[ERREUR] introuvable : {p}")

    xm, fm = ge.load_official_maps(str(XETRA), str(FRANKFURT))
    tickers = load_unprocessed_german(TICKERS)
    if args.limit:
        tickers = tickers[: args.limit]

    kept: list[ge.Classified] = []
    dropped = 0
    for t in tickers:
        c = ge.classify_ticker(t, xm, fm)
        if c:
            kept.append(c)
        else:
            dropped += 1
    n_etf = sum(c.is_etf for c in kept)
    print(f"Tickers allemands non traités : {len(tickers)}")
    print(f"  Retenus : {len(kept)}  (ETF/ETN/ETC={n_etf}, actions={len(kept) - n_etf})")
    print(f"  Écartés (BOND/FUN/non-appariés) : {dropped}")

    if not args.apply:
        print("\n[DRY-RUN] Aucune écriture. Relancer avec --apply pour sonder Yahoo et écrire.")
        return

    print(f"\nSonde Yahoo de {len(kept)} symboles (lots de {args.chunk_size})…")

    def _progress(done, total, found):
        if done % (args.chunk_size * 20) == 0 or done == total:
            print(f"  {done}/{total} sondés, {found} résolus", flush=True)

    quotes = ge.probe_symbols([c.ticker for c in kept],
                              chunk_size=args.chunk_size, on_batch=_progress)
    df_broker = pd.read_excel(BROKER)
    rows, invalid = ge.build_rows(kept, quotes, ge.existing_sector_map(df_broker))
    print(f"  Valides : {len(rows)}   Invalides (non résolus Yahoo) : {len(invalid)}")

    invalid_set = set(invalid)
    kind_by_ticker = {c.ticker: (c.market, c.kind) for c in kept
                      if c.ticker not in invalid_set}
    n_maj, n_del = ge.write_tickers_csv(str(TICKERS), kind_by_ticker, invalid_set)
    n_up = ge.upsert_toutbroker(str(BROKER), rows)
    print(f"tickers.csv : {n_maj} mis à jour, {n_del} supprimés (invalides).")
    print(f"ToutBroker  : {n_up} lignes upsertées. reset_etf_cache() OK.")


if __name__ == "__main__":
    main()
