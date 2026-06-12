"""Schémas Pydantic pour les routes Films & Séries."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class WatchItemCreate(BaseModel):
    type: str = "film"
    titre: str
    tmdb_id: int | None = None
    statut: str = "a_voir"
    note: float | None = None
    annee: int | None = None
    genres: list[str] = []
    poster_url: str | None = None
    duree_min: int | None = None
    nb_saisons: int | None = None
    nb_episodes_total: int | None = None
    synopsis: str = ""
    date_vue: dt.date | None = None


class WatchItemPatch(BaseModel):
    statut: str | None = None
    note: float | None = None
    date_vue: dt.date | None = None
    titre: str | None = None
    genres: list[str] | None = None
    poster_url: str | None = None
    synopsis: str | None = None
    duree_min: int | None = None
    nb_saisons: int | None = None
    nb_episodes_total: int | None = None


class SerieProgressPatch(BaseModel):
    saison: int
    episode_courant: int
    episodes_saison: int | None = None
    date_derniere_vue: dt.date | None = None
