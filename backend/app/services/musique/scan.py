"""Scan de la bibliothèque musicale (mutagen) → table MusicTrack."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.musique import MusicTrack
from app.services.musique.constants import AUDIO_EXTENSIONS

_COVER_NAMES = ("Folder.jpg", "folder.jpg", "cover.jpg", "cover.png", "Cover.jpg")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def relative_to_root(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def find_cover(album_dir: Path) -> Path | None:
    for name in _COVER_NAMES:
        candidate = album_dir / name
        if candidate.exists():
            return candidate
    # Repli : pochette au nom quelconque (rip Spotify/web) — première image du dossier.
    for candidate in sorted(album_dir.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in _IMAGE_EXTENSIONS:
            return candidate
    return None


def extract_metadata(path: Path) -> dict:
    """Tags via mutagen ; repli sur l'arborescence artiste/album/fichier."""
    import mutagen

    artist = album = title = genre = ""
    duree_sec: int | None = None
    try:
        audio = mutagen.File(path, easy=True)
        if audio is not None:
            def first(key: str) -> str:
                v = audio.get(key)
                return str(v[0]) if v else ""
            artist = first("artist")
            album = first("album")
            title = first("title")
            genre = first("genre")
            if audio.info and getattr(audio.info, "length", None):
                duree_sec = int(audio.info.length)
    except Exception:
        pass
    # Repli sur l'arborescence .../Artiste/Album/Fichier
    if not artist and len(path.parts) >= 3:
        artist = path.parent.parent.name
    if not album:
        album = path.parent.name
    if not title:
        title = path.stem
    return {"artist": artist, "album": album, "title": title, "genre": genre, "duree_sec": duree_sec}


def scan_library(session: Session, root: Path) -> dict:
    """Indexe les fichiers audio sous root (idempotent, upsert par path)."""
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"Dossier musique introuvable : {root}")
    ajoutes = majs = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        rel = relative_to_root(path, root)
        meta = extract_metadata(path)
        cover = find_cover(path.parent)
        cover_rel = relative_to_root(cover, root) if cover else None
        track = session.exec(select(MusicTrack).where(MusicTrack.path == rel)).first()
        if track is None:
            track = MusicTrack(path=rel, cover=cover_rel, **meta)
            session.add(track)
            ajoutes += 1
        else:
            for k, v in meta.items():
                setattr(track, k, v)
            track.cover = cover_rel
            session.add(track)
            majs += 1
    session.commit()
    total = len(session.exec(select(MusicTrack)).all())
    return {"ajoutes": ajoutes, "majs": majs, "total": total}
