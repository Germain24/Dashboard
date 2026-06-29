"""Classement des morceaux par lots via l'API DeepSeek (compatible OpenAI).

Alternative à l'API Claude : DeepSeek expose un endpoint Chat Completions
compatible OpenAI avec un mode JSON (`response_format={"type": "json_object"}`).
On lui fait classer un lot entier en un appel ; la sortie est un objet JSON
`{"resultats": [{"index": N, "ambiances": [labels]}]}` qu'on parse puis convertit
en slugs. Comme pour Claude, les morceaux déjà classés ne sont jamais renvoyés.
"""
from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCES, LABEL_TO_SLUG

# Taille de lot : assez grand pour limiter les appels, assez petit pour une
# réponse JSON fiable.
BATCH_SIZE = 20


def is_configured() -> bool:
    """True si une clé API DeepSeek est renseignée (.env DEEPSEEK_API_KEY)."""
    return bool(settings.deepseek_api_key)


def build_batch_prompt(tracks: list[dict]) -> str:
    lignes = "\n".join(f"- {AMBIANCE_LABELS[slug]} : {desc}" for slug, desc in AMBIANCES.items())
    morceaux = "\n".join(
        f"{i}. artiste={t.get('artist', '')}, album={t.get('album', '')}, "
        f"titre={t.get('title', '')}, genre={t.get('genre', '')}"
        for i, t in enumerate(tracks, start=1)
    )
    labels = ", ".join(f'"{label}"' for label in AMBIANCE_LABELS.values())
    return (
        "Tu classes des morceaux de musique par ambiance pour des playlists "
        "personnelles. Ambiances possibles :\n"
        f"{lignes}\n\n"
        "Pour chaque morceau, attribue les ambiances réellement adaptées "
        "(0 à 3). Si aucune ne convient (dialogue, interlude, jingle...), "
        "renvoie une liste vide.\n\n"
        f"Morceaux :\n{morceaux}\n\n"
        "Réponds UNIQUEMENT par un objet JSON de la forme :\n"
        '{"resultats": [{"index": <numéro du morceau>, "ambiances": [<ambiances>]}]}\n'
        f"Chaque ambiance doit être exactement l'une de : {labels}. "
        "Un objet par morceau, dans l'ordre."
    )


def classify_batch(tracks: list[dict], *, model: str | None = None, _post=None) -> list[list[str]]:
    """Classe un lot de morceaux en un appel API. Retourne, pour chaque morceau
    (même ordre que l'entrée), la liste de ses slugs d'ambiance (possiblement vide).

    Lève en cas d'échec API : l'appelant décide quoi marquer comme classé.
    """
    post = _post or httpx.post
    resp = post(
        f"{settings.deepseek_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model or settings.musique_deepseek_model,
            "messages": [
                {"role": "system", "content": "Tu réponds uniquement par du JSON valide."},
                {"role": "user", "content": build_batch_prompt(tracks)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "stream": False,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(text)

    out: list[list[str]] = [[] for _ in tracks]
    for item in data.get("resultats", []):
        i = item.get("index", 0) - 1
        if not 0 <= i < len(tracks):
            continue
        vues: list[str] = []
        for amb in item.get("ambiances", []):
            slug = LABEL_TO_SLUG.get(amb)
            if slug and slug not in vues:
                vues.append(slug)
        out[i] = vues
    return out
