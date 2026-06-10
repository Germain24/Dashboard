# Module Musique — playlists par ambiance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Indexer la bibliothèque musicale locale, classer chaque morceau par ambiance via Ollama (autonome, sans chat), et gérer des playlists d'ambiance (lecteur intégré + export .m3u + reco), morceaux multi-ambiances.

**Architecture:** Pattern module existant (models → services → `routes_musique.py` → front). Le classement/découverte appellent Ollama en local ; tout le reste est déterministe. Fonctions pures (scan helpers, m3u, parsing, reco) testées sans réseau ; l'appel Ollama est injecté en test.

**Tech Stack:** FastAPI + SQLModel + Alembic + pytest (uv) ; `mutagen` (tags audio) ; Ollama HTTP local. Frontend Next.js + Vitest.

**Référence :** `docs/superpowers/specs/2026-06-09-musique-ambiances-design.md`.

---

## File Structure

- Modify `backend/pyproject.toml` (+ lock) — dépendance `mutagen`.
- Modify `backend/app/core/config.py` — `music_dir`, `musique_ollama_host`, `musique_ollama_model`.
- Create `backend/app/services/musique/__init__.py`, `constants.py`, `scan.py`, `ollama_client.py`, `classify.py`, `playlists.py`, `discovery.py`.
- Create `backend/app/models/musique.py` — `MusicTrack`, `TrackAmbiance`.
- Modify `backend/app/models/__init__.py`, `backend/app/api/__init__.py`, `backend/app/main.py`.
- Create `backend/app/api/routes_musique.py`.
- Create `backend/alembic/versions/<rev>_musique.py` (autogénérée).
- Create `backend/tests/test_musique/__init__.py`, `test_scan.py`, `test_classify.py`, `test_playlists.py`, `test_api.py`.
- Create `frontend/lib/musique.ts`.
- Modify `frontend/src/app/musique/page.tsx`; create `frontend/src/app/musique/loading.tsx`.
- Create `frontend/components/musique/Musique.tsx`, `Bibliotheque.tsx`, `Ambiances.tsx`, `Decouverte.tsx`.

---

## Task 1: Dépendance, constantes & config

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/services/musique/__init__.py` (vide), `backend/app/services/musique/constants.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Ajouter mutagen**

Run (depuis `backend/`) : `uv add mutagen`
Expected: `mutagen` ajouté à `pyproject.toml` + `uv.lock` mis à jour.

- [ ] **Step 2: Constantes d'ambiances**

`backend/app/services/musique/constants.py` :
```python
"""Ambiances musicales et leurs définitions (pour guider Ollama)."""

AMBIANCES: dict[str, str] = {
    "café": "léger, acoustique, agréable en fond",
    "loft": "chill/électro posé, ambiance appartement",
    "coworking": "rythmé mais non distrayant, pour travailler",
    "étude": "calme, instrumental, concentration",
    "repos": "très calme, détente, sieste",
    "énergie": "entraînant, motivant, tempo élevé",
    "soirée": "festif, dansant",
    "love": "chansons d'amour, romantiques (type date)",
}

AMBIANCE_NAMES = list(AMBIANCES)
AUDIO_EXTENSIONS = {".mp3", ".flac", ".dsf"}
```

- [ ] **Step 3: Config**

Dans `backend/app/core/config.py`, après le bloc `ical_sync_urls`/`ical_sync_url_list`, ajouter :
```python
    # --- Musique (module playlists par ambiance) ---
    music_dir: str = "C:/Users/germa/Music"
    musique_ollama_host: str = "http://localhost:11434"
    musique_ollama_model: str = "qwen2.5-coder:1.5b"
```

- [ ] **Step 4: Vérifier**

Run : `uv run python -c "from app.core.config import settings; from app.services.musique.constants import AMBIANCE_NAMES; print(settings.music_dir, AMBIANCE_NAMES)"`
Expected: affiche le chemin et la liste des 8 ambiances.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock app/services/musique/__init__.py app/services/musique/constants.py app/core/config.py
git commit -m "feat(musique): deps mutagen + constantes ambiances + config"
```

---

## Task 2: Modèles + migration

**Files:**
- Create: `backend/app/models/musique.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<rev>_musique.py`

- [ ] **Step 1: Modèles**

`backend/app/models/musique.py` :
```python
"""Module Musique — bibliothèque + appartenance multi-ambiances."""
import datetime as dt

from sqlmodel import Field, SQLModel


class MusicTrack(SQLModel, table=True):
    __tablename__ = "music_track"
    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)  # relatif à music_dir
    artist: str = ""
    album: str = ""
    title: str = ""
    genre: str = ""
    duree_sec: int | None = None
    cover: str | None = None      # chemin relatif de la pochette
    classified: bool = False      # déjà passé par Ollama
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)


