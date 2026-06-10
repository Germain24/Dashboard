"""Classement autonome des morceaux par ambiance via Ollama."""
from __future__ import annotations

import unicodedata

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client
from app.services.musique.constants import AMBIANCES, AMBIANCE_NAMES

_progress = {"n_done": 0, "n_total": 0, "active": False, "error": None}

# Au-delà de ce nombre d'échecs Ollama consécutifs, on arrête le job (Ollama HS).
_MAX_CONSECUTIVE_FAILS = 5


def get_progress() -> dict:
    return dict(_progress)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip(" .,-")


def build_prompt(track: dict) -> str:
    lignes = "\n".join(f"- {name} : {desc}" for name, desc in AMBIANCES.items())
    return (
        "Tu classes un morceau de musique par ambiance. Ambiances possibles :\n"
        f"{lignes}\n\n"
        f"Morceau : artiste={track.get('artist','')}, album={track.get('album','')}, "
        f"titre={track.get('title','')}, genre={track.get('genre','')}.\n"
        "Réponds uniquement par les ambiances adaptées séparées par des virgules "
        "(ou 'aucune'). Pas de phrase."
    )


def parse_ambiances(raw: str, ambiances: list[str]) -> list[str]:
    norm_map = {_norm(a): a for a in ambiances}
    out: list[str] = []
    for token in raw.replace("\n", ",").split(","):
        key = _norm(token)
        if key in norm_map and norm_map[key] not in out:
            out.append(norm_map[key])
    return out


def classify_untagged(session: Session, *, generate=ollama_client.generate) -> dict:
    tracks = session.exec(select(MusicTrack).where(MusicTrack.classified == False)).all()  # noqa: E712
    _progress.update(n_done=0, n_total=len(tracks), active=True, error=None)
    classes = 0
    fails = 0
    try:
        for track in tracks:
            try:
                raw = generate(build_prompt(track.model_dump()))
            except Exception:
                # Échec Ollama : on NE marque PAS le morceau classé (réessayable).
                fails += 1
                if fails >= _MAX_CONSECUTIVE_FAILS:
                    _progress["error"] = (
                        "Ollama indisponible (le modèle plante ?). Classement interrompu — "
                        "vérifie Ollama puis relance."
                    )
                    break
                continue
            fails = 0  # un succès réinitialise le compteur d'échecs
            ambiances = parse_ambiances(raw, AMBIANCE_NAMES)
            for amb in ambiances:
                session.add(TrackAmbiance(track_id=track.id, ambiance=amb, source="auto"))
            track.classified = True
            session.add(track)
            session.commit()
            if ambiances:
                classes += 1
            _progress["n_done"] += 1
    finally:
        _progress["active"] = False
    return {"classes": classes, "total": len(tracks)}


def reset_classification(session: Session) -> dict:
    """Réinitialise les morceaux SANS ambiance (ex. après un échec Ollama) pour
    qu'ils soient reclassés. Ne touche pas aux morceaux ayant déjà des ambiances."""
    tagged_ids = {r.track_id for r in session.exec(select(TrackAmbiance)).all()}
    n = 0
    for track in session.exec(select(MusicTrack).where(MusicTrack.classified == True)).all():  # noqa: E712
        if track.id not in tagged_ids:
            track.classified = False
            session.add(track)
            n += 1
    session.commit()
    return {"reinitialises": n}
