"""Module Musique — bibliothèque + appartenance multi-ambiances."""
import datetime as dt

from sqlmodel import Field, SQLModel


class MusicTrack(SQLModel, table=True):
    __tablename__ = "music_track"
    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)  # relatif à music_dir
    artist: str = ""
    album: str = ""
    title: str = ""
    genre: str = ""
    duree_sec: int | None = None
    cover: str | None = None      # chemin relatif de la pochette
    classified: bool = False      # déjà passé par Ollama
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class TrackAmbiance(SQLModel, table=True):
    __tablename__ = "track_ambiance"
    id: int | None = Field(default=None, primary_key=True)
    track_id: int = Field(foreign_key="music_track.id", index=True)
    ambiance: str
    source: str = "auto"          # auto | manuel
