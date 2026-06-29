# Musique — Playlists `.m3u8` + export ZIP + suivi qualité Qobuz — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refondre l'onglet Musique : 8 nouvelles playlists (avec slugs), export en un seul ZIP de `.m3u8` (UTF-8 BOM), et un nouvel onglet de suivi qualité/achat Qobuz.

**Architecture :** Backend FastAPI + SQLModel/SQLite (migrations Alembic), classement IA via API Claude (sinon Ollama). Frontend Next.js + TanStack Query. On introduit un couple `slug` (identifiant ASCII stocké en base + URL + nom de fichier) ↔ `label` (affichage). La qualité audio est auto-déduite via mutagen ; un seul champ manuel (`qobuz_available`) alimente un statut d'achat dérivé.

**Tech Stack :** Python 3.13, FastAPI, SQLModel, Alembic, mutagen, pytest ; TypeScript, Next.js, React, TanStack Query, vitest, Tailwind.

## Global Constraints

- Slugs : ASCII, sans `/` ni espace ; stockés dans `track_ambiance.ambiance` et utilisés dans les URLs et noms de fichiers.
- `.m3u8` écrit en **UTF-8 avec BOM** (`﻿`).
- Export = **un seul fichier ZIP** téléchargé (jamais un download par playlist).
- Qualité et origine **auto-déduites** du fichier (mutagen) ; seul `qobuz_available` est manuel (tri-état : `True` / `False` / `None` = à vérifier).
- TDD strict : test qui échoue → implémentation minimale → test vert → commit. Un commit par tâche.
- Commandes lancées depuis `backend/` avec `uv run` (ex. `uv run pytest …`). Frontend depuis `frontend/` avec `npm test` / `npx vitest`.
- Messages de commit terminés par `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Catalogue de référence (slug ↔ label)

| Slug | Label |
|---|---|
| `cafe-petit-dej` | café pour le petit dep |
| `coworking-travail-detente` | coworking/travail/detente |
| `soiree-francophone` | soirée ( francophone ) |
| `soiree-internationale` | soirée ( internationale ) |
| `amour-love-sex` | amour/love/sex |
| `chanson-francaise` | chanson francaise |
| `melancolie` | Mélancolie |
| `sport-gym` | sport/gym |

---

# Chantier A — Playlists slug/label + classement

### Task A1 : Catalogue de playlists (constants.py)

**Files:**
- Modify: `backend/app/services/musique/constants.py`
- Test: `backend/tests/test_musique/test_constants.py` (créer)

**Interfaces:**
- Produces : `AMBIANCE_NAMES: list[str]` (slugs, ordre d'affichage), `AMBIANCE_LABELS: dict[str,str]` (slug→label), `AMBIANCES: dict[str,str]` (slug→description IA), `LABEL_TO_SLUG: dict[str,str]` (label→slug), `AUDIO_EXTENSIONS: set[str]` (inchangé).

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `backend/tests/test_musique/test_constants.py` :

```python
from app.services.musique.constants import (
    AMBIANCE_NAMES, AMBIANCE_LABELS, AMBIANCES, LABEL_TO_SLUG,
)


def test_catalogue_a_huit_playlists():
    assert len(AMBIANCE_NAMES) == 8


def test_slugs_sont_ascii_sans_slash_ni_espace():
    for slug in AMBIANCE_NAMES:
        assert slug.isascii(), slug
        assert "/" not in slug and " " not in slug, slug


def test_bijection_slug_label():
    assert set(AMBIANCE_LABELS) == set(AMBIANCE_NAMES)
    assert set(AMBIANCES) == set(AMBIANCE_NAMES)
    assert set(LABEL_TO_SLUG.values()) == set(AMBIANCE_NAMES)
    assert len(LABEL_TO_SLUG) == 8


def test_quelques_correspondances():
    assert AMBIANCE_LABELS["amour-love-sex"] == "amour/love/sex"
    assert AMBIANCE_LABELS["cafe-petit-dej"] == "café pour le petit dep"
    assert LABEL_TO_SLUG["Mélancolie"] == "melancolie"
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_constants.py -v`
Expected: FAIL (ImportError `LABEL_TO_SLUG` / valeurs absentes).

- [ ] **Step 3 : Réécrire `constants.py`**

```python
"""Playlists musicales : slug (identifiant) ↔ label (affichage) + description IA."""

# Ordre = ordre d'affichage. slug : ASCII, sans '/' ni espace ; stocké en base,
# utilisé dans les URLs et comme base des noms de fichiers d'export.
PLAYLISTS: dict[str, dict[str, str]] = {
    "cafe-petit-dej": {
        "label": "café pour le petit dep",
        "desc": "léger, doux, agréable au réveil / petit-déjeuner",
    },
    "coworking-travail-detente": {
        "label": "coworking/travail/detente",
        "desc": "rythmé mais non distrayant, fond de travail/concentration",
    },
    "soiree-francophone": {
        "label": "soirée ( francophone )",
        "desc": "festif, dansant, chansons francophones",
    },
    "soiree-internationale": {
        "label": "soirée ( internationale )",
        "desc": "festif, dansant, hits internationaux",
    },
    "amour-love-sex": {
        "label": "amour/love/sex",
        "desc": "romantique, sensuel, intime (type date)",
    },
    "chanson-francaise": {
        "label": "chanson francaise",
        "desc": "chanson française : variété et auteurs-compositeurs francophones",
    },
    "melancolie": {
        "label": "Mélancolie",
        "desc": "mélancolique, doux-amer, introspectif",
    },
    "sport-gym": {
        "label": "sport/gym",
        "desc": "entraînant, tempo élevé, motivation sportive",
    },
}

AMBIANCE_NAMES: list[str] = list(PLAYLISTS)
AMBIANCE_LABELS: dict[str, str] = {s: p["label"] for s, p in PLAYLISTS.items()}
AMBIANCES: dict[str, str] = {s: p["desc"] for s, p in PLAYLISTS.items()}
LABEL_TO_SLUG: dict[str, str] = {p["label"]: s for s, p in PLAYLISTS.items()}

