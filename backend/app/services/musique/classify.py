"""Classement autonome des morceaux par ambiance.

Provider : API Claude (par lots, fiable) si ANTHROPIC_API_KEY est configurée,
sinon Ollama local en unitaire — les prompts « par lot » font s'effondrer les
petits modèles (qwen2.5:3b se contente d'énumérer les ambiances dans l'ordre).

Sémantique : un morceau ``classified=True`` n'est JAMAIS reclassé, même s'il
n'a aucune ambiance (= traité, aucune playlist adaptée). Seul le bouton
Réinitialiser permet de le remettre dans la file.
"""
from __future__ import annotations

import unicodedata

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import claude_client, deepseek_client, ollama_client
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCES

_progress = {"n_done": 0, "n_total": 0, "active": False, "error": None}

# Au-delà de ce nombre d'échecs Ollama consécutifs, on arrête le job (Ollama HS).
_MAX_CONSECUTIVE_FAILS = 5

# Synonymes (texte normalisé) -> slug, pour le chemin Ollama (texte libre).
_SYNONYMES = {
    "amour": "amour-love-sex", "love": "amour-love-sex", "sex": "amour-love-sex",
    "romantique": "amour-love-sex", "romance": "amour-love-sex",
    "fete": "soiree-internationale", "festif": "soiree-internationale",
    "dansant": "soiree-internationale", "soiree": "soiree-internationale",
    "internationale": "soiree-internationale", "francophone": "soiree-francophone",
    "cafe": "cafe-petit-dej", "petit dejeuner": "cafe-petit-dej",
    "coworking": "coworking-travail-detente", "travail": "coworking-travail-detente",
    "detente": "coworking-travail-detente", "concentration": "coworking-travail-detente",
    "chanson francaise": "chanson-francaise", "variete": "chanson-francaise",
    "melancolie": "melancolie", "melancolique": "melancolie", "triste": "melancolie",
    "sport": "sport-gym", "gym": "sport-gym", "energie": "sport-gym", "motivant": "sport-gym",
}


def get_progress() -> dict:
    return dict(_progress)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip(" .,-")


# Texte normalisé (labels + synonymes) -> slug.
_NORM_TO_SLUG: dict[str, str] = {_norm(label): slug for slug, label in AMBIANCE_LABELS.items()}
_NORM_TO_SLUG.update(_SYNONYMES)


def build_prompt(track: dict) -> str:
    lignes = "\n".join(f"- {AMBIANCE_LABELS[slug]} : {desc}" for slug, desc in AMBIANCES.items())
    return (
        "Tu classes un morceau de musique par ambiance. Ambiances possibles :\n"
        f"{lignes}\n\n"
        f"Morceau : artiste={track.get('artist','')}, album={track.get('album','')}, "
        f"titre={track.get('title','')}, genre={track.get('genre','')}.\n"
        "Réponds uniquement par les ambiances adaptées séparées par des virgules "
        "(ou 'aucune'). Pas de phrase."
    )


def parse_ambiances(raw: str) -> list[str]:
    """Texte libre (Ollama) -> liste de slugs de playlists."""
    out: list[str] = []
    for token in raw.replace("\n", ",").split(","):
        slug = _NORM_TO_SLUG.get(_norm(token))
        if slug and slug not in out:
            out.append(slug)
    return out


def _pending_tracks(session: Session) -> list[MusicTrack]:
    """Morceaux à classer : uniquement ceux jamais traités (classified=False).

    Un morceau classé sans ambiance est un résultat valide (« aucune playlist
    adaptée ») : il n'est pas repris ici.
    """
    return list(session.exec(select(MusicTrack).where(MusicTrack.classified == False)).all())  # noqa: E712


def classify_untagged(session: Session, *, generate=None, classify_lot=None) -> dict:
    """Classe les morceaux en attente.

    - ``classify_lot`` (lots de dicts -> liste d'ambiances par morceau) : API Claude.
    - ``generate`` (prompt -> texte) : Ollama unitaire.
    - Aucun des deux fourni : Claude si la clé API est configurée, sinon Ollama.
    """
    tracks = _pending_tracks(session)
    _progress.update(n_done=0, n_total=len(tracks), active=True, error=None)
    try:
        if generate is None and classify_lot is None:
            if deepseek_client.is_configured():
                classify_lot = deepseek_client.classify_batch
            elif claude_client.is_configured():
                classify_lot = claude_client.classify_batch
            else:
                generate = ollama_client.generate
        if classify_lot is not None:
            classes = _classify_par_lots(session, tracks, classify_lot)
        else:
            classes = _classify_unitaire(session, tracks, generate)
    finally:
        _progress["active"] = False
    return {"classes": classes, "total": len(tracks)}


def _classify_par_lots(session: Session, tracks: list[MusicTrack], classify_lot) -> int:
    """Chemin API Claude : un appel par lot. Tout morceau d'un lot réussi est
    marqué classé, même sans ambiance ; un lot en échec reste réessayable."""
    classes = 0
    fails = 0
    # Snapshot des métadonnées AVANT toute écriture : `session.commit()` expire les
    # objets ORM (expire_on_commit), après quoi `model_dump()` renvoie des champs
    # vides/absents — le classifieur recevrait des morceaux vides dès le 2e lot.
    snapshot = [t.model_dump() for t in tracks]
    for i in range(0, len(tracks), claude_client.BATCH_SIZE):
        lot = tracks[i:i + claude_client.BATCH_SIZE]
        lot_dicts = snapshot[i:i + claude_client.BATCH_SIZE]
        try:
            resultats = classify_lot(lot_dicts)
        except Exception:
            fails += 1
            if fails >= 2:
                _progress["error"] = (
                    "API Claude indisponible. Classement interrompu — vérifie "
                    "ANTHROPIC_API_KEY et la connexion, puis relance."
                )
                break
            continue
        fails = 0
        for track, ambiances in zip(lot, resultats):
            for amb in ambiances:
                session.add(TrackAmbiance(track_id=track.id, ambiance=amb, source="auto"))
            track.classified = True
            session.add(track)
            if ambiances:
                classes += 1
            _progress["n_done"] += 1
        session.commit()
    return classes


def _classify_unitaire(session: Session, tracks: list[MusicTrack], generate) -> int:
    """Chemin Ollama : un morceau par appel (les lots font dérailler les petits
    modèles locaux)."""
    classes = 0
    fails = 0
    # Snapshot AVANT les commits (cf. _classify_par_lots) : sinon les morceaux
    # suivants seraient envoyés vides après l'expiry du premier commit.
    snapshot = [t.model_dump() for t in tracks]
    for track, data in zip(tracks, snapshot):
        try:
            raw = generate(build_prompt(data))
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
        ambiances = parse_ambiances(raw)
        for amb in ambiances:
            session.add(TrackAmbiance(track_id=track.id, ambiance=amb, source="auto"))
        track.classified = True
        session.add(track)
        session.commit()
        if ambiances:
            classes += 1
        _progress["n_done"] += 1
    return classes


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
