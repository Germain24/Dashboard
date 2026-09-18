"""Service TMDB — recherche & détails (dégradation gracieuse sans clé) (#535)."""

from __future__ import annotations

import time
from typing import Any

_POSTER_BASE = "https://image.tmdb.org/t/p/w342"
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 3600.0  # 1h


def _cached(key: str, ttl: float = _CACHE_TTL) -> Any | None:
    entry = _CACHE.get(key)
    if entry and (time.monotonic() - entry[0]) < ttl:
        return entry[1]
    return None


def _store(key: str, value: Any) -> Any:
    _CACHE[key] = (time.monotonic(), value)
    return value


def _map_movie(r: dict) -> dict:
    return {
        "tmdb_id": r.get("id"),
        "titre": r.get("title") or r.get("original_title", ""),
        "annee": int(r["release_date"][:4]) if r.get("release_date") else None,
        "genres": [],
        "poster_url": (_POSTER_BASE + r["poster_path"]) if r.get("poster_path") else None,
        "synopsis": r.get("overview", ""),
        "type": "film",
        "duree_min": r.get("runtime"),
    }


def _map_tv(r: dict) -> dict:
    return {
        "tmdb_id": r.get("id"),
        "titre": r.get("name") or r.get("original_name", ""),
        "annee": int(r["first_air_date"][:4]) if r.get("first_air_date") else None,
        "genres": [],
        "poster_url": (_POSTER_BASE + r["poster_path"]) if r.get("poster_path") else None,
        "synopsis": r.get("overview", ""),
        "type": "serie",
        "nb_saisons": r.get("number_of_seasons"),
        "nb_episodes_total": r.get("number_of_episodes"),
    }


def search(query: str, media_type: str = "film", api_key: str = "") -> list[dict]:
    """Recherche TMDB. Retourne [] si pas de clé (mode manuel)."""
    if not api_key or not query.strip():
        return []

    cache_key = f"search:{media_type}:{query.lower()}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        import httpx
        endpoint = "movie" if media_type == "film" else "tv"
        r = httpx.get(
            f"https://api.themoviedb.org/3/search/{endpoint}",
            params={"api_key": api_key, "query": query, "language": "fr-FR"},
            timeout=10.0,
        )
        r.raise_for_status()
        mapper = _map_movie if media_type == "film" else _map_tv
        results = [mapper(item) for item in r.json().get("results", [])[:10]]
        return _store(cache_key, results)
    except Exception:
        return []


def get_details(tmdb_id: int, media_type: str = "film", api_key: str = "") -> dict | None:
    """Détails d'un item TMDB. Retourne None si pas de clé ou erreur."""
    if not api_key:
        return None

    cache_key = f"details:{media_type}:{tmdb_id}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        import httpx
        endpoint = "movie" if media_type == "film" else "tv"
        r = httpx.get(
            f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}",
            params={"api_key": api_key, "language": "fr-FR"},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
        mapper = _map_movie if media_type == "film" else _map_tv
        result = mapper(data)
        # genres enrichis depuis les détails
        result["genres"] = [g["name"] for g in data.get("genres", [])]
        if media_type == "film":
            result["duree_min"] = data.get("runtime")
        else:
            result["nb_saisons"] = data.get("number_of_seasons")
            result["nb_episodes_total"] = data.get("number_of_episodes")
        return _store(cache_key, result)
    except Exception:
        return None
