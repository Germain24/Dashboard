"""Routes Films & Séries (#536)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.films_series.schemas import (
    SerieProgressPatch,
    WatchItemCreate,
    WatchItemPatch,
)
from app.core.config import settings
from app.core.db import get_session
from app.models.films_series import WatchItem
from app.services.films_series import stats as stats_svc
from app.services.films_series import tmdb as tmdb_svc
from app.services.films_series import watchlist as wl_svc

router = APIRouter()


@router.get("/search")
def search(q: str, type: str = "film"):
    """Recherche TMDB — retourne [] sans clé (mode manuel)."""
    return tmdb_svc.search(q, media_type=type, api_key=settings.tmdb_api_key)


@router.get("/watchlist")
def list_watchlist(
    type: str | None = None,
    statut: str | None = None,
    session: Session = Depends(get_session),
):
    return wl_svc.get_watchlist(session, type=type, statut=statut)


@router.post("/watchlist", status_code=201)
def add_watch_item(body: WatchItemCreate, session: Session = Depends(get_session)):
    data = body.model_dump()
    # Enrichir via TMDB si clé dispo et tmdb_id fourni
    if body.tmdb_id and settings.tmdb_api_key:
        details = tmdb_svc.get_details(body.tmdb_id, body.type, settings.tmdb_api_key)
        if details:
            for k in ("poster_url", "synopsis", "duree_min", "nb_saisons", "nb_episodes_total", "annee"):
                if data.get(k) is None and details.get(k) is not None:
                    data[k] = details[k]
    return wl_svc.create_watch_item(session, **data)


@router.patch("/watchlist/{item_id}")
def patch_watch_item(
    item_id: int,
    body: WatchItemPatch,
    session: Session = Depends(get_session),
):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    item = wl_svc.update_watch_item(session, item_id, patch)
    if not item:
        raise HTTPException(404)
    return item


@router.delete("/watchlist/{item_id}", status_code=204)
def remove_watch_item(item_id: int, session: Session = Depends(get_session)):
    if not wl_svc.delete_watch_item(session, item_id):
        raise HTTPException(404)


@router.get("/progress/{item_id}")
def get_progress(item_id: int, session: Session = Depends(get_session)):
    item = session.get(WatchItem, item_id)
    if not item:
        raise HTTPException(404)
    prog = wl_svc.get_serie_progress(session, item_id)
    return prog or {}


@router.put("/progress/{item_id}")
def update_progress(
    item_id: int,
    body: SerieProgressPatch,
    session: Session = Depends(get_session),
):
    item = session.get(WatchItem, item_id)
    if not item:
        raise HTTPException(404)
    return wl_svc.upsert_serie_progress(
        session,
        item_id,
        saison=body.saison,
        episode_courant=body.episode_courant,
        episodes_saison=body.episodes_saison,
        date_derniere_vue=body.date_derniere_vue,
    )


@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    items = list(session.exec(select(WatchItem)).all())
    return stats_svc.watchlist_stats_pure(items)
