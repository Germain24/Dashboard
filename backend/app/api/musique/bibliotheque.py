"""Sous-routeur Musique : scan, classement, pistes, ambiances (#511)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.api.musique.common import ambiances_for, track_dict
from app.core.config import settings
from app.core.db import get_session
from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import classify, scan
from app.services.musique.constants import AMBIANCE_NAMES

router = APIRouter()


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


@router.post("/classify/reset")
def classify_reset(session: Session = Depends(get_session)):
    """Réinitialise les morceaux sans ambiance (échec Ollama) pour les reclasser."""
    return classify.reset_classification(session)


@router.get("/tracks")
def list_tracks(session: Session = Depends(get_session), q: str | None = None,
                ambiance: str | None = None):
    stmt = select(MusicTrack)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(MusicTrack.title.ilike(like) | MusicTrack.artist.ilike(like))  # type: ignore[attr-defined]
    tracks = list(session.exec(stmt.limit(500)).all())
    amb_map = ambiances_for(session, [t.id for t in tracks])
    rows = [track_dict(t, amb_map.get(t.id, [])) for t in tracks]
    if ambiance:
        rows = [r for r in rows if ambiance in r["ambiances"]]
    return rows


@router.get("/ambiances")
def ambiances(session: Session = Depends(get_session)):
    counts: dict[str, int] = {a: 0 for a in AMBIANCE_NAMES}
    for r in session.exec(select(TrackAmbiance)).all():
        counts[r.ambiance] = counts.get(r.ambiance, 0) + 1
    return [{"ambiance": a, "count": counts.get(a, 0)} for a in AMBIANCE_NAMES]
