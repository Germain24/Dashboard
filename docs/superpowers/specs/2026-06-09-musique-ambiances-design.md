# Module Musique — playlists par ambiance (design)

Date : 2026-06-09
Statut : validé (brainstorming)
Périmètre : transformer le placeholder `/musique` en vrai module.

## Objectif

Indexer la bibliothèque musicale locale, **classer chaque morceau par ambiance**
(café, loft, coworking, étude, repos, énergie, soirée) pour jouer/exporter des
playlists d'ambiance, et **recommander** des morceaux pour les agrandir.

Contrainte IA : **pas d'IA en mode discussion/chat**, mais l'IA **autonome** est
autorisée. Le classement et la découverte utilisent **Ollama en local** (gratuit,
aucune API payante, aucune interface de conversation).

## Faits sur la bibliothèque (vérifiés)

- Racine : `C:\Users\germa\Music`, arborescence **artiste / album / morceaux**.
- ~718 morceaux : **flac** (648), **mp3** (70), **dsf** (1). Lecture des tags via
  `mutagen` (supporte les trois).
- Chaque dossier d'album contient une pochette **`Folder.jpg`** (≈687 images) →
  source des **vignettes**, avec repli sur `cover.*`/art embarqué si absente.

## Architecture

Suit le pattern module : `models/musique.py` → `services/musique/` →
`api/routes_musique.py` → front `src/app/musique/` + `components/musique/` +
`lib/musique.ts`. La page `/musique` remplace l'actuel `ModulePlaceholder`.

### Configuration (`app/core/config.py`)

- `music_dir: str = "C:/Users/germa/Music"` (env `MUSIC_DIR`).
- `musique_ollama_host: str = "http://localhost:11434"` (env `MUSIQUE_OLLAMA_HOST`).
- `musique_ollama_model: str = "qwen2.5-coder:1.5b"` (env `MUSIQUE_OLLAMA_MODEL` ;
  un modèle généraliste comme `qwen2.5:3b` classe mieux — `ollama pull` au besoin).
- `AMBIANCES` (toutes classées par Ollama), chacune avec une **courte définition**
  injectée dans le prompt pour guider le petit modèle :
  - `café` — léger, acoustique, agréable en fond.
  - `loft` — chill/électro posé, ambiance appartement.
  - `coworking` — rythmé mais non distrayant, pour travailler.
  - `étude` — calme, instrumental, concentration.
  - `repos` — très calme, détente, sieste.
  - `énergie` — entraînant, motivant, tempo élevé.
  - `soirée` — festif, dansant.
  - `love` — chansons d'amour, romantiques (type date).
- Un morceau peut appartenir à **plusieurs** ambiances (relation plusieurs-à-plusieurs).

### Modèle de données

Table `music_track` (`models/musique.py`) — métadonnées du morceau :

| champ | type | note |
|---|---|---|
| id | int | PK |
| path | str | **chemin relatif** à `music_dir`, **unique** |
| artist | str | dossier artiste / tag |
| album | str | dossier album / tag |
| title | str | tag ou nom de fichier |
| genre | str | tag (peut être vide) |
| duree_sec | int \| None | tag |
| cover | str \| None | chemin relatif de la pochette (`…/Folder.jpg`) |
| classified | bool | True une fois passé par Ollama (évite de re-classer) |
| created_at | datetime | |

Table `track_ambiance` (`models/musique.py`) — **appartenance** plusieurs-à-plusieurs :

| champ | type | note |
|---|---|---|
| id | int | PK |
| track_id | int | FK `music_track.id`, index |
| ambiance | str | une valeur de `AMBIANCES` |
| source | str | `auto` (Ollama) ou `manuel` |

Unicité `(track_id, ambiance)`. La présence d'une ligne = le morceau est dans cette
playlist. Pas de table Album séparée (v1). Migration Alembic dédiée.

### Services (`services/musique/`)

`scan.py` :
- `relative_to_root(path, root) -> str`, `find_cover(album_dir) -> str | None`
  (cherche `Folder.jpg`/`cover.*`) — **purs/testables** sur une arbo temporaire.
- `extract_metadata(audio_path) -> dict` : via `mutagen` (artist, album, title,
  genre, duree_sec) avec repli sur la structure de dossiers si tags absents.
- `scan_library(session, root) -> dict` : parcourt `root` (extensions mp3/flac/dsf),
  upsert `MusicTrack` par `path`, renvoie compteurs (ajoutés/maj/total). Ne
  re-télécharge rien, idempotent.

`ollama_client.py` :
- `generate(prompt, *, host, model, _post=httpx.post) -> str` : POST
  `"{host}/api/generate"` (`stream=false`), renvoie le texte. `_post` injectable.

`classify.py` :
- `build_prompt(track) -> str` : prompt **contraint** listant les `AMBIANCES` avec
  leur définition courte, demandant **une ou plusieurs** ambiances (séparées par
  des virgules) ou `aucune`.
- `parse_ambiances(raw, ambiances) -> list[str]` : **pur** — normalise la réponse
  et garde les ambiances **valides** (0..N) ; ignore le reste (robuste à un petit modèle).