AUDIO_EXTENSIONS = {".mp3", ".flac", ".dsf"}
```

- [ ] **Step 4 : Lancer le test (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_constants.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/musique/constants.py backend/tests/test_musique/test_constants.py
git commit -m "feat(musique): nouveau catalogue de 8 playlists slug/label

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A2 : Classement IA en slugs (claude_client + classify)

**Files:**
- Modify: `backend/app/services/musique/claude_client.py`
- Modify: `backend/app/services/musique/classify.py`
- Test: `backend/tests/test_musique/test_claude_client.py` (mettre à jour)
- Test: `backend/tests/test_musique/test_classify.py` (mettre à jour)

**Interfaces:**
- Consumes : `AMBIANCES`, `AMBIANCE_LABELS`, `LABEL_TO_SLUG`, `AMBIANCE_NAMES` (Task A1).
- Produces : `claude_client.classify_batch(...) -> list[list[str]]` renvoie des **slugs** ; `classify.parse_ambiances(raw: str) -> list[str]` renvoie des **slugs** (signature change : plus de 2e argument).

- [ ] **Step 1 : Mettre à jour les tests (échec attendu)**

Dans `backend/tests/test_musique/test_claude_client.py`, remplacer `test_build_batch_prompt_contains_tracks_and_ambiances`, `test_classify_batch_parses_structured_response` et `test_classify_batch_ignores_unknown_ambiances_and_indexes` par :

```python
def test_build_batch_prompt_contains_tracks_and_labels():
    tracks = [
        {"artist": "Joe Hisaishi", "album": "Spirited Away", "title": "One Summer's Day", "genre": "BO"},
        {"artist": "Daft Punk", "album": "Discovery", "title": "One More Time", "genre": "Électro"},
    ]
    p = claude_client.build_batch_prompt(tracks)
    assert "café pour le petit dep" in p and "amour/love/sex" in p   # labels affichés
    assert "One Summer's Day" in p and "Daft Punk" in p
    assert "1." in p and "2." in p


def test_classify_batch_convertit_labels_en_slugs():
    tracks = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café pour le petit dep", "Mélancolie"]},
        {"index": 2, "ambiances": []},
        {"index": 3, "ambiances": ["soirée ( internationale )"]},
    ]}
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeResp(payload)

    res = claude_client.classify_batch(tracks, _create=fake_create)
    assert res == [["cafe-petit-dej", "melancolie"], [], ["soiree-internationale"]]
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert "max_tokens" in captured


def test_classify_batch_ignore_labels_inconnus_et_index_hors_lot():
    tracks = [{"title": "A"}]
    payload = {"resultats": [
        {"index": 1, "ambiances": ["café pour le petit dep", "inconnu", "café pour le petit dep"]},
        {"index": 99, "ambiances": ["amour/love/sex"]},
    ]}
    res = claude_client.classify_batch(tracks, _create=lambda **kw: _FakeResp(payload))
    assert res == [["cafe-petit-dej"]]
    assert all(a in AMBIANCE_NAMES for ambs in res for a in ambs)
```

Dans `backend/tests/test_musique/test_classify.py`, remplacer `test_parse_ambiances_keeps_valid_only`, `test_parse_ambiances_accepte_les_synonymes`, `test_build_prompt_lists_ambiances`, `test_classify_untagged_creates_rows`, `test_classify_ne_reprend_jamais_un_morceau_classe`, `test_classify_untagged_par_lots_marque_aussi_les_zero_ambiance`, `test_reset_classification_targets_empty_only`, `test_reset_classification_tout_efface_auto_garde_manuel` (lignes utilisant les anciens noms) — version mise à jour :

```python
from app.services.musique.classify import build_prompt, classify_untagged, parse_ambiances


def test_parse_ambiances_mappe_labels_et_synonymes_vers_slugs():
    assert parse_ambiances("café, mélancolie") == ["cafe-petit-dej", "melancolie"]
    assert parse_ambiances("Mélancolie.") == ["melancolie"]
    assert parse_ambiances("inconnu") == []
    assert parse_ambiances("aucune") == []


def test_parse_ambiances_synonymes():
    assert parse_ambiances("amour") == ["amour-love-sex"]
    assert parse_ambiances("romantique") == ["amour-love-sex"]
    assert parse_ambiances("sport, gym") == ["sport-gym"]
    assert parse_ambiances("travail") == ["coworking-travail-detente"]


def test_build_prompt_liste_les_labels():
    p = build_prompt({"artist": "A", "album": "B", "title": "T", "genre": "jazz"})
    assert "café pour le petit dep" in p and "amour/love/sex" in p and "T" in p
```

Et adapter les insertions/asserts de slugs dans les tests de `classify_untagged`/`reset_classification` (remplacer chaque `"café"`→`"cafe-petit-dej"`, `"étude"`→`"coworking-travail-detente"`, `"soirée"`→`"soiree-internationale"`, `"repos"`→`"melancolie"`, `"love"`→`"amour-love-sex"`, `"énergie"`→`"sport-gym"`). Les générateurs factices renvoient désormais des slugs côté `classify_lot` et des textes mappables côté `generate` :

```python
def test_classify_untagged_creates_rows(monkeypatch):
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T")); s.commit()
        res = classify_untagged(s, generate=lambda prompt, **kw: "café, mélancolie")
        assert res["classes"] == 1
        ambs = {ta.ambiance for ta in s.exec(select(TrackAmbiance)).all()}
        assert ambs == {"cafe-petit-dej", "melancolie"}
        assert s.exec(select(MusicTrack)).first().classified is True


def test_classify_untagged_par_lots_marque_aussi_les_zero_ambiance():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", title="T1")); s.add(MusicTrack(path="B/2.flac", title="T2")); s.commit()
        res = classify_untagged(s, classify_lot=lambda tracks: [["soiree-internationale"], []])
        assert res == {"classes": 1, "total": 2}
        ambs = [(ta.track_id, ta.ambiance) for ta in s.exec(select(TrackAmbiance)).all()]
        assert ambs == [(1, "soiree-internationale")]
```

(Pour `test_classify_ne_reprend_jamais_un_morceau_classe`, `test_reset_classification_targets_empty_only`, `test_reset_classification_tout_efface_auto_garde_manuel` : remplacer les littéraux d'ambiance par leurs slugs comme ci-dessus, garder la logique inchangée.)

- [ ] **Step 2 : Lancer les tests (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_claude_client.py tests/test_musique/test_classify.py -v`
Expected: FAIL (prompt sans labels, slugs absents).

- [ ] **Step 3 : Implémenter — `claude_client.py`**

Remplacer les imports et fonctions concernées :

```python
from app.services.musique.constants import (
    AMBIANCE_LABELS, AMBIANCES, LABEL_TO_SLUG,
)

# Enum = labels (langage naturel pour le modèle) ; conversion en slug au parsing.
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
```

```python
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
```

Dans `classify_batch`, la boucle de parsing convertit label→slug :

```python
        vues: list[str] = []
        for amb in item.get("ambiances", []):
            slug = LABEL_TO_SLUG.get(amb)
            if slug and slug not in vues:
                vues.append(slug)
        out[i] = vues
```

