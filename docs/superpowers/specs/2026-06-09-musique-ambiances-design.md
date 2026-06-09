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
- `AMBIANCES = ["café", "loft", "coworking", "étude", "repos", "énergie", "soirée"]`
  (constante module, ajustable).

### Modèle de données

Table `music_track` (`models/musique.py`) :

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
| ambiance | str \| None | une valeur de `AMBIANCES`, ou None si non classé |
| ambiance_source | str | `auto` (Ollama) ou `manuel` |
| inclus | bool | True = présent dans la playlist de son ambiance |
| created_at | datetime | |

Pas de table Album séparée (v1) : la pochette/album sont portés par le morceau.
Migration Alembic dédiée.

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
- `build_prompt(track) -> str` : prompt **contraint** listant les ambiances
  autorisées, demandant **un seul mot**.
- `parse_ambiance(raw, ambiances) -> str | None` : **pur** — normalise la réponse
  et la mappe à une ambiance valide, sinon None (robuste à un petit modèle).
- `classify_untagged(session, *, generate=ollama_client.generate) -> dict` : job
  autonome qui classe les morceaux `ambiance is None` ; met à jour
  `ambiance`/`ambiance_source="auto"`. Expose une progression (n_done/n_total)
  via un état mémoire (comme l'analyse Buffett), pas de chat.

`playlists.py` :
- `playlist_tracks(session, ambiance) -> list` : morceaux `ambiance==X & inclus`.
- `reco_bibliotheque(session, ambiance) -> list` : `ambiance==X & not inclus`
  (**pur** sur des dicts en test).
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
- `GET /musique/tracks?ambiance=&q=` → liste (avec `cover` pour la vignette).
- `PATCH /musique/tracks/{id}` → override `ambiance` (`ambiance_source="manuel"`)
  et/ou `inclus`.
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
Classement : `POST /classify` → job Ollama par morceau non classé → `ambiance`.
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
- `parse_ambiance` (réponses propres, bruitées, invalides → None).
- `to_m3u` (format `#EXTINF`, chemins relatifs).
- `reco_bibliotheque` (filtre ambiance & inclus) sur des données injectées.
- `parse_suggestions` (découverte).
- `classify_untagged` avec `generate` **injecté** (faux Ollama) → met à jour les ambiances.
- Route smoke : `POST /scan` sur un `music_dir` temporaire ; `export.m3u` renvoie du texte M3U.

`mutagen` ajouté aux dépendances backend.

## Hors périmètre (YAGNI)

Édition de tags des fichiers, multi-ambiances par morceau, table Album dédiée,
synchro automatique vers le téléphone, services externes payants. Découverte
limitée à des suggestions d'artistes/genres (pas d'achat/streaming intégré).