class TrackAmbiance(SQLModel, table=True):
    __tablename__ = "track_ambiance"
    id: int | None = Field(default=None, primary_key=True)
    track_id: int = Field(foreign_key="music_track.id", index=True)
    ambiance: str
    source: str = "auto"          # auto | manuel
```

- [ ] **Step 2: Importer les modèles**

Dans `backend/app/models/__init__.py`, après l'import `journal`, ajouter :
```python
from app.models.musique import MusicTrack, TrackAmbiance  # noqa: F401
```

- [ ] **Step 3: Générer + appliquer la migration**

Run : `uv run alembic revision --autogenerate -m "musique tracks" && uv run alembic upgrade head`
Expected: migration créant `music_track` + `track_ambiance`.

- [ ] **Step 4: Vérifier modèles == migrations**

Run : `uv run pytest tests/test_migrations.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/musique.py app/models/__init__.py alembic/versions
git commit -m "feat(musique): modeles MusicTrack + TrackAmbiance + migration"
```

---

## Task 3: Scan de la bibliothèque

**Files:**
- Create: `backend/app/services/musique/scan.py`
- Test: `backend/tests/test_musique/__init__.py` (vide), `backend/tests/test_musique/test_scan.py`

- [ ] **Step 1: Tests des helpers purs (échouent)**

`backend/tests/test_musique/test_scan.py` :
```python
from pathlib import Path

from app.services.musique import scan


def test_relative_to_root_uses_forward_slashes(tmp_path):
    root = tmp_path
    p = tmp_path / "Artiste" / "Album" / "01.flac"
    assert scan.relative_to_root(p, root) == "Artiste/Album/01.flac"


