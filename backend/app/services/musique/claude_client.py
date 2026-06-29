"""Classement des morceaux par lots via l'API Claude (Anthropic).

Contrairement aux petits modèles Ollama locaux (qui s'effondrent sur les
prompts par lot), Claude classe de façon fiable des lots entiers en un appel :
la sortie est contrainte par un schéma JSON (structured outputs), donc pas de
parsing de texte libre. Utilisé pour les nouveaux morceaux ajoutés à la
bibliothèque ; les morceaux déjà classés ne sont jamais renvoyés à l'API.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCES, LABEL_TO_SLUG

# Taille de lot : assez grand pour limiter le nombre d'appels, assez petit
# pour une réponse JSON courte et fiable.
BATCH_SIZE = 20

_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "resultats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "ambiances": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(AMBIANCE_LABELS.values())},
                    },
                },
                "required": ["index", "ambiances"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["resultats"],
    "additionalProperties": False,
}


def is_configured() -> bool:
    """True si une clé API Anthropic est renseignée (.env ANTHROPIC_API_KEY)."""
    return bool(settings.anthropic_api_key)


def build_batch_prompt(tracks: list[dict]) -> str:
    lignes = "\n".join(f"- {AMBIANCE_LABELS[slug]} : {desc}" for slug, desc in AMBIANCES.items())
    morceaux = "\n".join(
        f"{i}. artiste={t.get('artist', '')}, album={t.get('album', '')}, "
        f"titre={t.get('title', '')}, genre={t.get('genre', '')}"
        for i, t in enumerate(tracks, start=1)
    )
    return (
        "Tu classes des morceaux de musique par ambiance pour des playlists "
        "personnelles. Ambiances possibles :\n"
        f"{lignes}\n\n"
        "Pour chaque morceau, attribue les ambiances réellement adaptées "
        "(0 à 3). Si aucune ne convient (dialogue, interlude, jingle...), "
        "renvoie une liste vide. Réponds pour chaque index.\n\n"
        f"Morceaux :\n{morceaux}"
    )


def classify_batch(tracks: list[dict], *, model: str | None = None, _create=None) -> list[list[str]]:
    """Classe un lot de morceaux en un appel API. Retourne, pour chaque morceau
    (même ordre que l'entrée), la liste de ses ambiances (possiblement vide).

    Lève en cas d'échec API : l'appelant décide quoi marquer comme classé.
    """
    if _create is None:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        _create = client.messages.create

    resp = _create(
        model=model or settings.musique_claude_model,
        max_tokens=4000,
        output_config={"format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": build_batch_prompt(tracks)}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
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
