"""Ajoute `Primary Market` et `Fundamentals Symbol` à ToutBroker.xlsx.

POURQUOI. Ces deux colonnes sont absentes du fichier. Or `build_fundamentals_links`
exige qu'un ISIN possède une ligne marquée `Primary Market` pour former un groupe
de cotations. Sans elles, aucun groupe ne se formait, et la propagation des
fondamentaux de la cotation PRINCIPALE vers les cotations SECONDAIRES ne produisait
rien — à chaque run, silencieusement (« 0 cotations secondaires propagees »). C'est
ce qui affamait Munich, Milan, Amsterdam et une grande partie de Londres, où le PEG
manque à 80-98 %. La même absence privait aussi la déduplication de sa règle « la
place principale prime », qui retombait sur le seul volume.

CE QUE FAIT CE SCRIPT. Il est strictement ADDITIF : aucune ligne n'est supprimée,
aucune colonne existante modifiée, les autres feuilles sont recopiées telles quelles.
C'est la différence avec `catalog/apply.py`, qui RECONSTRUIT le fichier depuis les
exports officiels (Euronext, Nasdaq, NYSE, Amex) et supprimerait donc les dizaines
de milliers de lignes venues d'autres imports — Francfort, Xetra, Tokyo, Shenzhen,
Hong Kong.

La désignation de la cotation principale réutilise `build_fundamentals_links` : une
seule source de vérité, partagée avec le runtime. À défaut de donnée officielle, la
ligne la plus liquide de chaque groupe ISIN est retenue.

Usage :
    python scripts/backfill_primary_market_columns.py --dry-run
    python scripts/backfill_primary_market_columns.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.backup_storage import backup_file  # noqa: E402
from app.services.finance.buffett.config import Config  # noqa: E402
from app.services.finance.buffett.fundamentals_resolver import (  # noqa: E402
    build_fundamentals_links,
)

TICKER_COL = "Ticker Yahoo Finance"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--broker", type=Path, default=Path(Config.BROKER_FILE))
    args = parser.parse_args(argv)

    import pandas as pd

    if not args.broker.exists():
        print(f"fichier introuvable : {args.broker}")
        return 1

    sheets = pd.read_excel(args.broker, sheet_name=None)
    main_name = next(iter(sheets))
    current = sheets[main_name]
    print(f"feuille « {main_name} » : {len(current)} lignes, {len(current.columns)} colonnes")

    deja = [c for c in ("Primary Market", "Fundamentals Symbol")
            if c in current.columns]
    if deja:
        print(f"colonnes déjà présentes : {deja} — elles seront RECALCULÉES")

    links = build_fundamentals_links(current)
    fundamentals = {t: link.fundamentals_symbol for t, link in links.items()}

    tickers = current[TICKER_COL].astype(str).str.strip()
    fs = [fundamentals.get(t, t) for t in tickers]
    pm = [fundamentals.get(t, t) == t for t in tickers]

    groupes = len({v for v in fs}) if fs else 0
    multi = sum(1 for t, f in zip(tickers, fs) if f != t)
    print(f"\ncotations principales désignées : {sum(pm)}")
    print(f"cotations secondaires rattachées : {multi}")
    print(f"symboles fondamentaux distincts  : {groupes}")

    if args.dry_run:
        apercu = pd.DataFrame({
            TICKER_COL: tickers, "Primary Market": pm, "Fundamentals Symbol": fs,
        })
        rattachees = apercu[apercu[TICKER_COL] != apercu["Fundamentals Symbol"]]
        print("\nexemples de rattachements :")
        print(rattachees.head(12).to_string(index=False))
        print("\n--dry-run : aucun fichier écrit.")
        return 0

    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    sauvegarde = backup_file(
        args.broker,
        category="maintenance/backfill_primary_market_columns",
        filename=f"{args.broker.name}.bak-primary-{horodatage}",
    )
    print(f"\nsauvegarde : {sauvegarde.name}")

    enrichi = current.copy()
    enrichi["Primary Market"] = pm
    enrichi["Fundamentals Symbol"] = fs

    temporaire = args.broker.with_name(f".{args.broker.name}.{horodatage}.tmp.xlsx")
    with pd.ExcelWriter(temporaire, engine="openpyxl") as writer:
        enrichi.to_excel(writer, sheet_name=main_name, index=False)
        for nom, frame in list(sheets.items())[1:]:
            frame.to_excel(writer, sheet_name=nom, index=False)
    os.replace(temporaire, args.broker)
    print(f"écrit : {args.broker.name} "
          f"({len(enrichi)} lignes, {len(enrichi.columns)} colonnes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
