"""Normalise les métadonnées entre la bibliothèque Qobuz (FLAC) et
les téléchargements MP3, toutes deux hébergées sur le NAS.

État constaté (audit avant écriture, voir music_survey) : les FLAC Qobuz ont
déjà genre + pochette embarquée + tracknumber non zero-paddé sur 100% des
fichiers. Les MP3 ont déjà pochette embarquée + format "N/total" sur TRCK sur
100% des fichiers -- seul le GENRE manque sur 100% des MP3 (aucun tag TCON).
Ce script comble ce trou en deux passes :
  1. Match par artiste contre la bibliothèque FLAC (déjà taggée par Qobuz,
     source la plus fiable) -- aucun appel réseau.
  2. Pour les artistes sans correspondance FLAC : lookup MusicBrainz (tag le
     plus utilisé de l'artiste), rate-limité à 1 req/s (politique de l'API
     publique, pas de clé requise).
Un artiste sans correspondance ni résultat MusicBrainz reste SANS genre
plutôt que de deviner -- une mauvaise donnée écrite dans un fichier est pire
qu'une donnée absente. Le script journalise chaque décision.

Ré-exécutable sans risque : ne touche jamais un fichier qui a déjà un genre.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

from mutagen.flac import FLAC
from mutagen.mp3 import MP3

MUSIC_DIR = Path("Z:/Musique/Qobuz")
TELE_DIR = Path("Z:/Musique/Musique Tele")
MB_USER_AGENT = "mission-control-music-normalizer/1.0 (personal use)"


def build_artist_genre_map(flac_dir: Path) -> dict[str, str]:
    """Artiste (minuscule) -> genre le plus fréquent dans sa discographie FLAC."""
    counters: dict[str, Counter] = {}
    for f in flac_dir.rglob("*.flac"):
        try:
            audio = FLAC(f)
        except Exception:
            continue
        genre = (audio.get("genre") or [None])[0]
        artist = (audio.get("albumartist") or audio.get("artist") or [None])[0]
        if genre and artist:
            counters.setdefault(artist.strip().lower(), Counter())[genre] += 1
    return {artist: counter.most_common(1)[0][0] for artist, counter in counters.items()}


def musicbrainz_genre(artist: str) -> str | None:
    """Tag le plus utilisé de l'artiste sur MusicBrainz, ou None si introuvable."""
    import requests

    try:
        r = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": f'artist:"{artist}"', "fmt": "json", "limit": 1},
            headers={"User-Agent": MB_USER_AGENT}, timeout=10,
        )
        r.raise_for_status()
        artists = r.json().get("artists") or []
        if not artists:
            return None
        tags = artists[0].get("tags") or []
        if not tags:
            return None
        best = max(tags, key=lambda t: t.get("count", 0))
        return best["name"].title()
    except Exception:
        return None


def normalize_mp3_genres(tele_dir: Path, artist_genre: dict[str, str], *, use_musicbrainz: bool = True) -> list[dict]:
    """Écrit le tag genre (TCON) manquant sur chaque MP3, best-effort. Renvoie
    un journal `[{"file", "artist", "genre"|None, "source"}]` par fichier."""
    log: list[dict] = []
    mb_cache: dict[str, str | None] = {}

    for f in sorted(tele_dir.rglob("*.mp3")):
        try:
            audio = MP3(f)
        except Exception as exc:
            log.append({"file": str(f), "artist": None, "genre": None, "source": f"ERROR: {exc}"})
            continue
        tags = audio.tags
        if tags and tags.getall("TCON"):
            continue  # déjà tagué -> ré-exécution sans risque

        artist = str((tags.get("TPE2") or tags.get("TPE1") or [""])[0] if tags else "").strip()
        key = artist.lower()
        genre, source = None, None

        if key in artist_genre:
            genre, source = artist_genre[key], "flac-library"
        elif use_musicbrainz and artist:
            if key not in mb_cache:
                mb_cache[key] = musicbrainz_genre(artist)
                time.sleep(1.0)  # politique MusicBrainz : 1 req/s max
            genre = mb_cache[key]
            source = "musicbrainz" if genre else "not-found"

        if genre and tags is not None:
            from mutagen.id3 import TCON
            tags.add(TCON(encoding=3, text=[genre]))
            audio.save()

        log.append({"file": str(f), "artist": artist, "genre": genre, "source": source or "not-found"})

    return log


def main() -> None:
    if not MUSIC_DIR.exists() or not TELE_DIR.exists():
        print(f"Dossier(s) introuvable(s) : {MUSIC_DIR} / {TELE_DIR}")
        sys.exit(1)

    print(f"Construction de la table artiste->genre depuis {MUSIC_DIR} ...")
    artist_genre = build_artist_genre_map(MUSIC_DIR)
    print(f"  {len(artist_genre)} artistes avec genre connu (bibliothèque Qobuz).")

    print(f"Normalisation des genres MP3 dans {TELE_DIR} (MusicBrainz en repli, ~1s/artiste inconnu) ...")
    log = normalize_mp3_genres(TELE_DIR, artist_genre)

    by_source = Counter(entry["source"] for entry in log)
    print("\nRésumé :")
    for source, count in by_source.most_common():
        print(f"  {source}: {count}")

    not_found = [e for e in log if e["source"] == "not-found"]
    if not_found:
        print(f"\n{len(not_found)} fichier(s) sans genre trouvé (laissés tels quels) :")
        for e in not_found:
            print(f"  - {Path(e['file']).name} (artiste: {e['artist']})")


if __name__ == "__main__":
    main()