(Supprimer l'ancien import `AMBIANCE_NAMES` s'il n'est plus utilisé.)

- [ ] **Step 4 : Implémenter — `classify.py`**

Remplacer le bloc `_SYNONYMES` + `parse_ambiances` + `build_prompt` et l'appel dans `_classify_unitaire` :

```python
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCES

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
```

Dans `_classify_unitaire`, remplacer `ambiances = parse_ambiances(raw, AMBIANCE_NAMES)` par `ambiances = parse_ambiances(raw)`. Supprimer l'import `AMBIANCE_NAMES` s'il n'est plus utilisé.

- [ ] **Step 5 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_claude_client.py tests/test_musique/test_classify.py -v`
Expected: PASS.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/musique/claude_client.py backend/app/services/musique/classify.py backend/tests/test_musique/test_claude_client.py backend/tests/test_musique/test_classify.py
git commit -m "feat(musique): classement IA en slugs (labels affichés, slugs stockés)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A3 : Endpoint /ambiances renvoie le label

**Files:**
- Modify: `backend/app/api/musique/bibliotheque.py:69-74`
- Test: `backend/tests/test_musique/test_api.py` (mettre à jour `test_ambiances_and_membership_and_export`, partie ambiances)

**Interfaces:**
- Consumes : `AMBIANCE_NAMES`, `AMBIANCE_LABELS` (Task A1).
- Produces : `GET /musique/ambiances` → `[{ "ambiance": <slug>, "label": <label>, "count": <int> }]` (8 entrées, ordre du catalogue).

- [ ] **Step 1 : Écrire le test (échec attendu)**

Ajouter dans `backend/tests/test_musique/test_api.py` :

```python
def test_ambiances_renvoie_slug_label_count():
    engine = _engine()
    client = _client(engine)
    rows = client.get("/musique/ambiances").json()
    assert len(rows) == 8
    first = rows[0]
    assert set(first) == {"ambiance", "label", "count"}
    by_slug = {r["ambiance"]: r for r in rows}
    assert by_slug["amour-love-sex"]["label"] == "amour/love/sex"
    assert by_slug["amour-love-sex"]["count"] == 0
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_api.py::test_ambiances_renvoie_slug_label_count -v`
Expected: FAIL (clé `label` absente).

- [ ] **Step 3 : Implémenter**

Dans `backend/app/api/musique/bibliotheque.py`, modifier l'import et la fonction `ambiances` :

```python
from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCE_NAMES
```

```python
@router.get("/ambiances")
def ambiances(session: Session = Depends(get_session)):
    counts: dict[str, int] = {a: 0 for a in AMBIANCE_NAMES}
    for r in session.exec(select(TrackAmbiance)).all():
        if r.ambiance in counts:
            counts[r.ambiance] += 1
    return [{"ambiance": a, "label": AMBIANCE_LABELS[a], "count": counts[a]} for a in AMBIANCE_NAMES]
```

- [ ] **Step 4 : Lancer le test (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_api.py::test_ambiances_renvoie_slug_label_count -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/api/musique/bibliotheque.py backend/tests/test_musique/test_api.py
git commit -m "feat(musique): /ambiances expose le label d'affichage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task A4 : Purge des appartenances aux noms inconnus (au démarrage)

**Files:**
- Modify: `backend/app/services/musique/playlists.py`
- Modify: `backend/app/main.py:30-48` (bloc seed dans `lifespan`)
- Test: `backend/tests/test_musique/test_playlists.py`

**Interfaces:**
- Consumes : `AMBIANCE_NAMES` (Task A1).
- Produces : `playlists.purge_unknown_ambiances(session) -> int` — supprime les lignes `TrackAmbiance` dont le slug n'est pas connu et remet les morceaux orphelinés `classified=False` ; retourne le nombre de lignes supprimées.

- [ ] **Step 1 : Écrire le test (échec attendu)**

Ajouter dans `backend/tests/test_musique/test_playlists.py` :

```python
def test_purge_unknown_ambiances():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack, TrackAmbiance
    from app.services.musique.playlists import purge_unknown_ambiances

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", classified=True))   # id1 : ancien nom -> purgé
        s.add(MusicTrack(path="B/2.flac", classified=True))   # id2 : slug valide -> conservé
        s.commit()
        s.add(TrackAmbiance(track_id=1, ambiance="café", source="auto"))      # ancien nom
        s.add(TrackAmbiance(track_id=2, ambiance="sport-gym", source="auto"))  # slug valide
        s.commit()

        n = purge_unknown_ambiances(s)
        assert n == 1
        restantes = {ta.ambiance for ta in s.exec(select(TrackAmbiance)).all()}
        assert restantes == {"sport-gym"}
        t1 = s.exec(select(MusicTrack).where(MusicTrack.path == "A/1.flac")).first()
        t2 = s.exec(select(MusicTrack).where(MusicTrack.path == "B/2.flac")).first()
        assert t1.classified is False   # orphelin -> à reclasser
        assert t2.classified is True


def test_purge_unknown_ambiances_idempotent():
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool
    from app.services.musique.playlists import purge_unknown_ambiances

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        assert purge_unknown_ambiances(s) == 0
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_playlists.py -k purge -v`
Expected: FAIL (ImportError `purge_unknown_ambiances`).

- [ ] **Step 3 : Implémenter dans `playlists.py`**

Ajouter en tête l'import `AMBIANCE_NAMES` (déjà importé `AMBIANCE_NAMES` via constants) et la fonction :

```python
def purge_unknown_ambiances(session: Session) -> int:
    """Supprime les appartenances aux playlists inconnues (anciens noms) et remet
    les morceaux orphelinés à reclasser. Idempotent. Retourne le nb de lignes purgées."""
    valides = set(AMBIANCE_NAMES)
    a_purger = [r for r in session.exec(select(TrackAmbiance)).all() if r.ambiance not in valides]
    if not a_purger:
        return 0
    track_ids = {r.track_id for r in a_purger}
    for r in a_purger:
        session.delete(r)
    encore_taggés = {
        r.track_id for r in session.exec(select(TrackAmbiance)).all()
        if r.ambiance in valides
    }
    for tid in track_ids - encore_taggés:
        track = session.get(MusicTrack, tid)
        if track is not None:
            track.classified = False
            session.add(track)
    session.commit()
    return len(a_purger)
```

(Vérifier que `from app.services.musique.constants import AMBIANCE_NAMES` figure dans les imports — l'ajouter à l'import existant `from app.services.musique.constants import AMBIANCE_NAMES`.)

- [ ] **Step 4 : Câbler dans `main.py`**

Dans `lifespan`, à l'intérieur du `with Session(engine) as session:` (après le seed skincare), ajouter :

```python
        # Purge des playlists musicales aux noms obsolètes (#musique)
        try:
            from app.services.musique.playlists import purge_unknown_ambiances
            n = purge_unknown_ambiances(session)
            if n:
                log.info("Musique : %d appartenances obsolètes purgées", n)
        except Exception as exc:
            log.warning("Purge playlists musique: %s", exc)
```

- [ ] **Step 5 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_playlists.py -k purge -v`
Expected: PASS (2 tests).

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/musique/playlists.py backend/app/main.py backend/tests/test_musique/test_playlists.py
git commit -m "feat(musique): purge des appartenances obsolètes au démarrage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

# Chantier B — Export ZIP `.m3u8`

### Task B1 : Génération `.m3u8` (UTF-8 BOM) + nom de fichier assaini

**Files:**
- Modify: `backend/app/services/musique/playlists.py`
- Test: `backend/tests/test_musique/test_playlists.py`

**Interfaces:**
- Produces :
  - `playlists.to_m3u8(tracks: list[dict], *, titre: str) -> bytes` — contenu `.m3u8` encodé UTF-8 **avec BOM**, en-têtes `#EXTM3U` + `#PLAYLIST:<titre>`.
  - `playlists.safe_filename(label: str) -> str` — label assaini pour le système de fichiers (sans caractères interdits Windows ni `/`).

- [ ] **Step 1 : Écrire les tests (échec attendu)**

Remplacer `test_to_m3u_relative_paths` dans `backend/tests/test_musique/test_playlists.py` par :

```python
def test_to_m3u8_bom_entete_et_lignes():
    from app.services.musique.playlists import to_m3u8
    tracks = [
        {"path": "A/Alb/01.flac", "artist": "A", "title": "T1", "duree_sec": 200},
        {"path": "B/Alb/02.mp3", "artist": "B", "title": "T2", "duree_sec": None},
    ]
    data = to_m3u8(tracks, titre="café pour le petit dep")
    assert isinstance(data, bytes)
    assert data.startswith("﻿".encode("utf-8"))    # BOM UTF-8
    texte = data.decode("utf-8-sig")
    lines = texte.splitlines()
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#PLAYLIST:café pour le petit dep"
    assert "#EXTINF:200,A - T1" in lines
    assert "A/Alb/01.flac" in lines
    assert "#EXTINF:-1,B - T2" in lines


def test_to_m3u8_playlist_vide():
    from app.services.musique.playlists import to_m3u8
    data = to_m3u8([], titre="Mélancolie")
    texte = data.decode("utf-8-sig")
    assert texte.splitlines() == ["#EXTM3U", "#PLAYLIST:Mélancolie"]


def test_safe_filename_retire_les_caracteres_interdits():
    from app.services.musique.playlists import safe_filename
    assert safe_filename("amour/love/sex") == "amour - love - sex"
    assert safe_filename("soirée ( internationale )") == "soirée ( internationale )"
    assert safe_filename('a:b*c?"d') == "abcd"
```

- [ ] **Step 2 : Lancer les tests (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_playlists.py -k "m3u8 or safe_filename" -v`
Expected: FAIL (ImportError `to_m3u8`/`safe_filename`).

- [ ] **Step 3 : Implémenter dans `playlists.py`**

**Ne pas supprimer `to_m3u` ici** (l'API l'importe encore ; il sera retiré en Task B2 quand l'import API sera mis à jour). Ajouter, à côté de `to_m3u`, les deux nouvelles fonctions :

```python
def to_m3u8(tracks: list[dict], *, titre: str) -> bytes:
    """Construit un .m3u8 (UTF-8 avec BOM) lisible par Poweramp. Chemins relatifs."""
    lines = ["#EXTM3U", f"#PLAYLIST:{titre}"]
    for t in tracks:
        dur = t.get("duree_sec") or -1
        artist = t.get("artist", "")
        title = t.get("title", "")
        lines.append(f"#EXTINF:{dur},{artist} - {title}")
        lines.append(t["path"])
    texte = "\n".join(lines) + "\n"
    return ("﻿" + texte).encode("utf-8")


# Caractères interdits dans un nom de fichier Windows (hors '/').
_FORBIDDEN = '<>:"\\|?*'


def safe_filename(label: str) -> str:
    """Label -> nom de fichier sûr : '/' devient ' - ', caractères interdits retirés."""
    name = label.replace("/", " - ")
    return "".join(c for c in name if c not in _FORBIDDEN).strip()
```

(Note : `reco_bibliotheque`, `set_membership`, `playlist_tracks`, `purge_unknown_ambiances` restent inchangés. `to_m3u` est conservé jusqu'à Task B2.)

- [ ] **Step 4 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_playlists.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/musique/playlists.py backend/tests/test_musique/test_playlists.py
git commit -m "feat(musique): export .m3u8 UTF-8 BOM + nom de fichier assaini

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B2 : Endpoint export ZIP unique (et suppression de l'export par playlist)

**Files:**
- Modify: `backend/app/api/musique/playlists.py`
- Test: `backend/tests/test_musique/test_api.py` (mettre à jour `test_ambiances_and_membership_and_export`)

**Interfaces:**
- Consumes : `playlists.playlist_tracks`, `to_m3u8`, `safe_filename` (Task B1) ; `AMBIANCE_NAMES`, `AMBIANCE_LABELS` (Task A1).
- Produces : `GET /musique/playlists/export.zip` → réponse `application/zip` (`Content-Disposition: attachment; filename="playlists-musique.zip"`) contenant un `.m3u8` par playlist. **Supprime** `GET /musique/playlists/{ambiance}/export.m3u`.

- [ ] **Step 1 : Mettre à jour le test (échec attendu)**

Dans `backend/tests/test_musique/test_api.py`, **remplacer** `test_ambiances_and_membership_and_export` par une version sans `export.m3u` (slugs), et ajouter un test ZIP :

```python
def test_membership_and_playlist_avec_slug():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
    client = _client(engine)

    assert client.get("/musique/ambiances").status_code == 200
    assert client.put("/musique/tracks/1/ambiances/amour-love-sex").status_code == 204
    pl = client.get("/musique/playlists/amour-love-sex")
    assert pl.status_code == 200 and len(pl.json()) == 1
    assert client.delete("/musique/tracks/1/ambiances/amour-love-sex").status_code == 204
    assert client.get("/musique/playlists/amour-love-sex").json() == []


def test_export_zip_un_seul_fichier_par_playlist():
    import io, zipfile
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        from app.models.musique import TrackAmbiance
        s.add(MusicTrack(path="A/B/1.flac", artist="A", title="T", duree_sec=100)); s.commit()
        s.add(TrackAmbiance(track_id=1, ambiance="amour-love-sex", source="manuel")); s.commit()
    client = _client(engine)

    r = client.get("/musique/playlists/export.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "playlists-musique.zip" in r.headers["content-disposition"]
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert len(names) == 8                                  # une entrée par playlist
    assert all(n.endswith(".m3u8") and "/" not in n for n in names)
    assert "amour - love - sex.m3u8" in names
    contenu = zf.read("amour - love - sex.m3u8").decode("utf-8-sig")
    assert contenu.startswith("#EXTM3U")
    assert "A/B/1.flac" in contenu
```

- [ ] **Step 2 : Lancer les tests (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_api.py -k "export_zip or slug" -v`
Expected: FAIL (route `export.zip` absente).

- [ ] **Step 3 : Implémenter dans `backend/app/api/musique/playlists.py`**

Remplacer l'import de `to_m3u` et l'endpoint `export_m3u` :

```python
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse  # (retirer si plus utilisé)

from app.services.musique.constants import AMBIANCE_LABELS, AMBIANCE_NAMES
from app.services.musique.playlists import (
    playlist_tracks, reco_bibliotheque, safe_filename, set_membership, to_m3u8,
)
```

**Placement important :** déclarer `export_zip` **avant** la route `/playlists/{ambiance}` (sinon FastAPI interprète `export.zip` comme une valeur d'`ambiance`). Placer la fonction juste après `router = APIRouter()`, avant `add_membership`/`playlist`.

```python
@router.get("/playlists/export.zip")
def export_zip(session: Session = Depends(get_session)):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for slug in AMBIANCE_NAMES:
            label = AMBIANCE_LABELS[slug]
            tracks = [t.model_dump() for t in playlist_tracks(session, slug)]
            zf.writestr(f"{safe_filename(label)}.m3u8", to_m3u8(tracks, titre=label))
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="playlists-musique.zip"'},
    )
```

Supprimer l'ancien `export_m3u`. Si `PlainTextResponse` n'est plus utilisé ailleurs dans le fichier, retirer son import. **Supprimer aussi `to_m3u` de `backend/app/services/musique/playlists.py`** (conservé jusqu'ici en Task B1) — plus aucun import ne le référence désormais.

- [ ] **Step 4 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_api.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/api/musique/playlists.py backend/tests/test_musique/test_api.py
git commit -m "feat(musique): export ZIP unique de toutes les playlists (.m3u8)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task B3 : Frontend — onglets par slug + bouton « Tout exporter (.zip) »

**Files:**
- Modify: `frontend/lib/musique.ts`
- Modify: `frontend/components/musique/Ambiances.tsx`

**Interfaces:**
- Consumes : `GET /musique/ambiances` renvoie `{ ambiance, label, count }` (Task A3) ; `GET /musique/playlists/export.zip` (Task B2).
- Produces : `musiqueApi.exportAllUrl(): string` ; type `AmbianceCount` avec `label`.

- [ ] **Step 1 : Modifier `frontend/lib/musique.ts`**

Étendre le type et remplacer `exportUrl` :

```typescript
export interface AmbianceCount { ambiance: string; label: string; count: number; }
```

Dans `musiqueApi`, remplacer la ligne `exportUrl` par :

```typescript
  exportAllUrl: () => `${env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "")}/musique/playlists/export.zip`,
```

- [ ] **Step 2 : Modifier `frontend/components/musique/Ambiances.tsx`**

- Initialiser `sel` sur la première ambiance chargée plutôt que `"café"` codé en dur :

```tsx
  const ambiances: AmbianceCount[] = useAmbiances().data ?? [];
  const [sel, setSel] = useState<string>("");
  const active = sel || ambiances[0]?.ambiance || "";
```

Puis utiliser `active` partout où `sel` servait à charger les données :

```tsx
  const tracks: Track[] = usePlaylist(active).data ?? [];
  const reco: Track[] = usePlaylistReco(active).data ?? [];
  const add = (id: number) => addMutation.mutate({ id, ambiance: active });
```

- Afficher le label, garder le slug comme clé/valeur de sélection, et comparer à `active` :

```tsx
        {ambiances.map((a) => (
          <button key={a.ambiance} onClick={() => setSel(a.ambiance)}
            className={`text-xs px-2.5 py-1 rounded-full border ${active === a.ambiance
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>
            {a.label} ({a.count})
          </button>
        ))}
        <a href={musiqueApi.exportAllUrl()} download
           className="ml-auto text-xs px-2.5 py-1 rounded-full border border-[var(--border)]">⬇ Tout exporter (.zip)</a>
```

- [ ] **Step 3 : Vérifier le build/typecheck et les tests front**

Run: `cd frontend && npx tsc --noEmit && npx vitest run __tests__/queries/musique.test.tsx`
Expected: PASS (typecheck OK ; le test queries existant reste vert).

- [ ] **Step 4 : Vérification manuelle**

Lancer l'app (skill `/run` ou `npm run dev` côté frontend + backend), aller dans Musique → onglet Ambiances : les onglets affichent les labels (`café pour le petit dep`, `amour/love/sex`…) ; cliquer « ⬇ Tout exporter (.zip) » télécharge **un seul** `playlists-musique.zip` contenant 8 `.m3u8`.

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/musique.ts frontend/components/musique/Ambiances.tsx
git commit -m "feat(musique): onglets par slug/label + bouton export ZIP unique

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

# Chantier C — Suivi qualité / achat Qobuz

### Task C1 : Colonnes qualité sur MusicTrack + migration Alembic

**Files:**
- Modify: `backend/app/models/musique.py`
- Create: `backend/alembic/versions/20260629_1200_m601_music_quality.py`
- Test: `backend/tests/test_musique/test_model_quality.py` (créer)

**Interfaces:**
- Produces : `MusicTrack` avec `bitrate_kbps: int | None`, `sample_rate_hz: int | None`, `bits_per_sample: int | None`, `qobuz_available: bool | None`.

- [ ] **Step 1 : Écrire le test (échec attendu)**

Créer `backend/tests/test_musique/test_model_quality.py` :

```python
def test_music_track_a_les_colonnes_qualite():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/1.flac", bitrate_kbps=940, sample_rate_hz=44100,
                         bits_per_sample=16, qobuz_available=True))
        s.commit()
        t = s.exec(select(MusicTrack)).first()
        assert t.bitrate_kbps == 940 and t.sample_rate_hz == 44100
        assert t.bits_per_sample == 16 and t.qobuz_available is True