def test_find_cover_prefers_folder_jpg(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    (album / "Folder.jpg").write_bytes(b"x")
    assert scan.find_cover(album) == album / "Folder.jpg"


def test_find_cover_none_when_absent(tmp_path):
    album = tmp_path / "Album"
    album.mkdir()
    assert scan.find_cover(album) is None


def test_scan_library_indexes_audio(tmp_path, monkeypatch):
    # Arborescence factice : 1 morceau flac + une pochette.
    album = tmp_path / "Artiste" / "Album"
    album.mkdir(parents=True)
    (album / "01 - Titre.flac").write_bytes(b"x")
    (album / "Folder.jpg").write_bytes(b"x")
    # mutagen ne lit pas un faux fichier -> on stub extract_metadata.
    monkeypatch.setattr(scan, "extract_metadata", lambda p: {
        "artist": "Artiste", "album": "Album", "title": "Titre", "genre": "", "duree_sec": 200})

    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        res = scan.scan_library(s, tmp_path)
        assert res["ajoutes"] == 1
        from app.models.musique import MusicTrack
        from sqlmodel import select
        t = s.exec(select(MusicTrack)).first()
        assert t.path == "Artiste/Album/01 - Titre.flac"
        assert t.cover == "Artiste/Album/Folder.jpg"
        assert t.title == "Titre"
```

- [ ] **Step 2: Lancer (échoue)**

Run : `uv run pytest tests/test_musique/test_scan.py -q`
Expected: FAIL (`ModuleNotFoundError` scan).

- [ ] **Step 3: Implémenter**

`backend/app/services/musique/scan.py` :
```python
"""Scan de la bibliothèque musicale (mutagen) → table MusicTrack."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.musique import MusicTrack
from app.services.musique.constants import AUDIO_EXTENSIONS

_COVER_NAMES = ("Folder.jpg", "folder.jpg", "cover.jpg", "cover.png", "Cover.jpg")


def relative_to_root(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def find_cover(album_dir: Path) -> Path | None:
    for name in _COVER_NAMES:
        candidate = album_dir / name
        if candidate.exists():
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
```

- [ ] **Step 4: Lancer (passe)**

Run : `uv run pytest tests/test_musique/test_scan.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/musique/scan.py tests/test_musique
git commit -m "feat(musique): scan bibliotheque (mutagen, pochettes Folder.jpg)"
```

---

## Task 4: Export M3U (pur)

**Files:**
- Create: `backend/app/services/musique/playlists.py`
- Test: `backend/tests/test_musique/test_playlists.py`

- [ ] **Step 1: Test (échoue)**

`backend/tests/test_musique/test_playlists.py` :
```python
from app.services.musique.playlists import reco_bibliotheque, to_m3u


def test_to_m3u_relative_paths():
    tracks = [
        {"path": "A/Alb/01.flac", "artist": "A", "title": "T1", "duree_sec": 200},
        {"path": "B/Alb/02.mp3", "artist": "B", "title": "T2", "duree_sec": None},
    ]
    m = to_m3u(tracks)
    lines = m.splitlines()
    assert lines[0] == "#EXTM3U"
    assert "#EXTINF:200,A - T1" in lines
    assert "A/Alb/01.flac" in lines
    assert "#EXTINF:-1,B - T2" in lines  # durée inconnue -> -1


def test_reco_scores_by_shared_artist_or_genre():
    tracks_in = [{"id": 1, "artist": "X", "genre": "jazz"}]
    tracks_out = [
        {"id": 2, "artist": "X", "genre": "rock"},   # même artiste -> score 1
        {"id": 3, "artist": "Z", "genre": "jazz"},   # même genre -> score 1
        {"id": 4, "artist": "Q", "genre": "metal"},  # rien -> exclu
    ]
    reco = reco_bibliotheque(tracks_in, tracks_out)
    ids = [t["id"] for t in reco]
    assert set(ids) == {2, 3} and 4 not in ids
```

- [ ] **Step 2: Lancer (échoue)**

Run : `uv run pytest tests/test_musique/test_playlists.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter (purs ; CRUD ajouté en Task 6)**

`backend/app/services/musique/playlists.py` :
```python
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
```

- [ ] **Step 4: Lancer (passe)**

Run : `uv run pytest tests/test_musique/test_playlists.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/musique/playlists.py tests/test_musique/test_playlists.py
git commit -m "feat(musique): to_m3u + reco_bibliotheque (purs)"
```

---

## Task 5: Ollama + classement

**Files:**
- Create: `backend/app/services/musique/ollama_client.py`, `backend/app/services/musique/classify.py`
- Test: `backend/tests/test_musique/test_classify.py`

- [ ] **Step 1: Tests (échouent)**

`backend/tests/test_musique/test_classify.py` :
```python
from app.services.musique.classify import build_prompt, classify_untagged, parse_ambiances
from app.services.musique.constants import AMBIANCE_NAMES


def test_parse_ambiances_keeps_valid_only():
    assert parse_ambiances("café, étude", AMBIANCE_NAMES) == ["café", "étude"]
    assert parse_ambiances("Étude.", AMBIANCE_NAMES) == ["étude"]   # accents/casse/ponctuation
    assert parse_ambiances("inconnu", AMBIANCE_NAMES) == []
    assert parse_ambiances("aucune", AMBIANCE_NAMES) == []


def test_build_prompt_lists_ambiances():
    p = build_prompt({"artist": "A", "album": "B", "title": "T", "genre": "jazz"})
    assert "café" in p and "love" in p and "T" in p


def test_classify_untagged_creates_rows(monkeypatch):
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T"))
        s.commit()
        res = classify_untagged(s, generate=lambda prompt, **kw: "café, étude")
        assert res["classes"] == 1
        ambs = {ta.ambiance for ta in s.exec(select(TrackAmbiance)).all()}
        assert ambs == {"café", "étude"}
        t = s.exec(select(MusicTrack)).first()
        assert t.classified is True
```

- [ ] **Step 2: Lancer (échoue)**

Run : `uv run pytest tests/test_musique/test_classify.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implémenter le client Ollama**

`backend/app/services/musique/ollama_client.py` :
```python
"""Client Ollama minimal (génération non-stream). Aucun chat persistant."""
from __future__ import annotations

import httpx

from app.core.config import settings


def generate(prompt: str, *, host: str | None = None, model: str | None = None,
             _post=httpx.post) -> str:
    host = host or settings.musique_ollama_host
    model = model or settings.musique_ollama_model
    resp = _post(f"{host}/api/generate",
                 json={"model": model, "prompt": prompt, "stream": False}, timeout=120.0)
    resp.raise_for_status()
    return resp.json().get("response", "")
```

- [ ] **Step 4: Implémenter le classement**

`backend/app/services/musique/classify.py` :
```python
"""Classement autonome des morceaux par ambiance via Ollama."""
from __future__ import annotations

import unicodedata

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client
from app.services.musique.constants import AMBIANCES, AMBIANCE_NAMES

_progress = {"n_done": 0, "n_total": 0, "active": False}


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
    _progress.update(n_done=0, n_total=len(tracks), active=True)
    classes = 0
    try:
        for track in tracks:
            try:
                raw = generate(build_prompt(track.model_dump()))
                ambiances = parse_ambiances(raw, AMBIANCE_NAMES)
            except Exception:
                ambiances = []
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
```

- [ ] **Step 5: Lancer (passe)**

Run : `uv run pytest tests/test_musique/test_classify.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/services/musique/ollama_client.py app/services/musique/classify.py tests/test_musique/test_classify.py
git commit -m "feat(musique): classement ambiances via Ollama (parse robuste, progress)"
```

---

## Task 6: Appartenance + découverte

**Files:**
- Modify: `backend/app/services/musique/playlists.py`
- Create: `backend/app/services/musique/discovery.py`
- Test: `backend/tests/test_musique/test_playlists.py`

- [ ] **Step 1: Tests (échouent)**

Ajouter à `backend/tests/test_musique/test_playlists.py` :
```python
def test_set_membership_add_remove():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.playlists import set_membership

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac")); s.commit()
        set_membership(s, 1, "café", True)
        set_membership(s, 1, "café", True)  # idempotent
        assert len(s.exec(select(TrackAmbiance)).all()) == 1
        set_membership(s, 1, "café", False)
        assert s.exec(select(TrackAmbiance)).all() == []


def test_set_membership_rejects_unknown_ambiance():
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack
    from app.services.musique.playlists import set_membership
    import pytest

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac")); s.commit()
        with pytest.raises(ValueError):
            set_membership(s, 1, "inexistante", True)


def test_parse_suggestions_splits_list():
    from app.services.musique.discovery import parse_suggestions
    assert parse_suggestions("- Artiste A\n- Artiste B\n") == ["Artiste A", "Artiste B"]
    assert parse_suggestions("1. X\n2. Y") == ["X", "Y"]
```

- [ ] **Step 2: Lancer (échoue)**

Run : `uv run pytest tests/test_musique/test_playlists.py -q`
Expected: FAIL (set_membership / discovery manquants).

- [ ] **Step 3: Implémenter set_membership + playlist_tracks**

Ajouter à `backend/app/services/musique/playlists.py` (en tête, imports) :
```python
from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique.constants import AMBIANCE_NAMES
```
et les fonctions :
```python
def playlist_tracks(session: Session, ambiance: str) -> list[MusicTrack]:
    ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    if not ids:
        return []
    return list(session.exec(select(MusicTrack).where(MusicTrack.id.in_(ids))).all())  # type: ignore[attr-defined]


def set_membership(session: Session, track_id: int, ambiance: str, present: bool,
                   source: str = "manuel") -> None:
    if ambiance not in AMBIANCE_NAMES:
        raise ValueError(f"Ambiance inconnue : {ambiance}")
    row = session.exec(
        select(TrackAmbiance).where(TrackAmbiance.track_id == track_id)
        .where(TrackAmbiance.ambiance == ambiance)
    ).first()
    if present and row is None:
        session.add(TrackAmbiance(track_id=track_id, ambiance=ambiance, source=source))
        session.commit()
    elif not present and row is not None:
        session.delete(row)
        session.commit()
```

- [ ] **Step 4: Implémenter la découverte**

`backend/app/services/musique/discovery.py` :
```python
"""Suggestions d'artistes/genres à explorer (Ollama), pas de titres exacts."""
from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import ollama_client


def parse_suggestions(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        s = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
        if s:
            out.append(s)
    return out


def suggest_artists(session: Session, ambiance: str, *, generate=ollama_client.generate) -> list[str]:
    ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    artists = sorted({t.artist for t in session.exec(
        select(MusicTrack).where(MusicTrack.id.in_(ids))).all() if t.artist})[:20]  # type: ignore[attr-defined]
    if not artists:
        return []
    prompt = (
        f"Voici des artistes d'une playlist '{ambiance}': {', '.join(artists)}.\n"
        "Propose 10 autres artistes ou genres similaires à explorer (un par ligne, "
        "juste le nom, pas de titres de chansons)."
    )
    try:
        return parse_suggestions(generate(prompt))[:10]
    except Exception:
        return []
```

- [ ] **Step 5: Lancer (passe)**

Run : `uv run pytest tests/test_musique/test_playlists.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add app/services/musique/playlists.py app/services/musique/discovery.py tests/test_musique/test_playlists.py
git commit -m "feat(musique): appartenance playlists + decouverte Ollama"
```

---

## Task 7: Routes + montage statique

**Files:**
- Create: `backend/app/api/routes_musique.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/main.py`
- Test: `backend/tests/test_musique/test_api.py`

- [ ] **Step 1: Test API (échoue)**

`backend/tests/test_musique/test_api.py` :
```python
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


def _client(engine):
    def override():
        with Session(engine) as s:
            yield s
    app = create_app()
    app.dependency_overrides[get_session] = override
    from fastapi.testclient import TestClient
    return TestClient(app)


def _engine():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    return e


def test_ambiances_and_membership_and_export():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
    client = _client(engine)

    assert client.get("/musique/ambiances").status_code == 200
    r = client.put("/musique/tracks/1/ambiances/café")
    assert r.status_code == 204
    pl = client.get("/musique/playlists/café")
    assert pl.status_code == 200 and len(pl.json()) == 1
    m = client.get("/musique/playlists/café/export.m3u")
    assert m.status_code == 200 and m.text.startswith("#EXTM3U")
    assert client.delete("/musique/tracks/1/ambiances/café").status_code == 204
    assert client.get("/musique/playlists/café").json() == []
```

- [ ] **Step 2: Lancer (échoue)**

Run : `uv run pytest tests/test_musique/test_api.py -q`
Expected: FAIL (routes absentes).

- [ ] **Step 3: Implémenter les routes**

`backend/app/api/routes_musique.py` :
```python
"""Routes module Musique — bibliothèque, ambiances, playlists, export."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import get_session
from app.models.musique import MusicTrack, TrackAmbiance
from app.services.musique import classify, discovery, scan
from app.services.musique.constants import AMBIANCE_NAMES
from app.services.musique.playlists import playlist_tracks, reco_bibliotheque, set_membership, to_m3u

router = APIRouter()


def _track_dict(t: MusicTrack, ambiances: list[str]) -> dict:
    return {"id": t.id, "path": t.path, "artist": t.artist, "album": t.album,
            "title": t.title, "genre": t.genre, "duree_sec": t.duree_sec,
            "cover": t.cover, "ambiances": ambiances}


def _ambiances_for(session: Session, track_ids: list[int]) -> dict[int, list[str]]:
    rows = session.exec(select(TrackAmbiance).where(TrackAmbiance.track_id.in_(track_ids))).all() if track_ids else []  # type: ignore[attr-defined]
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r.track_id, []).append(r.ambiance)
    return out


@router.post("/scan")
def run_scan(session: Session = Depends(get_session)):
    try:
        return scan.scan_library(session, Path(settings.music_dir))
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@router.post("/classify", status_code=202)
def run_classify(background_tasks: BackgroundTasks):
    if classify.get_progress()["active"]:
        return {"message": "Classement déjà en cours"}
    from app.core.db import engine
    from sqlmodel import Session as S

    def job():
        with S(engine) as s:
            classify.classify_untagged(s)
    background_tasks.add_task(job)
    return {"message": "Classement démarré"}


@router.get("/classify/progress")
def classify_progress():
    return classify.get_progress()


@router.get("/tracks")
def list_tracks(session: Session = Depends(get_session), q: str | None = None,
                ambiance: str | None = None):
    stmt = select(MusicTrack)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(MusicTrack.title.ilike(like) | MusicTrack.artist.ilike(like))  # type: ignore[attr-defined]
    tracks = list(session.exec(stmt.limit(500)).all())
    amb_map = _ambiances_for(session, [t.id for t in tracks])
    rows = [_track_dict(t, amb_map.get(t.id, [])) for t in tracks]
    if ambiance:
        rows = [r for r in rows if ambiance in r["ambiances"]]
    return rows


@router.get("/ambiances")
def ambiances(session: Session = Depends(get_session)):
    counts: dict[str, int] = {a: 0 for a in AMBIANCE_NAMES}
    for r in session.exec(select(TrackAmbiance)).all():
        counts[r.ambiance] = counts.get(r.ambiance, 0) + 1
    return [{"ambiance": a, "count": counts.get(a, 0)} for a in AMBIANCE_NAMES]


@router.put("/tracks/{track_id}/ambiances/{ambiance}", status_code=204)
def add_membership(track_id: int, ambiance: str, session: Session = Depends(get_session)):
    try:
        set_membership(session, track_id, ambiance, True)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/tracks/{track_id}/ambiances/{ambiance}", status_code=204)
def remove_membership(track_id: int, ambiance: str, session: Session = Depends(get_session)):
    try:
        set_membership(session, track_id, ambiance, False)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/playlists/{ambiance}")
def playlist(ambiance: str, session: Session = Depends(get_session)):
    tracks = playlist_tracks(session, ambiance)
    return [_track_dict(t, [ambiance]) for t in tracks]


@router.get("/playlists/{ambiance}/reco")
def playlist_reco(ambiance: str, session: Session = Depends(get_session)):
    in_ids = session.exec(select(TrackAmbiance.track_id).where(TrackAmbiance.ambiance == ambiance)).all()
    tracks_in = [t.model_dump() for t in session.exec(select(MusicTrack).where(MusicTrack.id.in_(in_ids))).all()]  # type: ignore[attr-defined]
    tracks_out = [t.model_dump() for t in session.exec(select(MusicTrack).where(MusicTrack.id.notin_(in_ids))).all()] if in_ids else []  # type: ignore[attr-defined]
    return reco_bibliotheque(tracks_in, tracks_out)[:50]


@router.get("/playlists/{ambiance}/discovery")
def playlist_discovery(ambiance: str, session: Session = Depends(get_session)):
    return {"ambiance": ambiance, "suggestions": discovery.suggest_artists(session, ambiance)}


@router.get("/playlists/{ambiance}/export.m3u", response_class=PlainTextResponse)
def export_m3u(ambiance: str, session: Session = Depends(get_session)):
    tracks = [t.model_dump() for t in playlist_tracks(session, ambiance)]
    return PlainTextResponse(to_m3u(tracks), media_type="audio/x-mpegurl",
                             headers={"Content-Disposition": f'attachment; filename="{ambiance}.m3u"'})
```

Dans `backend/app/api/__init__.py` : ajouter `routes_musique,` à l'import (après `routes_livres,`) et la ligne d'enregistrement (après livres) :
```python
api_router.include_router(routes_musique.router, prefix="/musique", tags=["musique"])
```

- [ ] **Step 4: Monter les fichiers musique en statique**

Dans `backend/app/main.py`, juste après le bloc `for url, directory in (...)` existant (après la ligne `app.mount(... name=...)` du `for`, donc à l'intérieur du même `try`), ajouter un montage de la bibliothèque musicale (lecture seule, sans mkdir) :
```python
        music_path = Path(settings.music_dir)
        if music_path.exists():
            app.mount("/media/music", StaticFiles(directory=str(music_path)), name="media-music")
```
Ajouter en haut de `main.py` l'import `from pathlib import Path` s'il n'y est pas déjà, et `from app.core.config import settings` est déjà importé.

- [ ] **Step 5: Lancer (passe)**

Run : `uv run pytest tests/test_musique -q`
Expected: PASS (tous les tests musique).

- [ ] **Step 6: Commit**

```bash
git add app/api/routes_musique.py app/api/__init__.py app/main.py tests/test_musique/test_api.py
git commit -m "feat(musique): routes /musique + montage statique /media/music"
```

---

## Task 8: Client & types frontend

**Files:**
- Create: `frontend/lib/musique.ts`

- [ ] **Step 1: Implémenter**

`frontend/lib/musique.ts` :
```typescript
import { api } from "./api";
import { env } from "./env";

export const MEDIA_BASE = `${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/media/music`;

export interface Track {
  id: number; path: string; artist: string; album: string; title: string;
  genre: string; duree_sec: number | null; cover: string | null; ambiances: string[];
}
export interface AmbianceCount { ambiance: string; count: number; }
export interface ClassifyProgress { n_done: number; n_total: number; active: boolean; }

export const mediaUrl = (rel: string) => `${MEDIA_BASE}/${rel.split("/").map(encodeURIComponent).join("/")}`;

export const musiqueApi = {
  scan: () => api<{ ajoutes: number; majs: number; total: number }>("/musique/scan", { method: "POST" }),
  classify: () => api<{ message: string }>("/musique/classify", { method: "POST" }),
  progress: () => api<ClassifyProgress>("/musique/classify/progress"),
  tracks: (q = "", ambiance = "") => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (ambiance) p.set("ambiance", ambiance);
    return api<Track[]>(`/musique/tracks?${p}`);
  },
  ambiances: () => api<AmbianceCount[]>("/musique/ambiances"),
  playlist: (a: string) => api<Track[]>(`/musique/playlists/${encodeURIComponent(a)}`),
  reco: (a: string) => api<Track[]>(`/musique/playlists/${encodeURIComponent(a)}/reco`),
  discovery: (a: string) => api<{ ambiance: string; suggestions: string[] }>(`/musique/playlists/${encodeURIComponent(a)}/discovery`),
  addAmbiance: (id: number, a: string) => api<void>(`/musique/tracks/${id}/ambiances/${encodeURIComponent(a)}`, { method: "PUT" }),
  removeAmbiance: (id: number, a: string) => api<void>(`/musique/tracks/${id}/ambiances/${encodeURIComponent(a)}`, { method: "DELETE" }),
  exportUrl: (a: string) => `${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/musique/playlists/${encodeURIComponent(a)}/export.m3u`,
};
```

- [ ] **Step 2: Vérifier**

Run (depuis `frontend/`) : `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add lib/musique.ts
git commit -m "feat(musique): client + types frontend"
```

---

## Task 9: Bibliothèque (scan + classement + table)

**Files:**
- Create: `frontend/components/musique/Bibliotheque.tsx`

- [ ] **Step 1: Implémenter**

`frontend/components/musique/Bibliotheque.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { mediaUrl, musiqueApi, type Track } from "@/lib/musique";

export function Bibliotheque() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState<{ n_done: number; n_total: number } | null>(null);

  const load = () => musiqueApi.tracks(q).then(setTracks).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q]);

  const doScan = async () => {
    setBusy("Scan…");
    try { const r = await musiqueApi.scan(); alert(`Scan : ${r.ajoutes} ajoutés, ${r.total} au total`); await load(); }
    finally { setBusy(""); }
  };
  const doClassify = async () => {
    await musiqueApi.classify();
    const poll = setInterval(async () => {
      const p = await musiqueApi.progress().catch(() => null);
      if (!p) return;
      setProgress({ n_done: p.n_done, n_total: p.n_total });
      if (!p.active) { clearInterval(poll); setProgress(null); await load(); }
    }, 1500);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={() => void doScan()} disabled={!!busy}
          className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm">{busy || "Scanner"}</button>
        <button onClick={() => void doClassify()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm">Classer (Ollama)</button>
        {progress && <span className="text-xs text-[var(--muted-foreground)]">Classement {progress.n_done}/{progress.n_total}</span>}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher…"
          className="ml-auto px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {tracks.map((t) => (
          <div key={t.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2">
            {t.cover
              ? <img src={mediaUrl(t.cover)} alt="" className="h-12 w-12 rounded object-cover" />
              : <div className="h-12 w-12 rounded bg-[var(--muted)]" />}
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{t.title}</div>
              <div className="truncate text-xs text-[var(--muted-foreground)]">{t.artist} · {t.album}</div>
              <div className="text-xs text-[var(--ring)]">{t.ambiances.join(", ")}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier**

Run : `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add components/musique/Bibliotheque.tsx
git commit -m "feat(musique): onglet Bibliotheque (scan, classement, vignettes)"
```

---

## Task 10: Ambiances (lecteur + export + reco) + Découverte + page

**Files:**
- Create: `frontend/components/musique/Ambiances.tsx`, `frontend/components/musique/Decouverte.tsx`, `frontend/components/musique/Musique.tsx`
- Modify: `frontend/src/app/musique/page.tsx`
- Create: `frontend/src/app/musique/loading.tsx`

- [ ] **Step 1: Ambiances (playlist + lecteur HTML5 + export + reco)**

`frontend/components/musique/Ambiances.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { mediaUrl, musiqueApi, type AmbianceCount, type Track } from "@/lib/musique";

export function Ambiances() {
  const [ambiances, setAmbiances] = useState<AmbianceCount[]>([]);
  const [sel, setSel] = useState<string>("café");
  const [tracks, setTracks] = useState<Track[]>([]);
  const [reco, setReco] = useState<Track[]>([]);

  useEffect(() => { musiqueApi.ambiances().then(setAmbiances).catch(() => {}); }, []);
  const load = (a: string) => {
    musiqueApi.playlist(a).then(setTracks).catch(() => {});
    musiqueApi.reco(a).then(setReco).catch(() => {});
  };
  useEffect(() => { load(sel); /* eslint-disable-next-line */ }, [sel]);

  const add = async (id: number) => { await musiqueApi.addAmbiance(id, sel); load(sel); };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {ambiances.map((a) => (
          <button key={a.ambiance} onClick={() => setSel(a.ambiance)}
            className={`text-xs px-2.5 py-1 rounded-full border ${sel === a.ambiance
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>
            {a.ambiance} ({a.count})
          </button>
        ))}
        <a href={musiqueApi.exportUrl(sel)} className="ml-auto text-xs px-2.5 py-1 rounded-full border border-[var(--border)]">⬇ .m3u</a>
      </div>

      <div className="space-y-1">
        {tracks.map((t) => (
          <div key={t.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2">
            {t.cover && <img src={mediaUrl(t.cover)} alt="" className="h-10 w-10 rounded object-cover" />}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">{t.title} — <span className="text-[var(--muted-foreground)]">{t.artist}</span></div>
              <audio controls preload="none" src={mediaUrl(t.path)} className="h-8 w-full mt-1" />
            </div>
          </div>
        ))}
        {tracks.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Playlist vide — lance un classement ou ajoute depuis la reco.</p>}
      </div>

      {reco.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-1">Suggestions de ta bibliothèque</h3>
          <div className="space-y-1">
            {reco.slice(0, 15).map((t) => (
              <div key={t.id} className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{t.title} — <span className="text-[var(--muted-foreground)]">{t.artist}</span></span>
                <button onClick={() => void add(t.id)} className="text-xs px-2 py-0.5 rounded border border-[var(--border)]">+ ajouter</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Découverte**

`frontend/components/musique/Decouverte.tsx` :
```tsx
"use client";

import { useState } from "react";
import { musiqueApi } from "@/lib/musique";

const AMBIANCES = ["café", "loft", "coworking", "étude", "repos", "énergie", "soirée", "love"];

export function Decouverte() {
  const [sel, setSel] = useState("café");
  const [items, setItems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const go = async () => {
    setLoading(true);
    try { const r = await musiqueApi.discovery(sel); setItems(r.suggestions); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5 items-center">
        {AMBIANCES.map((a) => (
          <button key={a} onClick={() => setSel(a)}
            className={`text-xs px-2.5 py-1 rounded-full border ${sel === a
              ? "bg-[var(--ring)] text-white border-[var(--ring)]" : "border-[var(--border)]"}`}>{a}</button>
        ))}
        <button onClick={() => void go()} disabled={loading}
          className="ml-auto rounded-md border border-[var(--border)] px-3 py-1.5 text-sm">{loading ? "…" : "Suggérer (Ollama)"}</button>
      </div>
      <ul className="list-disc pl-5 text-sm space-y-0.5">
        {items.map((s, i) => <li key={i}>{s}</li>)}
      </ul>
      <p className="text-xs text-[var(--muted-foreground)]">Artistes/genres à explorer pour agrandir ta bibliothèque (suggestions locales, à vérifier).</p>
    </div>
  );
}
```

- [ ] **Step 3: Assemblage + page**

`frontend/components/musique/Musique.tsx` :
```tsx
"use client";

import { useState } from "react";
import { Bibliotheque } from "./Bibliotheque";
import { Ambiances } from "./Ambiances";
import { Decouverte } from "./Decouverte";

const TABS = [["ambiances", "Ambiances"], ["bibliotheque", "Bibliothèque"], ["decouverte", "Découverte"]] as const;

export default function Musique() {
  const [tab, setTab] = useState<string>("ambiances");
  return (
    <div className="space-y-5 p-4 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold">Musique</h1>
      <div className="flex gap-2">
        {TABS.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`text-sm px-3 py-1.5 rounded-full border ${tab === id
              ? "bg-[var(--ring)] text-white border-[var(--ring)]" : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>{label}</button>
        ))}
      </div>
      {tab === "ambiances" && <Ambiances />}
      {tab === "bibliotheque" && <Bibliotheque />}
      {tab === "decouverte" && <Decouverte />}
    </div>
  );
}
```

`frontend/src/app/musique/page.tsx` (remplacer le contenu) :
```tsx
import Musique from "@/components/musique/Musique";

export const metadata = { title: "Musique — Mission Control" };

export default function MusiquePage() {
  return <Musique />;
}
```

`frontend/src/app/musique/loading.tsx` :
```tsx
import { PageSkeleton } from "@/components/PageSkeleton";

export default function Loading() {
  return <PageSkeleton />;
}
```

- [ ] **Step 4: Vérifier compilation + lint**

Run : `npx tsc --noEmit && npx eslint components/musique lib/musique.ts`
Expected: tsc exit 0 ; pas de nouvelle erreur eslint sur ces fichiers.

- [ ] **Step 5: Commit**

```bash
git add components/musique src/app/musique/page.tsx src/app/musique/loading.tsx
git commit -m "feat(musique): page Musique (ambiances + lecteur + export, decouverte)"
```

---

## Task 11: Types OpenAPI + vérification finale

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/openapi.json`, `.env.example`

- [ ] **Step 1: .env.example**

Dans `.env.example`, après le bloc `ICAL_SYNC_URLS`, ajouter :
```
# --- Musique (playlists par ambiance, Ollama local) ---
MUSIC_DIR=C:/Users/germa/Music
MUSIQUE_OLLAMA_HOST=http://localhost:11434
MUSIQUE_OLLAMA_MODEL=qwen2.5-coder:1.5b
```

- [ ] **Step 2: Régénérer les types**

Run (racine) : `make gen-types`
Expected: `frontend/lib/types.ts` inclut les schémas `/musique`.

- [ ] **Step 3: Vérif backend**

Run (depuis `backend/`) : `uv run pytest tests/test_musique tests/test_migrations.py tests/test_health.py tests/test_openapi_contract.py -q`
Expected: PASS.

- [ ] **Step 4: Vérif front**

Run (depuis `frontend/`) : `rm -rf .next && npx tsc --noEmit && npm test`
Expected: tsc exit 0 ; vitest PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/openapi.json .env.example
git commit -m "feat(musique): types OpenAPI + .env.example"
```

---

## Notes de mise en œuvre

- **Sans chat** : Ollama est appelé en tâche de fond (classement, suggestions). Aucune interface de conversation.
- **Pas d'API payante** : tout est local (Ollama, mutagen, fichiers). Le lecteur intégré sert les fichiers via `/media/music` (StaticFiles lecture seule).
- **Chemins .m3u relatifs** : pour rester valides après transfert sur le téléphone (Poweramp).
- **Lecteur = aperçu** : `.dsf` et certains `.flac` ne se lisent pas dans le navigateur (le `<audio>` l'indiquera). Usage principal = export `.m3u`.
- **Modèle Ollama** : `qwen2.5-coder:1.5b` par défaut (déjà installé) ; `MUSIQUE_OLLAMA_MODEL=qwen2.5:3b` (après `ollama pull`) classera mieux.
- **Performance** : ~718 morceaux → le classement Ollama est un job de fond avec progression ; relançable, ne re-classe que `classified=False`.
