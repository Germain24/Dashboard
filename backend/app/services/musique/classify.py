"""Classement autonome des morceaux par ambiance via Ollama.

Un morceau par appel : les prompts « par lot » font s'effondrer les petits
modèles (qwen2.5:3b se contente d'énumérer les ambiances dans l'ordre).
Le classement reprend aussi les morceaux marqués « classés » mais sans aucune
ambiance (vieux runs ratés) : auto-guérison sans bouton Réinitialiser.
"""
from __future__ import annotations

import unicodedata

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client
from app.services.musique.constants import AMBIANCES, AMBIANCE_NAMES

_progress = {"n_done": 0, "n_total": 0, "active": False, "error": None}

# Au-delà de ce nombre d'échecs Ollama consécutifs, on arrête le job (Ollama HS).
_MAX_CONSECUTIVE_FAILS = 5

# Le modèle répond souvent en français libre : on mappe les synonymes courants
# vers les noms canoniques d'ambiances (clés normalisées sans accents).
_SYNONYMES = {
    "amour": "love",
    "romantique": "love",
    "romance": "love",
    "fete": "soirée",
    "festif": "soirée",
    "dansant": "soirée",
    "danse": "soirée",
    "detente": "repos",
    "calme": "repos",
    "relax": "repos",
    "sieste": "repos",
    "concentration": "étude",
    "travail": "coworking",
    "chill": "loft",
    "motivant": "énergie",
    "entrainant": "énergie",
}


def get_progress() -> dict:
    return dict(_progress)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip(" .,-")


def build_prompt(track: dict) -> str:
    # Formulation validée empiriquement (température 0) : les variantes
    # « genre d'abord / 1-2 max » donnaient de moins bons résultats.
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
    for syn, canonical in _SYNONYMES.items():
        if canonical in ambiances:
            norm_map.setdefault(syn, canonical)
    out: list[str] = []
    for token in raw.replace("\n", ",").split(","):
        key = _norm(token)
        if key in norm_map and norm_map[key] not in out:
            out.append(norm_map[key])
    return out


def _pending_tracks(session: Session) -> list[MusicTrack]:
    """Morceaux à classer : jamais classés + classés sans aucune ambiance."""
    tagged_ids = {r.track_id for r in session.exec(select(TrackAmbiance)).all()}
    return [
        t for t in session.exec(select(MusicTrack)).all()
        if not t.classified or t.id not in tagged_ids
    ]


def classify_untagged(session: Session, *, generate=ollama_client.generate) -> dict:
    tracks = _pending_tracks(session)
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


def reset_classification(session: Session, *, tout: bool = False) -> dict:
    """Réinitialise des morceaux pour un nouveau classement.

    - Par défaut : seulement les morceaux classés SANS ambiance (échec Ollama).
    - ``tout=True`` : efface toutes les attributions AUTO (mauvais run) et remet
      ces morceaux à reclasser. Les ambiances posées à la main sont préservées.
    """
    if tout:
        track_ids = set()
        for row in session.exec(select(TrackAmbiance).where(TrackAmbiance.source == "auto")).all():
            track_ids.add(row.track_id)
            session.delete(row)
        n = 0
        for track in session.exec(select(MusicTrack).where(MusicTrack.classified == True)).all():  # noqa: E712
            track.classified = False
            session.add(track)
            n += 1
        session.commit()
        return {"reinitialises": n}

    tagged_ids = {r.track_id for r in session.exec(select(TrackAmbiance)).all()}
    n = 0
    for track in session.exec(select(MusicTrack).where(MusicTrack.classified == True)).all():  # noqa: E712
        if track.id not in tagged_ids:
            track.classified = False
            session.add(track)
            n += 1
    session.commit()
    return {"reinitialises": n}
