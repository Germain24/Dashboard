"""Lanceur CLI de l'import inventaire garde-robe.

La logique vit dans app/services/garderobe/inventaire_import.py (partagée avec
POST /garderobe/inventaire/sync). Dossier source : GARDEROBE_INVENTAIRE_DIR
(.env), par défaut C:\\Users\\germa\\Desktop\\Vetements.

Usage (depuis backend/) :
    uv run python -m scripts.import_garderobe_inventaire [--dry-run]
"""
from __future__ import annotations

import argparse

# Ré-exports : les tests et anciens appels importent ces noms depuis ce module.
from app.services.garderobe.inventaire_import import (  # noqa: F401
    build_slug,
    find_pixel_file,
    normalize_couleur,
    parse_inventaire,
    resolve_categorie,
    resolve_type_objectif,
    run_import,
    slugify,
    target_asset_name,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="affiche les actions sans rien écrire (ni fichiers ni DB)")
    args = ap.parse_args()

    from sqlmodel import Session

    from app.core.db import engine
    with Session(engine) as session:
        run_import(session, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