def test_colonnes_qualite_par_defaut_none():
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool
    from app.models.musique import MusicTrack

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(MusicTrack(path="A/2.mp3")); s.commit()
        t = s.exec(select(MusicTrack)).first()
        assert t.bitrate_kbps is None and t.qobuz_available is None
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_model_quality.py -v`
Expected: FAIL (`TypeError`/colonnes inconnues).

- [ ] **Step 3 : Ajouter les colonnes au modèle**

Dans `backend/app/models/musique.py`, classe `MusicTrack`, après `classified` :

```python
    bitrate_kbps: int | None = None       # auto (scan mutagen)
    sample_rate_hz: int | None = None     # auto
    bits_per_sample: int | None = None    # auto (None pour MP3)
    qobuz_available: bool | None = None   # manuel (None = à vérifier)
```

- [ ] **Step 4 : Créer la migration Alembic**

Créer `backend/alembic/versions/20260629_1200_m601_music_quality.py` :

```python
"""music_track : colonnes qualité audio + dispo Qobuz (#musique)

Revision ID: m601musicquality
Revises: q257patrimoinesnap
Create Date: 2026-06-29 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "m601musicquality"
down_revision = "q257patrimoinesnap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("music_track") as batch_op:
        batch_op.add_column(sa.Column("bitrate_kbps", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sample_rate_hz", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bits_per_sample", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("qobuz_available", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("music_track") as batch_op:
        batch_op.drop_column("qobuz_available")
        batch_op.drop_column("bits_per_sample")
        batch_op.drop_column("sample_rate_hz")
        batch_op.drop_column("bitrate_kbps")
```

- [ ] **Step 5 : Lancer le test + vérifier la migration**

Run: `cd backend && uv run pytest tests/test_musique/test_model_quality.py -v && uv run alembic upgrade head && uv run alembic heads`
Expected: tests PASS ; `alembic heads` affiche `m601musicquality (head)`.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/models/musique.py backend/alembic/versions/20260629_1200_m601_music_quality.py backend/tests/test_musique/test_model_quality.py
git commit -m "feat(musique): colonnes qualité audio + dispo Qobuz (modèle + migration)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task C2 : Scan extrait bitrate / sample rate / bits

**Files:**
- Modify: `backend/app/services/musique/scan.py:31-58`
- Test: `backend/tests/test_musique/test_scan.py`

**Interfaces:**
- Consumes : `MusicTrack` colonnes qualité (Task C1).
- Produces : `scan.extract_metadata(path)` retourne en plus `bitrate_kbps`, `sample_rate_hz`, `bits_per_sample` (clés toujours présentes, valeurs `None` si indispo).

- [ ] **Step 1 : Écrire le test (échec attendu)**

Ajouter dans `backend/tests/test_musique/test_scan.py` :

```python
def test_extract_metadata_lit_qualite(monkeypatch):
    class FakeInfo:
        length = 200
        bitrate = 940000
        sample_rate = 44100
        bits_per_sample = 16

    class FakeAudio(dict):
        info = FakeInfo()

    import app.services.musique.scan as scanmod
    monkeypatch.setattr("mutagen.File", lambda p, easy=True: FakeAudio())
    meta = scanmod.extract_metadata(Path("Artiste/Album/01.flac"))
    assert meta["bitrate_kbps"] == 940
    assert meta["sample_rate_hz"] == 44100
    assert meta["bits_per_sample"] == 16


def test_extract_metadata_qualite_absente_donne_none(monkeypatch):
    import app.services.musique.scan as scanmod
    monkeypatch.setattr("mutagen.File", lambda p, easy=True: None)
    meta = scanmod.extract_metadata(Path("Artiste/Album/01.mp3"))
    assert meta["bitrate_kbps"] is None
    assert meta["sample_rate_hz"] is None
    assert meta["bits_per_sample"] is None
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_scan.py -k qualite -v`
Expected: FAIL (clés absentes).

- [ ] **Step 3 : Implémenter dans `scan.py`**

Dans `extract_metadata`, ajouter l'extraction et compléter le dict de retour :

```python
    artist = album = title = genre = ""
    duree_sec: int | None = None
    bitrate_kbps = sample_rate_hz = bits_per_sample = None
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
            info = getattr(audio, "info", None)
            if info is not None:
                if getattr(info, "length", None):
                    duree_sec = int(info.length)
                if getattr(info, "bitrate", None):
                    bitrate_kbps = int(info.bitrate) // 1000
                if getattr(info, "sample_rate", None):
                    sample_rate_hz = int(info.sample_rate)
                if getattr(info, "bits_per_sample", None):
                    bits_per_sample = int(info.bits_per_sample)
    except Exception:
        pass
```

Et le `return` :

```python
    return {"artist": artist, "album": album, "title": title, "genre": genre,
            "duree_sec": duree_sec, "bitrate_kbps": bitrate_kbps,
            "sample_rate_hz": sample_rate_hz, "bits_per_sample": bits_per_sample}
```

(`scan_library` fait déjà `MusicTrack(path=rel, cover=cover_rel, **meta)` et `setattr` en boucle : les nouvelles clés sont prises en charge automatiquement.)

- [ ] **Step 4 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_scan.py -v`
Expected: PASS (les tests existants — dont `test_scan_library_indexes_audio` qui stubbe `extract_metadata` sans ces clés — restent verts, les colonnes valant `None`).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/musique/scan.py backend/tests/test_musique/test_scan.py
git commit -m "feat(musique): le scan extrait bitrate/sample rate/bits

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task C3 : Fonctions pures qualité & statut d'achat

**Files:**
- Create: `backend/app/services/musique/quality.py`
- Test: `backend/tests/test_musique/test_quality.py` (créer)

**Interfaces:**
- Produces :
  - `quality.quality_tier(suffix: str, bits_per_sample: int | None, sample_rate_hz: int | None) -> str` → `"lossy" | "cd" | "hires" | "dsd"`.
  - `quality.quality_label(suffix: str, bitrate_kbps, sample_rate_hz, bits_per_sample) -> str`.
  - `quality.purchase_status(tier: str, qobuz_available: bool | None) -> str` → `"owned" | "to_buy" | "unavailable" | "unknown"`.

- [ ] **Step 1 : Écrire les tests (échec attendu)**

Créer `backend/tests/test_musique/test_quality.py` :

```python
from app.services.musique.quality import purchase_status, quality_label, quality_tier


def test_quality_tier():
    assert quality_tier(".mp3", None, None) == "lossy"
    assert quality_tier(".flac", 16, 44100) == "cd"
    assert quality_tier(".flac", 24, 96000) == "hires"
    assert quality_tier(".flac", 16, 96000) == "hires"     # >48kHz -> hires
    assert quality_tier(".dsf", 1, 2822400) == "dsd"


def test_quality_label():
    assert quality_label(".mp3", 320, 44100, None) == "MP3 (320 kbps)"
    assert quality_label(".flac", 940, 44100, 16) == "FLAC CD (16 bit · 44,1 kHz)"
    assert quality_label(".flac", 2300, 96000, 24) == "Hi-Res (24 bit · 96 kHz)"
    assert quality_label(".dsf", None, 2822400, 1) == "DSD"
    assert quality_label(".mp3", None, None, None) == "MP3"   # bitrate inconnu


def test_purchase_status():
    assert purchase_status("cd", None) == "owned"
    assert purchase_status("hires", False) == "owned"
    assert purchase_status("lossy", True) == "to_buy"
    assert purchase_status("lossy", False) == "unavailable"
    assert purchase_status("lossy", None) == "unknown"
```

- [ ] **Step 2 : Lancer les tests (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_quality.py -v`
Expected: FAIL (module absent).

- [ ] **Step 3 : Implémenter `backend/app/services/musique/quality.py`**

```python
"""Qualité audio (déduite du fichier) et statut d'achat Qobuz (fonctions pures)."""
from __future__ import annotations


