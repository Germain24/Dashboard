import datetime as dt
from sqlmodel import Session
from app.models.livres import ReadingSession, Book

LECTURE_HABIT_MIN = 30

# Genres considérés « techniques » → comptés aussi comme sessions d'étude (#152)
TECH_GENRES = {
    "technique", "informatique", "programmation", "science", "sciences",
    "essai", "manuel", "data", "ia", "mathématiques", "math",
}


def is_technical(genre: str | None) -> bool:
    """Pur : True si le genre est considéré technique (lien Études #152)."""
    if not genre:
        return False
    g = genre.strip().lower()
    return any(kw in g for kw in TECH_GENRES)


def create_session(db: Session, book_id: int, date: dt.date, duree_minutes: int,
                   page_debut: int | None = None, page_fin: int | None = None) -> ReadingSession:
    s = ReadingSession(book_id=book_id, date=date, duree_minutes=duree_minutes,
                       page_debut=page_debut, page_fin=page_fin)
    db.add(s)
    db.commit()
    db.refresh(s)

    # Met à jour la page courante du livre (#144)
    book = db.get(Book, book_id)
    if book and page_fin is not None:
        if book.page_courante is None or page_fin > book.page_courante:
            book.page_courante = page_fin
            db.add(book)
            db.commit()

    # Habitude lecture (existant)
    if duree_minutes >= LECTURE_HABIT_MIN:
        try:
            from app.services.habitudes.entries import auto_check_habit
            auto_check_habit(db, source="livres_lecture", date=date, valeur=float(duree_minutes))
        except Exception:
            pass

    # Lien Études : un livre technique lu = session d'étude (#152)
    if book and is_technical(book.genre):
        try:
            from app.models.etudes import SessionEtude
            db.add(SessionEtude(
                cours_id=None,
                date=date,
                duree_min=duree_minutes,
                sujet=f"Lecture : {book.titre}",
                note="Auto depuis Livres",
            ))
            db.commit()
        except Exception:
            db.rollback()

    return s
