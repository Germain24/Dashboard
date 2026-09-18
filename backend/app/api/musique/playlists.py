"""Sous-routeur Musique : appartenances, playlists, reco, découverte, export (#511)."""
from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.api.musique.common import track_dict
from app.core.db import get_session
from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import discovery
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCE_NAMES
from app.services.musique.playlists import (
    playlist_tracks, reco_bibliotheque, safe_filename, set_membership, to_m3u8,
)

router = APIRouter()


@router.get("/playlists/export.zip")
def export_zip(session: Session = Depends(get_session)):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for slug in AMBIANCE_NAMES:
            label = AMBIANCE_LABELS[slug]
            tracks = [t.model_dump() for t in playlist_tracks(session, slug)]
            zf.writestr(f"{safe_filename(label)}.m3u8", to_m3u8(tracks, titre=label))
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="playlists-musique.zip"'},
    )


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
