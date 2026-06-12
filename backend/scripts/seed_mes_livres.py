"""Synchronise mes livres personnels dans la base (upsert par titre).

Usage :  uv run python scripts/seed_mes_livres.py

Comportement :
- Nouveau livre  -> cree
- Livre existant -> met a jour les champs modifies (pages, genre, couverture_url, isbn, auteur)
  Le statut et page_courante ne sont PAS ecrasés (pour préserver ta progression).
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.models.livres import Book  # noqa: E402

# Champs mis à jour si le livre existe déjà (on ne touche pas statut / page_courante)
UPDATABLE_FIELDS = ["auteur", "isbn", "pages", "genre", "couverture_url"]

LIVRES_INITIAUX: list[dict] = [
    # ── Finance / Mentalité ───────────────────────────────────────────────────
    {
        "titre": "Same as Ever: A Guide to What Never Changes",
        "auteur": "Morgan Housel",
        "isbn": "9780593332702",
        "pages": 240,
        "genre": "Psychologie comportementale et sociale",
        "statut": "a_lire",
        "couverture_url": "https://m.media-amazon.com/images/I/417ycDMhl5L._SY445_SX342_ML2_.jpg",
    },
    # ── Sport / Musculation ───────────────────────────────────────────────────
    {
        "titre": "Muscle Ladder: Get Jacked Using Science",
        "auteur": "Jeff Nippard",
        "isbn": "1628604867",
        "pages": 390,
        "genre": "Science du sport et de l'exercice",
        "statut": "a_lire",
        "couverture_url": "https://www.indigo.ca/cdn/shop/files/image_00ce1607-896f-4323-b76f-46445faacf8a.jpg?v=1757685494&width=299",
    },
    # ── Ajoute tes autres livres ici ─────────────────────────────────────────
    # {
    #     "titre": "...",
    #     "auteur": "...",
    #     "isbn": None,
    #     "pages": None,
    #     "genre": "...",       # Essai / Roman / SF / Sport / Finance / Informatique / etc.
    #     "statut": "a_lire",   # "a_lire" | "en_cours" | "lu" | "abandonne"
    #     "couverture_url": None,
    # },
]


def main() -> None:
    added = 0
    updated = 0
    with Session(engine) as session:
        existing = {b.titre: b for b in session.exec(select(Book)).all()}
        for data in LIVRES_INITIAUX:
            titre = data["titre"]
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
                    statut=data.get("statut", "a_lire"),
                    couverture_url=data.get("couverture_url"),
                    created_at=dt.datetime.utcnow(),
                )
                session.add(book)
                print(f"  [+]   {titre} ({book.auteur})")
                added += 1
        session.commit()

    print(f"\nOK: {added} ajoute(s), {updated} mis a jour.")


if __name__ == "__main__":
    main()
