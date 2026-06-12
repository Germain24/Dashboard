"""Module Films & Séries — watchlist + progression (#534)."""
import datetime as dt

from sqlmodel import Field, SQLModel


class WatchItem(SQLModel, table=True):
    __tablename__ = "watch_item"
    id: int | None = Field(default=None, primary_key=True)
    type: str = "film"          # "film" | "serie"
    titre: str
    tmdb_id: int | None = None
    statut: str = "a_voir"      # "a_voir" | "en_cours" | "vu"
    note: float | None = None   # /5
    annee: int | None = None
    genres: str = "[]"          # JSON list of str
    poster_url: str | None = None
    duree_min: int | None = None         # films (minutes)
    nb_saisons: int | None = None        # séries
    nb_episodes_total: int | None = None  # séries
    synopsis: str = ""
    date_vue: dt.date | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class SerieProgress(SQLModel, table=True):
    __tablename__ = "serie_progress"
    id: int | None = Field(default=None, primary_key=True)
    watch_item_id: int = Field(foreign_key="watch_item.id", index=True)
    saison: int = 1
    episode_courant: int = 0
    episodes_saison: int | None = None
    date_derniere_vue: dt.date | None = None
