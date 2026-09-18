"""Synchronise mes livres personnels depuis data/mes_livres.json (upsert par titre).

Usage :  uv run python scripts/seed_mes_livres.py

Pour ajouter ou modifier un livre :
  1. Editer  backend/data/mes_livres.json
  2. Relancer ce script

Comportement :
- Nouveau livre  -> cree en base
- Livre existant -> met a jour pages / genre / auteur / isbn / couverture_url
  Le statut et page_courante ne sont PAS ecrases (progression preservee).
"""

from __future__ import annotations

import datetime as dt
from app.core.timeutil import utcnow
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.livres import Book  # noqa: E402

LIVRES_JSON = settings.data_dir / "mes_livres.json"

# Champs mis a jour si le livre existe deja (statut / page_courante preserves)
UPDATABLE_FIELDS = ["auteur", "isbn", "pages", "genre", "langue", "couverture_url"]


def load_livres() -> list[dict]:
    if not LIVRES_JSON.exists():
        print(f"Fichier introuvable : {LIVRES_JSON}")
        print("Creez ce fichier JSON avec une liste de livres.")
        return []
    try:
        data = json.loads(LIVRES_JSON.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            print("ERREUR : mes_livres.json doit contenir une liste JSON.")
            return []
        return data
    except json.JSONDecodeError as e:
        print(f"ERREUR JSON : {e}")
        return []


def main() -> None:
    livres = load_livres()
    if not livres:
        return

    added = updated = 0
    with Session(engine) as session:
        existing = {b.titre: b for b in session.exec(select(Book)).all()}
        for data in livres:
            titre = data.get("titre", "").strip()
            if not titre:
                print("  [ignore] entree sans titre")
                continue
            if titre in existing:
                book = existing[titre]
                changed = []
                for field in UPDATABLE_FIELDS:
                    new_val = data.get(field)
                    if new_val is not None and getattr(book, field) != new_val:
                        setattr(book, field, new_val)
                        changed.append(field)
                if changed:
                    session.add(book)
                    print(f"  [maj] {titre} ({', '.join(changed)})")
                    updated += 1
                else:
                    print(f"  [ok]  {titre}")
            else:
                book = Book(
                    titre=titre,
                    auteur=data.get("auteur", ""),
                    isbn=data.get("isbn"),
                    pages=data.get("pages"),
                    genre=data.get("genre", ""),
                    langue=data.get("langue", ""),
                    statut=data.get("statut", "a_lire"),
                    couverture_url=data.get("couverture_url"),
                    created_at=utcnow(),
                )
                session.add(book)
                print(f"  [+]   {titre}")
                added += 1
        session.commit()

    print(f"\nOK: {added} ajoute(s), {updated} mis a jour.")
    print(f"Source : {LIVRES_JSON}")


if __name__ == "__main__":
    main()
