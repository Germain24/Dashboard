"""Playlists d'ambiance : appartenance, reco, export M3U."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique.constants import AMBIANCE_NAMES


def playlist_tracks(session: Session, ambiance: str) -> list[MusicTrack]:
    ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    if not ids:
        return []
    return list(session.exec(select(MusicTrack).where(MusicTrack.id.in_(ids))).all())  # type: ignore[attr-defined]


def set_membership(session: Session, track_id: int, ambiance: str, present: bool,
                   source: str = "manuel") -> None:
    if ambiance not in AMBIANCE_NAMES:
        raise ValueError(f"Ambiance inconnue : {ambiance}")
    row = session.exec(
        select(TrackAmbiance).where(TrackAmbiance.track_id == track_id)
        .where(TrackAmbiance.ambiance == ambiance)
    ).first()
    if present and row is None:
        session.add(TrackAmbiance(track_id=track_id, ambiance=ambiance, source=source))
        session.commit()
    elif not present and row is not None:
        session.delete(row)
        session.commit()


def to_m3u(tracks: list[dict], *, relatif: bool = True) -> str:
    """Construit un .m3u (chemins relatifs) lisible par Poweramp."""
    lines = ["#EXTM3U"]
    for t in tracks:
        dur = t.get("duree_sec") or -1
        artist = t.get("artist", "")
        title = t.get("title", "")
        lines.append(f"#EXTINF:{dur},{artist} - {title}")
        lines.append(t["path"])
    return "\n".join(lines) + "\n"


def reco_bibliotheque(tracks_in: list[dict], tracks_out: list[dict]) -> list[dict]:
    """Parmi tracks_out, ceux partageant artiste OU genre avec tracks_in.

    Triés par nombre de recoupements décroissant (artistes + genres communs).
    """
    artists = {t.get("artist", "").lower() for t in tracks_in if t.get("artist")}
    genres = {t.get("genre", "").lower() for t in tracks_in if t.get("genre")}
    scored = []
    for t in tracks_out:
        score = 0
        if t.get("artist", "").lower() in artists:
            score += 1
        if t.get("genre", "").lower() in genres:
            score += 1
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda st: st[0], reverse=True)
    return [t for _, t in scored]
