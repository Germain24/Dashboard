"""Service CRUD watchlist films & séries (#536)."""

from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.films_series import SerieProgress, WatchItem


def get_watchlist(
    session: Session,
    type: str | None = None,
    statut: str | None = None,
) -> list[WatchItem]:
    stmt = select(WatchItem)
    if type:
        stmt = stmt.where(WatchItem.type == type)
    if statut:
        stmt = stmt.where(WatchItem.statut == statut)
    return list(session.exec(stmt.order_by(WatchItem.created_at.desc())).all())


def create_watch_item(session: Session, **data) -> WatchItem:
    genres = data.get("genres", [])
    if isinstance(genres, list):
        data["genres"] = json.dumps(genres, ensure_ascii=False)
    item = WatchItem(**data)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_watch_item(session: Session, item_id: int, patch: dict) -> WatchItem | None:
    item = session.get(WatchItem, item_id)
    if not item:
        return None
    genres = patch.get("genres")
    if isinstance(genres, list):
        patch["genres"] = json.dumps(genres, ensure_ascii=False)
    for k, v in patch.items():
        if hasattr(item, k):
            setattr(item, k, v)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_watch_item(session: Session, item_id: int) -> bool:
    item = session.get(WatchItem, item_id)
    if not item:
        return False
    # Supprimer la progression associée si série
    progs = session.exec(
        select(SerieProgress).where(SerieProgress.watch_item_id == item_id)
    ).all()
    for p in progs:
        session.delete(p)
    session.delete(item)
    session.commit()
    return True


def get_serie_progress(session: Session, item_id: int) -> SerieProgress | None:
    return session.exec(
        select(SerieProgress).where(SerieProgress.watch_item_id == item_id)
    ).first()


def upsert_serie_progress(
    session: Session,
    item_id: int,
    saison: int,
    episode_courant: int,
    episodes_saison: int | None = None,
    date_derniere_vue=None,
) -> SerieProgress:
    prog = session.exec(
        select(SerieProgress).where(SerieProgress.watch_item_id == item_id)
    ).first()
    if prog is None:
        prog = SerieProgress(watch_item_id=item_id)
    prog.saison = saison
    prog.episode_courant = episode_courant
    if episodes_saison is not None:
        prog.episodes_saison = episodes_saison
    if date_derniere_vue is not None:
        prog.date_derniere_vue = date_derniere_vue
    session.add(prog)
    session.commit()
    session.refresh(prog)
    return prog