def quality_tier(suffix: str, bits_per_sample: int | None, sample_rate_hz: int | None) -> str:
    """lossy (MP3) | cd (FLAC 16/≤48kHz) | hires (FLAC ≥24 bit ou >48kHz) | dsd."""
    ext = suffix.lower()
    if ext == ".dsf":
        return "dsd"
    if ext == ".mp3":
        return "lossy"
    # FLAC et autres lossless
    if (bits_per_sample or 0) >= 24 or (sample_rate_hz or 0) > 48000:
        return "hires"
    return "cd"


def _khz(sample_rate_hz: int | None) -> str:
    if not sample_rate_hz:
        return ""
    val = sample_rate_hz / 1000
    txt = (f"{val:.1f}".rstrip("0").rstrip(".")).replace(".", ",")
    return f"{txt} kHz"


def quality_label(suffix: str, bitrate_kbps: int | None,
                  sample_rate_hz: int | None, bits_per_sample: int | None) -> str:
    tier = quality_tier(suffix, bits_per_sample, sample_rate_hz)
    if tier == "dsd":
        return "DSD"
    if tier == "lossy":
        return f"MP3 ({bitrate_kbps} kbps)" if bitrate_kbps else "MP3"
    details = " · ".join(p for p in (
        f"{bits_per_sample} bit" if bits_per_sample else "",
        _khz(sample_rate_hz),
    ) if p)
    base = "FLAC CD" if tier == "cd" else "Hi-Res"
    return f"{base} ({details})" if details else base


