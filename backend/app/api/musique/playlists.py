"""Sous-routeur Musique : appartenances, playlists, reco, découverte, export (#511)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.api.musique.common import track_dict
from app.core.db import get_session
from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import discovery
from app.services.musique.playlists import playlist_tracks, reco_bibliotheque, set_membership, to_m3u

router = APIRouter()


@router.put("/tracks/{track_id}/ambiances/{ambiance}", status_code=204)
def add_membership(track_id: int, ambiance: str, session: Session = Depends(get_session)):
    try:
        set_membership(session, track_id, ambiance, True)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/tracks/{track_id}/ambiances/{ambiance}", status_code=204)
def remove_membership(track_id: int, ambiance: str, session: Session = Depends(get_session)):
    try:
        set_membership(session, track_id, ambiance, False)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/playlists/{ambiance}")
def playlist(ambiance: str, session: Session = Depends(get_session)):
    tracks = playlist_tracks(session, ambiance)
    return [track_dict(t, [ambiance]) for t in tracks]


@router.get("/playlists/{ambiance}/reco")
def playlist_reco(ambiance: str, session: Session = Depends(get_session)):
    in_ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    tracks_in = [t.model_dump() for t in session.exec(select(MusicTrack).where(MusicTrack.id.in_(in_ids))).all()]  # type: ignore[attr-defined]
    tracks_out = [t.model_dump() for t in session.exec(select(MusicTrack).where(MusicTrack.id.notin_(in_ids))).all()] if in_ids else []  # type: ignore[attr-defined]
    return reco_bibliotheque(tracks_in, tracks_out)[:50]


@router.get("/playlists/{ambiance}/discovery")
def playlist_discovery(ambiance: str, session: Session = Depends(get_session)):
    return {"ambiance": ambiance, "suggestions": discovery.suggest_artists(session, ambiance)}


@router.get("/playlists/{ambiance}/export.m3u", response_class=PlainTextResponse)
def export_m3u(ambiance: str, session: Session = Depends(get_session)):
    from urllib.parse import quote
    tracks = [t.model_dump() for t in playlist_tracks(session, ambiance)]
    # RFC 5987 encoding for non-ASCII filenames (e.g. "café.m3u")
    safe_name = ambiance.encode("ascii", "replace").decode("ascii") + ".m3u"
    encoded_name = quote(ambiance + ".m3u", safe="")
    disposition = f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
    return PlainTextResponse(to_m3u(tracks), media_type="audio/x-mpegurl",
                             headers={"Content-Disposition": disposition})
