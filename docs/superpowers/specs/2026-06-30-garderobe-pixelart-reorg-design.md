# Réorganisation des images pixel art + vignette dans l'onglet Objectif — Design

**Date :** 2026-06-30
**Statut :** approuvé (design)

## Objectif

1. Mettre de l'ordre dans les images pixel art des vêtements : aujourd'hui l'image est couplée à l'`id` (`assetUrl(v.id)` → `/garderobe/assets/{id}.png`) et les ids sont hétérogènes (`Lacoste_01`, `garmin`, `f01`, `v01`, `S01`…). On **découple** l'image de l'id via un champ explicite `Vetement.image`, et on range les fichiers en `assets/<catégorie>/<slug>.png`.
2. Afficher la vignette pixel art de chaque pièce dans l'onglet Objectif (emplacements remplis + excédent), où les pièces n'apparaissent qu'en texte.

La vignette s'affiche déjà dans l'Inventaire (`VetementCard`) et la Tenue du Jour (`SlotPreview`), toutes deux via `assetUrl(item.id)` ; on les bascule sur le nouveau helper.

## Contraintes / garanties

- **Aucun `id` de vêtement n'est modifié** (clés primaires référencées dans `TenueHistory.ids`/`.tenue` et le planner). C'est la raison d'être du champ `image`.
- Le repli `assetUrl(v.id)` (puis emoji) est conservé pour les pièces futures sans `image`.
- Frontend : tests vitest + tsc. Backend : pytest + Alembic.
- UI en français. Pas de nouvelle dépendance. Préférence utilisateur : pas d'aides d'accessibilité ajoutées.

## Schéma de slug

`slug = <sous_catégorie>-<marque>-<couleur>` puis :
- normalisation : NFKD → ASCII, minuscules, tout caractère non `[a-z0-9]` → `-`, trim des `-`, dédup des `-` consécutifs ; tokens vides ignorés.
- collision résiduelle (même `catégorie/slug` pour 2 pièces) : suffixe `-2`, `-3`… attribué de façon déterministe par ordre d'`id` croissant.

Chemin final stocké dans `Vetement.image` (et servi) : `<catégorie>/<slug>.png` (la catégorie est le dossier, pas répétée dans le nom).

Exemples (données réelles) :
- `uniqlo_01` (Haut / T-shirt / Uniqlo / Gris anthracite) → `Haut/t-shirt-uniqlo-gris-anthracite.png`
- `Fossil01` (Montre / Montre Analogique / Fossil / Marron) → `Montre/montre-analogique-fossil-marron.png`
- `Fossil02` (Montre / Montre Automatique / Fossil / Marron) → `Montre/montre-automatique-fossil-marron.png` (collision marque+couleur levée par la sous-catégorie)
- `v01` (Manteau / Bomber / Shinzo / Bleu marine) → `Manteau/bomber-shinzo-bleu-marine.png`

Les 23 pièces ont actuellement un PNG correspondant (20 par `id` exact, 3 par casse : `V01/V02/S01` ↔ `v01/v02/s01`). Le script doit retrouver le fichier source de façon insensible à la casse.

## Backend

### Modèle & migration
- `Vetement.image: Optional[str] = None` (nouvelle colonne nullable). Migration Alembic (`batch_alter_table` add_column, comme les précédentes ; `down_revision` = la tête courante).
- Propager `image` dans `VetementBase`/`VetementUpdate` (schemas), `vetement_to_dict` (common).

### Onglet Objectif
- `Emplacement` (schema) gagne `image: Optional[str] = None`.
- Fonction pure `fill_slots` : transporte `image` depuis chaque `owned` (comme `vetement_id`/`vetement_nom`/`marque`). `_empty_slot()` a `image=None`.
- `GET /objectif` (`get_objectif`) : `owned_by_type` inclut `"image": v.image`.

### Script de réorganisation (one-time)
`backend/scripts/reorg_garderobe_assets.py` :
- fonctions pures testables : `slugify(s) -> str`, `build_image_path(categorie, sous_categorie, marque, couleur) -> str` (sans suffixe), et `assign_paths(rows) -> dict[id->path]` qui applique la dédup/suffixe déterministe.
- exécution : pour chaque `Vetement`, calcule le chemin cible, retrouve le PNG source (insensible casse) dans `frontend/public/garderobe/assets/`, le **déplace** (`git mv` si possible, sinon move + add) vers `assets/<catégorie>/<slug>.png`, et écrit `Vetement.image` en base. Idempotent : si `image` est déjà à la bonne valeur et le fichier en place, ne rien faire.
- journalise les pièces sans PNG source trouvé (ne crashe pas).

## Frontend

### Helper & types
- `Vetement.image: string | null` (type TS).
- `imageUrl(v: Pick<Vetement,"image"|"id">): string` dans `lib/garderobe.ts` : si `v.image` → `/garderobe/assets/<image>` (préfixe base media non nécessaire, servi en statique Next sous `/garderobe/assets`) ; sinon `assetUrl(v.id)`. Le repli emoji reste géré par l'`onError` des composants.
- `Emplacement` (type TS) gagne `image: string | null`.
- `ObjectifResponse`/`ObjectifTypeOut` inchangés à part la propagation via `Emplacement`.

### Composants
- `VetementCard` (`InventaireTab.tsx`) et `SlotPreview` (`SlotCard.tsx`) : remplacer `assetUrl(item.id)` par `imageUrl(item)`. Comportement inchangé quand `image` est nul (repli id puis emoji).
- `ObjectifBar` : pour un emplacement non vide, afficher une vignette ~24px. Source : `slot.image` → `/garderobe/assets/<image>` si présent ; sinon pas d'image (le nom + barre restent). `imageRendering: pixelated`, `onError` → masque l'image (état local `failed`). Layout : `[vignette 24px] [nom marque] [barre]` ; lignes vides : réserver la largeur de vignette pour aligner les barres.

## Flux

1. Le script de réorg déplace les 23 PNG en sous-dossiers et renseigne `Vetement.image`.
2. Inventaire & Tenue lisent `imageUrl(v)` → mêmes vignettes, désormais via le chemin propre.
3. `GET /objectif` renvoie `image` par emplacement → `ObjectifBar` affiche la vignette de chaque pièce rattachée.

## Tests

- Backend purs : `slugify` (accents, espaces, casse, vide), `build_image_path`, `assign_paths` (collision Fossil → suffixe déterministe), `fill_slots` transporte `image` (rempli + excédent ; vide → None).
- Backend modèle/API : `Vetement.image` round-trip ; migration upgrade ; `GET /objectif` renvoie `image` sur un emplacement rempli ; `PATCH` accepte `image`.
- Frontend : `imageUrl` (avec/sans `image`) ; `ObjectifBar`/`objectif-tab` : emplacement rempli avec `image` rend une `<img>` au bon `src`, emplacement vide n'en rend pas.

## Décomposition (pour le plan)

1. `Vetement.image` colonne + migration + schémas + common.
2. `fill_slots` + `Emplacement` (+ propagation `GET /objectif`).
3. Script de réorg (fonctions pures + exécution one-time) + exécution réelle.
4. Frontend : type `image` + helper `imageUrl` + bascule `VetementCard`/`SlotPreview`.
5. `ObjectifBar` : vignette depuis `slot.image`.

Sous-projet cohérent unique (un seul spec/plan).
