"""CRUD humeur (1 entrée/jour) + agrégations pures (#476)."""
from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.journal import MoodEntry


def _validate(humeur: int, energie: int) -> None:
    for name, v in (("humeur", humeur), ("energie", energie)):
        if not (1 <= int(v) <= 5):
            raise ValueError(f"{name} doit être entre 1 et 5")


def upsert_entry(session: Session, date: dt.date, humeur: int, energie: int,
                 tags: list[str], note: str = "") -> MoodEntry:
    _validate(humeur, energie)
    entry = session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()
    if entry is None:
        entry = MoodEntry(date=date, humeur=humeur, energie=energie, tags=list(tags), note=note)
    else:
        entry.humeur = humeur
        entry.energie = energie
        entry.tags = list(tags)
        entry.note = note
        entry.updated_at = dt.datetime.utcnow()
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_entry(session: Session, date: dt.date) -> MoodEntry | None:
    return session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()


def list_entries(session: Session, debut: dt.date, fin: dt.date) -> list[MoodEntry]:
    return list(session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
        .order_by(MoodEntry.date)  # type: ignore[arg-type]
    ).all())


def delete_entry(session: Session, date: dt.date) -> bool:
    entry = get_entry(session, date)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True
