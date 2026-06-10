"""Playlists d'ambiance : appartenance, reco, export M3U."""
from __future__ import annotations


def to_m3u(tracks: list[dict], *, relatif: bool = True) -> str:
    """Construit un .m3u (chemins relatifs) lisible par Poweramp."""
    lines = ["#EXTM3U"]
    for t in tracks:
        dur = t.get("duree_sec") or -1
        artist = t.get("artist", "")
        title = t.get("title", "")
        lines.append(f"#EXTINF:{dur},{artist} - {title}")
        lines.append(t["path"])
    return "\n".join(lines) + "\n"


def reco_bibliotheque(tracks_in: list[dict], tracks_out: list[dict]) -> list[dict]:
    """Parmi tracks_out, ceux partageant artiste OU genre avec tracks_in.

    Triés par nombre de recoupements décroissant (artistes + genres communs).
    """
    artists = {t.get("artist", "").lower() for t in tracks_in if t.get("artist")}
    genres = {t.get("genre", "").lower() for t in tracks_in if t.get("genre")}
    scored = []
    for t in tracks_out:
        score = 0
        if t.get("artist", "").lower() in artists:
            score += 1
        if t.get("genre", "").lower() in genres:
            score += 1
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda st: st[0], reverse=True)
    return [t for _, t in scored]
