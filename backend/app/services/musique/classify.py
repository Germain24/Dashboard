"""Classement autonome des morceaux par ambiance via Ollama.

Les morceaux partent par lots (BATCH_SIZE par prompt) : ~10× moins d'appels
Ollama qu'en morceau-par-morceau, crucial en CPU. Le classement reprend aussi
les morceaux marqués « classés » mais sans aucune ambiance (vieux runs ratés) :
pas besoin du bouton Réinitialiser pour s'auto-guérir.
"""
from __future__ import annotations

import re
import unicodedata

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client
from app.services.musique.constants import AMBIANCES, AMBIANCE_NAMES

_progress = {"n_done": 0, "n_total": 0, "active": False, "error": None}

# Au-delà de ce nombre d'échecs Ollama consécutifs, on arrête le job (Ollama HS).
_MAX_CONSECUTIVE_FAILS = 5

# Morceaux par prompt. Assez grand pour aller vite, assez petit pour que le
# modèle (qwen2.5:3b) reste fiable sur la liste numérotée.
BATCH_SIZE = 8

_LINE_RE = re.compile(r"^\s*(\d+)\s*[:.\-–]\s*(.*)$")


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


def build_batch_prompt(tracks: list[dict]) -> str:
    lignes = "\n".join(f"- {name} : {desc}" for name, desc in AMBIANCES.items())
    morceaux = "\n".join(
        f"{i}. artiste={t.get('artist','')}, album={t.get('album','')}, "
        f"titre={t.get('title','')}, genre={t.get('genre','')}"
        for i, t in enumerate(tracks, start=1)
    )
    return (
        "Tu classes des morceaux de musique par ambiance. Ambiances possibles :\n"
        f"{lignes}\n\n"
        f"Morceaux :\n{morceaux}\n\n"
        "Réponds avec UNE ligne par morceau, au format exact "
        "`numéro: ambiance1, ambiance2` (ou `numéro: aucune`). Pas de phrase."
    )


def parse_ambiances(raw: str, ambiances: list[str]) -> list[str]:
    norm_map = {_norm(a): a for a in ambiances}
    out: list[str] = []
    for token in raw.replace("\n", ",").split(","):
        key = _norm(token)
        if key in norm_map and norm_map[key] not in out:
            out.append(norm_map[key])
    return out


def parse_batch_response(raw: str, n: int, ambiances: list[str]) -> dict[int, list[str]]:
    """Réponse numérotée → {numéro: ambiances}. Un numéro absent = morceau non
    traité (il sera retenté au prochain run, sans être marqué classé)."""
    out: dict[int, list[str]] = {}
    for line in raw.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        num = int(m.group(1))
        if 1 <= num <= n and num not in out:
            out[num] = parse_ambiances(m.group(2), ambiances)
    # Lot de 1 : certains modèles répondent sans numéro — la réponse brute vaut
    # pour le seul morceau du lot.
    if not out and n == 1 and raw.strip():
        out[1] = parse_ambiances(raw, ambiances)
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
        for start in range(0, len(tracks), BATCH_SIZE):
            batch = tracks[start:start + BATCH_SIZE]
            try:
                raw = generate(build_batch_prompt([t.model_dump() for t in batch]))
            except Exception:
                # Échec Ollama : on NE marque PAS les morceaux classés (réessayables).
                fails += 1
                _progress["n_done"] += len(batch)
                if fails >= _MAX_CONSECUTIVE_FAILS:
                    _progress["error"] = (
                        "Ollama indisponible (le modèle plante ?). Classement interrompu — "
                        "vérifie Ollama puis relance."
                    )
                    break
                continue
            fails = 0  # un succès réinitialise le compteur d'échecs
            parsed = parse_batch_response(raw, len(batch), AMBIANCE_NAMES)
            for i, track in enumerate(batch, start=1):
                if i not in parsed:
                    # Numéro manquant dans la réponse : non traité, sera retenté.
                    _progress["n_done"] += 1
                    continue
                ambiances = parsed[i]
                for amb in ambiances:
                    session.add(TrackAmbiance(track_id=track.id, ambiance=amb, source="auto"))
                track.classified = True
                session.add(track)
                if ambiances:
                    classes += 1
                _progress["n_done"] += 1
            session.commit()
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
