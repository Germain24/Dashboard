"""Helpers partagés entre les sous-routeurs Musique (#511)."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance


def track_dict(t: MusicTrack, ambiances: list[str]) -> dict:
    return {"id": t.id, "path": t.path, "artist": t.artist, "album": t.album,
            "title": t.title, "genre": t.genre, "duree_sec": t.duree_sec,
            "cover": t.cover, "ambiances": ambiances}


def ambiances_for(session: Session, track_ids: list[int]) -> dict[int, list[str]]:
    rows = session.exec(select(TrackAmbiance).where(TrackAmbiance.track_id.in_(track_ids))).all() if track_ids else []  # type: ignore[attr-defined]
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r.track_id, []).append(r.ambiance)
    return out
