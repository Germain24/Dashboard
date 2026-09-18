"""Regroupement des livres en séries / mangas (tomes) (#5.3)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.livres import Book


def group_series_pure(books: list[Book]) -> list[dict]:
    """Pur : regroupe les livres portant une `serie`, tomes triés, progression.

    Les livres sans `serie` (essais, romans isolés) sont ignorés — ils gardent
    leur rendu individuel côté UI.
    """
    par_serie: dict[str, list[Book]] = {}
    for b in books:
        nom = (b.serie or "").strip()
        if nom:
            par_serie.setdefault(nom, []).append(b)

    groupes = []
    for nom, tomes in sorted(par_serie.items(), key=lambda kv: kv[0].lower()):
        # Un tome sans numéro (hors-série, numérotation inconnue) passe en fin
        # de liste au lieu de faire échouer la comparaison avec les int.
        ordonnes = sorted(tomes, key=lambda b: (b.tome is None, b.tome or 0))
        lus = sum(1 for b in ordonnes if b.statut == "lu")
        groupes.append({
            "serie": nom,
            "total": len(ordonnes),
            "tomes_lus": lus,
            "pct": round(lus / len(ordonnes) * 100) if ordonnes else 0,
            "tomes": [
                {
                    "id": b.id,
                    "titre": b.titre,
                    "tome": b.tome,
                    "statut": b.statut,
                    "note": b.note,
                    "pages": b.pages,
                    "page_courante": b.page_courante,
                    "couverture_url": b.couverture_url,
                }
                for b in ordonnes
            ],
        })
    return groupes


def get_series(session: Session) -> list[dict]:
    books = session.exec(select(Book)).all()
    return group_series_pure(list(books))
