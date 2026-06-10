"""Suggestions d'artistes/genres à explorer (Ollama), pas de titres exacts."""
from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client


def parse_suggestions(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if s:
            out.append(s)
    return out


def suggest_artists(session: Session, ambiance: str, *, generate=ollama_client.generate) -> list[str]:
    ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    artists = sorted({t.artist for t in session.exec(
        select(MusicTrack).where(MusicTrack.id.in_(ids))).all() if t.artist})[:20]  # type: ignore[attr-defined]
    if not artists:
        return []
    prompt = (
        f"Voici des artistes d'une playlist '{ambiance}': {', '.join(artists)}.\n"
        "Propose 10 autres artistes ou genres similaires à explorer (un par ligne, "
        "juste le nom, pas de titres de chansons)."
    )
    try:
        return parse_suggestions(generate(prompt))[:10]
    except Exception:
        return []
