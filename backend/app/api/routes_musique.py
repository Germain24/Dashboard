"""Routes module Musique — bibliothèque, ambiances, playlists, export."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import classify, discovery, scan
from app.services.musique.constants import AMBIANCE_NAMES
from app.services.musique.playlists import playlist_tracks, reco_bibliotheque, set_membership, to_m3u

router = APIRouter()


def _track_dict(t: MusicTrack, ambiances: list[str]) -> dict:
    return {"id": t.id, "path": t.path, "artist": t.artist, "album": t.album,
            "title": t.title, "genre": t.genre, "duree_sec": t.duree_sec,
            "cover": t.cover, "ambiances": ambiances}


def _ambiances_for(session: Session, track_ids: list[int]) -> dict[int, list[str]]:
    rows = session.exec(select(TrackAmbiance).where(TrackAmbiance.track_id.in_(track_ids))).all() if track_ids else []  # type: ignore[attr-defined]
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r.track_id, []).append(r.ambiance)
    return out


@router.post("/scan")
def run_scan(session: Session = Depends(get_session)):
    try:
        return scan.scan_library(session, Path(settings.music_dir))
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@router.post("/classify", status_code=202)
def run_classify(background_tasks: BackgroundTasks):
    if classify.get_progress()["active"]:
        return {"message": "Classement déjà en cours"}
    from app.core.db import engine
    from sqlmodel import Session as S

    def job():
        with S(engine) as s:
            classify.classify_untagged(s)
    background_tasks.add_task(job)
    return {"message": "Classement démarré"}


@router.get("/classify/progress")
def classify_progress():
    return classify.get_progress()


@router.get("/tracks")
def list_tracks(session: Session = Depends(get_session), q: str | None = None,
                ambiance: str | None = None):
    stmt = select(MusicTrack)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(MusicTrack.title.ilike(like) | MusicTrack.artist.ilike(like))  # type: ignore[attr-defined]
    tracks = list(session.exec(stmt.limit(500)).all())
    amb_map = _ambiances_for(session, [t.id for t in tracks])
    rows = [_track_dict(t, amb_map.get(t.id, [])) for t in tracks]
    if ambiance:
        rows = [r for r in rows if ambiance in r["ambiances"]]
    return rows


@router.get("/ambiances")
def ambiances(session: Session = Depends(get_session)):
    counts: dict[str, int] = {a: 0 for a in AMBIANCE_NAMES}
    for r in session.exec(select(TrackAmbiance)).all():
        counts[r.ambiance] = counts.get(r.ambiance, 0) + 1
    return [{"ambiance": a, "count": counts.get(a, 0)} for a in AMBIANCE_NAMES]


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
    return [_track_dict(t, [ambiance]) for t in tracks]


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