def purchase_status(tier: str, qobuz_available: bool | None) -> str:
    """owned (déjà en qualité) | to_buy | unavailable | unknown."""
    if tier != "lossy":
        return "owned"
    if qobuz_available is True:
        return "to_buy"
    if qobuz_available is False:
        return "unavailable"
    return "unknown"
```

- [ ] **Step 4 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_quality.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/musique/quality.py backend/tests/test_musique/test_quality.py
git commit -m "feat(musique): fonctions pures qualité audio + statut d'achat Qobuz

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task C4 : API qualité (liste + maj dispo Qobuz)

**Files:**
- Modify: `backend/app/api/musique/bibliotheque.py`
- Test: `backend/tests/test_musique/test_api.py`

**Interfaces:**
- Consumes : `quality.quality_label`, `quality.quality_tier`, `quality.purchase_status` (Task C3) ; `MusicTrack` colonnes qualité (Task C1).
- Produces :
  - `GET /musique/quality` → `list[{ id, title, artist, format, quality_label, tier, qobuz_available, status }]`.
  - `PUT /musique/tracks/{track_id}/qobuz-available` (corps JSON `{ "available": true|false|null }`) → 204 ; 404 si morceau inconnu.

- [ ] **Step 1 : Écrire les tests (échec attendu)**

Ajouter dans `backend/tests/test_musique/test_api.py` :

```python
def test_quality_liste_et_statut():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/1.mp3", artist="A", title="MP3", bitrate_kbps=320))
        s.add(MusicTrack(path="B/2.flac", artist="B", title="FLAC",
                         bitrate_kbps=940, sample_rate_hz=44100, bits_per_sample=16))
        s.commit()
    client = _client(engine)

    rows = client.get("/musique/quality").json()
    by_title = {r["title"]: r for r in rows}
    assert by_title["MP3"]["format"] == "mp3"
    assert by_title["MP3"]["status"] == "unknown"          # mp3, dispo inconnue
    assert by_title["MP3"]["quality_label"] == "MP3 (320 kbps)"
    assert by_title["FLAC"]["tier"] == "cd"
    assert by_title["FLAC"]["status"] == "owned"


