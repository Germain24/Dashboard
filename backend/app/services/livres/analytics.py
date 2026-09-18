"""Statistiques annuelles & recommandations Livres (#146, #149)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.livres import Book


def annual_stats_pure(books: list[Book], year: int) -> dict:
    """Pur : agrège les livres lus (date_fin dans l'année) en stats annuelles."""
    lus = [
        b for b in books
        if b.statut == "lu" and b.date_fin is not None and b.date_fin.year == year
    ]
    pages = sum(b.pages or 0 for b in lus)
    par_genre: dict[str, int] = {}
    for b in lus:
        g = b.genre or "Autre"
        par_genre[g] = par_genre.get(g, 0) + 1
    return {
        "year": year,
        "livres_lus": len(lus),
        "pages_lues": pages,
        "par_genre": dict(sorted(par_genre.items(), key=lambda kv: kv[1], reverse=True)),
    }


def annual_stats(session: Session, year: int) -> dict:
    books = session.exec(select(Book)).all()
    return annual_stats_pure(list(books), year)


def recommend_pure(books: list[Book], limit: int = 5) -> list[dict]:
    """Pur : recommande des livres « à lire » dans les genres les plus lus.

    Classe les genres par nombre de livres lus, puis propose en priorité les
    livres à lire de ces genres. Complète avec les autres « à lire » si besoin.
    """
    lus = [b for b in books if b.statut == "lu"]
    a_lire = [b for b in books if b.statut == "a_lire"]
    if not a_lire:
        return []

    genre_rank: dict[str, int] = {}
    for b in lus:
        g = b.genre or "Autre"
        genre_rank[g] = genre_rank.get(g, 0) + 1

    def score(b: Book) -> int:
        return genre_rank.get(b.genre or "Autre", 0)

    ranked = sorted(a_lire, key=lambda b: (-score(b), b.titre.lower()))
    out = []
    for b in ranked[:limit]:
        s = score(b)
        out.append({
            "id": b.id,
            "titre": b.titre,
            "auteur": b.auteur,
            "genre": b.genre,
            "raison": (
                f"Tu as lu {s} livre(s) en « {b.genre or 'Autre'} »"
                if s > 0 else "Dans ta pile à lire"
            ),
        })
    return out


def recommend_books(session: Session, limit: int = 5) -> list[dict]:
    books = session.exec(select(Book)).all()
    return recommend_pure(list(books), limit)