- `classify_untagged(session, *, generate=ollama_client.generate) -> dict` : job
  autonome qui traite les morceaux `classified == False` ; crée une ligne
  `track_ambiance` (`source="auto"`) par ambiance retournée, puis marque
  `classified=True`. Expose une progression (n_done/n_total) via un état mémoire
  (comme l'analyse Buffett), pas de chat. L'utilisateur peut ensuite corriger
  manuellement (ajout/retrait d'appartenance, `source="manuel"`).

`playlists.py` :
- `playlist_tracks(session, ambiance) -> list` : morceaux ayant une ligne
  `track_ambiance` pour cette ambiance.
- `set_membership(session, track_id, ambiance, present, source="manuel")` :
  ajoute/retire l'appartenance (idempotent ; valide `ambiance ∈ AMBIANCES`).
- `reco_bibliotheque(tracks_in, tracks_out) -> list` : **pur** — parmi les morceaux
  **hors** de l'ambiance, ceux qui partagent un **artiste ou un genre** avec les
  morceaux déjà dans l'ambiance, triés par nombre de recoupements décroissant.
- `to_m3u(tracks, *, relatif=True) -> str` : **pur** — `#EXTM3U` + `#EXTINF` +
  **chemins relatifs** (compatibles Poweramp après transfert sur téléphone).

`discovery.py` :
- `suggest_artists(session, ambiance, *, generate=...) -> list[str]` : Ollama
  propose des **artistes/genres** à explorer (pas des titres exacts → limite
  l'hallucination) à partir des artistes déjà présents dans l'ambiance.
- `parse_suggestions(raw) -> list[str]` : **pur**, parsing de la liste.

### API (`api/routes_musique.py`, préfixe `/musique`)

- `POST /musique/scan` → relance le scan (compteurs).
- `POST /musique/classify` → lance le job de classement (background) ; `GET
  /musique/classify/progress` → progression.
- `GET /musique/tracks?ambiance=&q=` → liste (chaque morceau porte `cover` + sa
  liste d'`ambiances`).
- `PUT /musique/tracks/{id}/ambiances/{ambiance}` → ajoute l'appartenance (manuel) ;
  `DELETE` → la retire. Sert à corriger le classement et à inclure une reco (1 clic).
- `GET /musique/ambiances` → liste des ambiances + compteurs.
- `GET /musique/playlists/{ambiance}` → morceaux inclus.
- `GET /musique/playlists/{ambiance}/reco` → reco bibliothèque.
- `GET /musique/playlists/{ambiance}/discovery` → suggestions Ollama (à acquérir).
- `GET /musique/playlists/{ambiance}/export.m3u` → fichier `.m3u` (chemins relatifs).
- Montage **StaticFiles lecture seule** `/media/music` → `music_dir` (pour
  vignettes + lecteur HTML5). Enregistré dans `api/__init__.py` + `main.py`
  (montage statique, comme `/media/sante`).

### Frontend (`/musique`, remplace le placeholder)

- `src/app/musique/page.tsx` → `<Musique/>` ; `loading.tsx`.
- `components/musique/` :
  - **Bibliotheque** : bouton « Scanner » + « Classer (Ollama) » avec barre de
    progression ; table des morceaux (vignette `Folder.jpg`, titre, artiste,
    album, ambiance éditable, inclus).
  - **Ambiances** : sélection d'une ambiance → playlist (vignettes), **lecteur
    HTML5** (lit `/media/music/<path>`), bouton **Export .m3u**, panneau **Reco
    bibliothèque** (1 clic pour inclure).
  - **Decouverte** : suggestions d'artistes/genres à explorer (Ollama), par ambiance.
- `lib/musique.ts` : client + types.

## Flux de données

Scan : `POST /scan` → `scan_library` (mutagen + Folder.jpg) → `music_track`.
Classement : `POST /classify` → job Ollama par morceau `classified=False` → 0..N
lignes `track_ambiance` (source auto).
Écoute : page lit `/media/music/<path>` (HTML5) ; Export `.m3u` (chemins relatifs).
Reco : bibliothèque (déterministe) + découverte (Ollama, artistes/genres).

## Gestion d'erreurs

- `music_dir` absent/illisible → scan renvoie une erreur claire (pas de 500).
- Ollama indisponible → `classify`/`discovery` renvoient un message « Ollama hors
  ligne » sans casser le reste ; les morceaux restent `ambiance=None`.
- Tag illisible → repli sur l'arborescence (artiste/album/fichier) ; jamais d'arrêt.
- Pochette absente → `cover=None`, vignette par défaut côté front.
- **Lecteur intégré = aperçu** : le HTML5 audio ne lit pas le `.dsf` (et le `.flac`
  selon le navigateur). Les morceaux non lisibles sont affichés mais marqués « non
  lisible dans le navigateur » ; l'usage principal reste l'export `.m3u` → Poweramp
  sur le téléphone, qui lit tous les formats.

## Tests (TDD)

Purs / sans réseau :
- `find_cover` / `relative_to_root` sur une arbo temporaire (fichiers vides).
- `parse_ambiances` (réponse mono/multi/bruitée/`aucune` → liste filtrée 0..N).
- `to_m3u` (format `#EXTINF`, chemins relatifs).
- `reco_bibliotheque` (recoupement artiste/genre, tri par recoupements) sur données injectées.
- `parse_suggestions` (découverte).
- `classify_untagged` avec `generate` **injecté** (faux Ollama renvoyant 2 ambiances)
  → crée 2 lignes `track_ambiance` et marque `classified=True`.
- `set_membership` : ajout/retrait idempotent ; rejet d'une ambiance inconnue.
- Route smoke : `POST /scan` sur un `music_dir` temporaire ; `PUT`/`DELETE`
  d'appartenance ; `export.m3u` renvoie du texte M3U.

`mutagen` ajouté aux dépendances backend.

## Hors périmètre (YAGNI)

Édition de tags des fichiers, table Album dédiée, synchro automatique vers le
téléphone, services externes payants. Découverte limitée à des suggestions
d'artistes/genres (pas d'achat/streaming intégré).