def test_put_qobuz_available_met_a_jour_le_statut():
    engine = _engine()
    with Session(engine) as s:
        from app.models.musique import MusicTrack
        s.add(MusicTrack(path="A/1.mp3", artist="A", title="MP3", bitrate_kbps=320)); s.commit()
    client = _client(engine)

    assert client.put("/musique/tracks/1/qobuz-available", json={"available": True}).status_code == 204
    rows = client.get("/musique/quality").json()
    assert rows[0]["qobuz_available"] is True and rows[0]["status"] == "to_buy"

    assert client.put("/musique/tracks/1/qobuz-available", json={"available": None}).status_code == 204
    assert client.get("/musique/quality").json()[0]["status"] == "unknown"

    assert client.put("/musique/tracks/999/qobuz-available", json={"available": True}).status_code == 404
```

- [ ] **Step 2 : Lancer les tests (échec attendu)**

Run: `cd backend && uv run pytest tests/test_musique/test_api.py -k "quality or qobuz" -v`
Expected: FAIL (routes absentes).

- [ ] **Step 3 : Implémenter dans `bibliotheque.py`**

Ajouter imports et endpoints :

```python
from pathlib import PurePosixPath

from pydantic import BaseModel

from app.services.musique.quality import purchase_status, quality_label, quality_tier


class QobuzAvailableIn(BaseModel):
    available: bool | None


@router.get("/quality")
def quality(session: Session = Depends(get_session)):
    rows = []
    for t in session.exec(select(MusicTrack)).all():
        suffix = PurePosixPath(t.path).suffix
        tier = quality_tier(suffix, t.bits_per_sample, t.sample_rate_hz)
        rows.append({
            "id": t.id, "title": t.title, "artist": t.artist,
            "format": suffix.lstrip(".").lower(),
            "quality_label": quality_label(suffix, t.bitrate_kbps, t.sample_rate_hz, t.bits_per_sample),
            "tier": tier,
            "qobuz_available": t.qobuz_available,
            "status": purchase_status(tier, t.qobuz_available),
        })
    return rows


@router.put("/tracks/{track_id}/qobuz-available", status_code=204)
def set_qobuz_available(track_id: int, body: QobuzAvailableIn,
                        session: Session = Depends(get_session)):
    track = session.get(MusicTrack, track_id)
    if track is None:
        raise HTTPException(404, "Morceau inconnu")
    track.qobuz_available = body.available
    session.add(track)
    session.commit()
