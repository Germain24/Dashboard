"""Normalise la table CIQUAL 2020 (ANSES) en un CSV aux colonnes du dépôt.

    python scripts/import_ciqual.py [--source <xls>] [--out <csv>]

Entrée  : data/imports/Sante/ciqual/Table_Ciqual_2020_FR.xls
          (téléchargé depuis ciqual.anses.fr, licence ouverte Etalab)
Sortie  : data/imports/Sante/ciqual/ciqual_normalise.csv
          3 186 aliments × (identité + 42 teneurs), une ligne par aliment.

La sortie est une RÉFÉRENCE, pas un cache : elle ne dépend d'aucun prix ni
d'aucun état applicatif, et ne change que si l'ANSES publie une nouvelle table.
Elle vit sous `data/imports/`, que le dépôt ignore (comme `aliments.csv`) : elle
n'est donc pas versionnée, et se régénère en relançant ce script après avoir
retéléchargé le .xls depuis ciqual.anses.fr.

La traduction elle-même vit dans `app/services/sante/ciqual.py` (pure et
testée) ; ce script ne fait que les entrées/sorties.

Lecture du .xls : moteur `calamine` (python-calamine, déjà une dépendance du
projet) — openpyxl ne sait lire que le .xlsx, et xlrd n'est pas installé.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.sante.ciqual import (  # noqa: E402
    ACIDES_ORGANIQUES,
    ALCOOL,
    IDENTITY_COLUMNS,
    PROTEINES_FALLBACK,
    SIMPLE_MAP,
    SUM_MAP,
    VITA_BETACAROTENE,
    VITA_RETINOL,
    convert_row,
    identity,
)

#: Ordre des colonnes de teneur en sortie (stable → diffs lisibles).
NUTRIENT_COLUMNS: list[str] = [*SIMPLE_MAP, *SUM_MAP, "VitA"]


def _ciqual_dir() -> Path:
    return settings.imports_dir / "Sante" / "ciqual"


def _expected_source_columns() -> set[str]:
    return (
        set(SIMPLE_MAP.values())
        | {col for cols in SUM_MAP.values() for col in cols}
        | {VITA_RETINOL, VITA_BETACAROTENE, PROTEINES_FALLBACK, ALCOOL, ACIDES_ORGANIQUES}
        | set(IDENTITY_COLUMNS)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    source = args.source or (_ciqual_dir() / "Table_Ciqual_2020_FR.xls")
    out = args.out or (_ciqual_dir() / "ciqual_normalise.csv")

    if not source.exists():
        print(f"Table CIQUAL introuvable : {source}", file=sys.stderr)
        print("Télécharger depuis https://ciqual.anses.fr (table 2020, .xls).", file=sys.stderr)
        return 1

    # dtype=str : les teneurs contiennent « - », « traces » et « < X ». Laisser
    # pandas inférer transformerait ces colonnes en objets mixtes et perdrait
    # silencieusement la distinction entre « zéro » et « non déterminé ».
    raw = pd.read_excel(source, engine="calamine", sheet_name="compo", dtype=str)

    # Une colonne renommée par l'ANSES produirait des teneurs à zéro en silence,
    # et l'optimiseur se jetterait sur des aliments faussement bon marché en
    # nutriments. On échoue bruyamment.
    missing = sorted(_expected_source_columns() - set(raw.columns))
    if missing:
        print(f"{len(missing)} colonne(s) CIQUAL attendue(s) absente(s) :", file=sys.stderr)
        for col in missing:
            print(f"  - {col!r}", file=sys.stderr)
        return 2

    header = [*IDENTITY_COLUMNS.values(), *NUTRIENT_COLUMNS]
    rows_written = 0
    renseignes = dict.fromkeys(NUTRIENT_COLUMNS, 0)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(header)
        for record in raw.to_dict("records"):
            ident = identity(record)
            if not ident.get("CiqualCode"):
                continue
            values = convert_row(record)
            for col in values:
                renseignes[col] += 1
            writer.writerow(
                [ident[c] for c in IDENTITY_COLUMNS.values()]
                + [
                    # Teneur inconnue -> cellule VIDE, jamais un « 0 » inventé.
                    # `load_aliments_dataframe` la lira comme 0.0, donc l'aliment
                    # ne sera jamais crédité d'un nutriment non mesuré.
                    "" if col not in values else f"{values[col]:.6g}"
                    for col in NUTRIENT_COLUMNS
                ]
            )
            rows_written += 1

    print(f"{rows_written} aliments CIQUAL écrits dans {out}")
    print("\nTaux de renseignement par teneur (aliments avec une valeur connue) :")
    for col in sorted(NUTRIENT_COLUMNS, key=lambda c: renseignes[c]):
        pct = 100.0 * renseignes[col] / rows_written if rows_written else 0.0
        print(f"  {col:<18} {renseignes[col]:5d}  {pct:5.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
