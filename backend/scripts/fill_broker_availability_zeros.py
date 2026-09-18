"""Remplit par `0` les cases VIDES des colonnes de disponibilité broker.

POURQUOI. Une cellule vide est interprétée par `_cell_state` comme « inconnu »,
jamais comme « indisponible » : le titre reste donc achetable aux yeux de
l'optimiseur. Or les colonnes sont massivement vides (52 447 sur 56 663 pour le
PEA), si bien que le filtre de disponibilité n'écartait presque rien.

SUR QUOI REPOSE LE `0`. Les imports du 2026-08-06 ont marqué `1` tous les
instruments présents dans les catalogues brokers, et ils sont POSTÉRIEURS aux
imports de tickers (JPX le 4, monde le 5). Une case restée vide signifie donc
« absent de la liste du broker ». Cohérence vérifiée :

    Tradding 212     import 15 734 attendus -> 15 776 `1` dans le fichier (écart 42)
    Bourse Direct 2  import  3 859 attendus ->  3 863 `1` dans le fichier (écart  4)

RÉSERVE. `Bourse Direct` (compte-titres) n'a JAMAIS fait l'objet d'un import :
ses `0` sont posés par décision de l'utilisateur, pas déduits d'une source. Son
budget étant de 0 €, ils n'influencent aucune allocation aujourd'hui. À traiter
comme une hypothèse à confirmer, pas comme une donnée vérifiée.

Les listes datent du 6 août : un instrument ajouté depuis passera à `0` à tort.
Rejouer `import_boursedirect_pea.py` (et l'équivalent Trading212) puis ce script
corrige la situation — l'opération est idempotente et n'écrase jamais un `1`.

Usage (depuis backend/) :
    .venv/Scripts/python.exe scripts/fill_broker_availability_zeros.py --dry-run
    .venv/Scripts/python.exe scripts/fill_broker_availability_zeros.py --apply
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
from app.services.finance.buffett.broker_availability import _cell_state  # noqa: E402
from app.services.finance.buffett.config import Config  # noqa: E402

TICKER_COL = "Ticker Yahoo Finance"
# Colonnes traitées, avec la source qui justifie le `0`.
COLONNES = {
    "Tradding 212": "API Trading 212 v0 (import 2026-08-06)",
    "Bourse Direct 2": "boursedirect.fr ?pea=true (import 2026-08-06)",
    "Bourse Direct": "AUCUNE SOURCE — décision utilisateur",
}
# Brokers réellement budgétés, pour mesurer l'impact.
BUDGETES = {"Tradding 212": "Trading212", "Bourse Direct 2": "BoursDirect2",
            "Bourse Direct": "BoursDirect"}


def _is_blank(value) -> bool:
    """Vide au sens strict. Une valeur INATTENDUE n'est pas vide : on n'y touche pas."""
    import pandas as pd

    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in ("", "nan")


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
    principale = next(iter(sheets))
    df = sheets[principale]
    print(f"feuille « {principale} » : {len(df)} lignes, {len(df.columns)} colonnes\n")

    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        print(f"colonnes absentes : {manquantes}")
        return 1

    enrichi = df.copy()
    total_rempli = 0
    for colonne, source in COLONNES.items():
        valeurs = list(df[colonne])
        vides = [i for i, v in enumerate(valeurs) if _is_blank(v)]
        # Valeur présente mais non interprétable : on la SIGNALE sans y toucher.
        inattendues = [
            i for i, v in enumerate(valeurs)
            if not _is_blank(v) and _cell_state(v) is None
        ]
        avant_vrai = sum(1 for v in valeurs if _cell_state(v) is True)
        avant_faux = sum(1 for v in valeurs if _cell_state(v) is False)
        for i in vides:
            valeurs[i] = 0
        enrichi[colonne] = valeurs
        total_rempli += len(vides)
        print(f"{colonne}")
        print(f"   source        : {source}")
        print(f"   avant         : {avant_vrai} disponibles, {avant_faux} indisponibles, "
              f"{len(vides)} vides")
        print(f"   -> rempli     : {len(vides)} cases mises à 0")
        if inattendues:
            print(f"   !! {len(inattendues)} valeur(s) inattendue(s) LAISSÉE(S) telle(s) quelle(s)")
        print()

    # Impact : combien de titres n'ont plus AUCUN broker budgété disponible ?
    dispo = [
        any(_cell_state(enrichi[c].iloc[i]) is True for c in BUDGETES)
        for i in range(len(enrichi))
    ]
    sans_broker = len(enrichi) - sum(dispo)
    print(f"IMPACT : {sans_broker} titres sans aucun broker budgété disponible "
          f"({sans_broker / max(len(enrichi), 1) * 100:.1f} %)")
    print(f"         {sum(dispo)} titres restent achetables quelque part")

    if args.dry_run:
        print("\n--dry-run : aucun fichier écrit.")
        return 0

    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    sauvegarde = backup_file(
        args.broker,
        category="maintenance/fill_broker_availability_zeros",
        filename=f"{args.broker.name}.bak-dispo-{horodatage}",
    )
    print(f"\nsauvegarde : {sauvegarde.name}")

    temporaire = args.broker.with_name(f".{args.broker.name}.{horodatage}.tmp.xlsx")
    with pd.ExcelWriter(temporaire, engine="openpyxl") as writer:
        enrichi.to_excel(writer, sheet_name=principale, index=False)
        for nom, frame in list(sheets.items())[1:]:
            frame.to_excel(writer, sheet_name=nom, index=False)
    os.replace(temporaire, args.broker)
    print(f"écrit : {args.broker.name} ({len(enrichi)} lignes, "
          f"{len(enrichi.columns)} colonnes, {total_rempli} cases remplies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