```

- [ ] **Step 4 : Lancer les tests (vert attendu)**

Run: `cd backend && uv run pytest tests/test_musique/ -v`
Expected: PASS (toute la suite musique).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/api/musique/bibliotheque.py backend/tests/test_musique/test_api.py
git commit -m "feat(musique): API suivi qualité + maj dispo Qobuz

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task C5 : Frontend — onglet « Qualité / Achat »

**Files:**
- Modify: `frontend/lib/musique.ts`
- Modify: `frontend/lib/queries/musique.ts`
- Create: `frontend/components/musique/Qualite.tsx`
- Modify: `frontend/components/musique/Musique.tsx`

**Interfaces:**
- Consumes : `GET /musique/quality`, `PUT /musique/tracks/{id}/qobuz-available` (Task C4).
- Produces : `musiqueApi.quality()`, `musiqueApi.setQobuzAvailable(id, value)` ; hooks `useQuality()`, `useSetQobuzAvailable()` ; composant `Qualite` ; onglet `qualite`.

- [ ] **Step 1 : Étendre `frontend/lib/musique.ts`**

Ajouter le type et les deux méthodes API :

```typescript
export interface QualityRow {
  id: number; title: string; artist: string; format: string;
  quality_label: string; tier: string;
  qobuz_available: boolean | null;
  status: "owned" | "to_buy" | "unavailable" | "unknown";
}
```

Dans `musiqueApi`, ajouter :

```typescript
  quality: () => api<QualityRow[]>("/musique/quality"),
  setQobuzAvailable: (id: number, available: boolean | null) =>
    api<void>(`/musique/tracks/${id}/qobuz-available`, {
      method: "PUT", body: JSON.stringify({ available }),
    }),
```

- [ ] **Step 2 : Étendre `frontend/lib/queries/musique.ts`**

Ajouter une clé, un hook de lecture et une mutation :

```typescript
// dans musiqueKeys :
  quality: () => [...musiqueKeys.all, "quality"] as const,
```

```typescript
export function useQuality() {
  return useQuery({ queryKey: musiqueKeys.quality(), queryFn: musiqueApi.quality });
}

export function useSetQobuzAvailable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { id: number; available: boolean | null }) =>
      musiqueApi.setQobuzAvailable(p.id, p.available),
    onSuccess: () => qc.invalidateQueries({ queryKey: musiqueKeys.quality() }),
  });
}
```

(Importer `musiqueApi` est déjà fait en tête du fichier.)

- [ ] **Step 3 : Créer `frontend/components/musique/Qualite.tsx`**

```tsx
"use client";

import { useMemo, useState } from "react";
import type { QualityRow } from "@/lib/musique";
import { useQuality, useSetQobuzAvailable } from "@/lib/queries/musique";

const STATUS_LABEL: Record<QualityRow["status"], string> = {
  owned: "✅ Déjà en qualité",
  to_buy: "🛒 À acheter",
  unavailable: "⛔ Indispo Qobuz",
  unknown: "❔ À vérifier",
};

const FILTERS: [string, string][] = [
  ["all", "Tous"], ["to_buy", "À acheter"], ["unknown", "À vérifier"], ["owned", "Déjà en qualité"],
];

export function Qualite() {
  const rows: QualityRow[] = useQuality().data ?? [];
  const setQobuz = useSetQobuzAvailable();
  const [filter, setFilter] = useState<string>("all");

  const counts = useMemo(() => {
    const c = { to_buy: 0, unknown: 0, owned: 0, unavailable: 0 };
    rows.forEach((r) => { c[r.status] += 1; });
    return c;
  }, [rows]);

  const shown = filter === "all" ? rows : rows.filter((r) => r.status === filter);

  const setValue = (id: number, v: string) =>
    setQobuz.mutate({ id, available: v === "oui" ? true : v === "non" ? false : null });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-sm">
        <span>🛒 À acheter : <b>{counts.to_buy}</b></span>
        <span>❔ À vérifier : <b>{counts.unknown}</b></span>
        <span>✅ En qualité : <b>{counts.owned}</b></span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map(([id, label]) => (
          <button key={id} onClick={() => setFilter(id)}
            className={`text-xs px-2.5 py-1 rounded-full border ${filter === id
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>{label}</button>
        ))}
      </div>

      <div className="space-y-1">
        {shown.map((r) => (
          <div key={r.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate">{r.title} — <span className="text-[var(--muted-foreground)]">{r.artist}</span></div>
              <div className="text-xs text-[var(--muted-foreground)]">{r.quality_label} · {STATUS_LABEL[r.status]}</div>
            </div>
            <select
              value={r.qobuz_available === true ? "oui" : r.qobuz_available === false ? "non" : "?"}
              onChange={(e) => setValue(r.id, e.target.value)}
              className="text-xs rounded border border-[var(--border)] bg-transparent px-1.5 py-1">
              <option value="?">Qobuz ?</option>
              <option value="oui">Achetable</option>
              <option value="non">Indispo</option>
            </select>
          </div>
        ))}
        {shown.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Aucun morceau — lance un scan.</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4 : Brancher l'onglet dans `Musique.tsx`**

```tsx
import { Qualite } from "./Qualite";

const TABS = [["ambiances", "Ambiances"], ["bibliotheque", "Bibliothèque"], ["qualite", "Qualité"], ["decouverte", "Découverte"]] as const;
```

Et dans le rendu, ajouter :

```tsx
      {tab === "qualite" && <Qualite />}
```

- [ ] **Step 5 : Typecheck + tests front**

Run: `cd frontend && npx tsc --noEmit && npx vitest run __tests__/queries/musique.test.tsx`
Expected: PASS.

- [ ] **Step 6 : Vérification manuelle**

App lancée : Musique → onglet **Qualité**. Le tableau liste les morceaux avec leur qualité (`MP3 (320 kbps)`, `FLAC CD…`), un statut, et un sélecteur Achetable/Indispo/?. Basculer un MP3 sur « Achetable » le fait passer en « 🛒 À acheter » ; le filtre « À acheter » donne la todo-list d'achats.

- [ ] **Step 7 : Commit**

```bash
git add frontend/lib/musique.ts frontend/lib/queries/musique.ts frontend/components/musique/Qualite.tsx frontend/components/musique/Musique.tsx
git commit -m "feat(musique): onglet suivi qualité/achat Qobuz

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Vérification finale (après toutes les tâches)

- [ ] Backend : `cd backend && uv run pytest tests/test_musique/ -v` → tout vert.
- [ ] Backend : `cd backend && uv run pytest` → aucune régression ailleurs.
- [ ] Migration : `cd backend && uv run alembic upgrade head` puis `uv run alembic downgrade -1` puis `uv run alembic upgrade head` → aller-retour OK.
- [ ] Frontend : `cd frontend && npx tsc --noEmit && npx vitest run` → vert.
- [ ] Manuel : export ZIP unique (8 `.m3u8`, accents corrects à l'ouverture), onglets par label, onglet Qualité fonctionnel.
