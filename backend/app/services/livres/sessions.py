import datetime as dt
from sqlmodel import Session
from app.models.livres import ReadingSession

LECTURE_HABIT_MIN = 30

def create_session(db: Session, book_id: int, date: dt.date, duree_minutes: int,
                   page_debut: int | None = None, page_fin: int | None = None) -> ReadingSession:
    s = ReadingSession(book_id=book_id, date=date, duree_minutes=duree_minutes,
                       page_debut=page_debut, page_fin=page_fin)
    db.add(s)
    db.commit()
    db.refresh(s)
    if duree_minutes >= LECTURE_HABIT_MIN:
        try:
            from app.services.habitudes.entries import auto_check_habit
            auto_check_habit(db, source="livres_lecture", date=date, valeur=float(duree_minutes))
        except Exception:
            pass
    return s
