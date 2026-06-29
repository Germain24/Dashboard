# Musique — Playlists `.m3u8` + export ZIP unique

**Date :** 2026-06-29
**Branche :** `feat/ameliorations-section-e`
**Statut :** Design validé (en attente de relecture utilisateur)

## Contexte

L'onglet Musique gère des playlists d'« ambiances » : chaque morceau peut appartenir
à plusieurs playlists (table `track_ambiance`, une ligne par couple morceau+playlist).
Un classement automatique (API Claude, sinon Ollama local) attribue les playlists aux
nouveaux morceaux.

Trois problèmes / demandes :

1. **Format d'export** — l'export actuel produit un `.m3u` (la mention `.m3u` laisse les
   lecteurs interpréter le fichier dans l'encodage local). Les noms de morceaux/chemins
   contiennent des caractères spéciaux → il faut du `.m3u8` (UTF-8 explicite).
2. **Téléchargement unique** — il faut **un seul fichier** téléchargé (ZIP) contenant
   toutes les playlists, pas un téléchargement par playlist.
3. **Nouveau jeu de playlists** — remplacer entièrement les 8 ambiances actuelles
   (`café, loft, coworking, étude, repos, énergie, soirée, love`) par 8 nouvelles.

Le multi-appartenance (un morceau dans plusieurs playlists) est **déjà supporté** par le
modèle `TrackAmbiance` : aucune modification du modèle de données n'est requise.

## Décisions validées

- Export = **un seul ZIP** contenant un `.m3u8` par playlist.
- Remplacement **total** des anciennes ambiances.
- `.m3u8` écrit en **UTF-8 avec BOM** (robustesse Poweramp/Windows).
- **Purge automatique au démarrage** des appartenances aux noms inconnus.

## Architecture

### Le problème des `/` dans les noms

3 playlists contiennent des `/` et plusieurs ont espaces/parenthèses/accents. Les `/`
cassent (a) le routage FastAPI (`/playlists/{ambiance}`, ajout/retrait de morceau : le
`%2F` est ré-interprété et l'URL ne matche plus) et (b) les noms de fichiers dans le ZIP
(un `/` créerait des sous-dossiers).

**Solution : couple `slug` ↔ `label`.**
- `slug` : identifiant ASCII stable → stocké en base (`track_ambiance.ambiance`), utilisé
  dans les URLs.
- `label` : nom affiché dans l'UI et utilisé comme titre `#PLAYLIST:` dans le `.m3u8`.
- nom de fichier dans le ZIP : label « assaini » pour le système de fichiers
  (`/` → ` - `, suppression des caractères Windows interdits `< > : " \ | ? *`).

| Label affiché | Slug (DB/URL) | Fichier `.m3u8` dans le ZIP |
|---|---|---|
| café pour le petit dep | `cafe-petit-dej` | `café pour le petit dep.m3u8` |
| coworking/travail/detente | `coworking-travail-detente` | `coworking - travail - detente.m3u8` |
| soirée ( francophone ) | `soiree-francophone` | `soirée (francophone).m3u8` |
| soirée ( internationale ) | `soiree-internationale` | `soirée (internationale).m3u8` |
| amour/love/sex | `amour-love-sex` | `amour - love - sex.m3u8` |
| chanson francaise | `chanson-francaise` | `chanson francaise.m3u8` |
| Mélancolie | `melancolie` | `Mélancolie.m3u8` |
| sport/gym | `sport-gym` | `sport - gym.m3u8` |

### Composants

**1. `backend/app/services/musique/constants.py`**

Remplacer `AMBIANCES` par le catalogue des 8 playlists. Structure ordonnée
`slug → {label, desc}` + helpers dérivés :
- `AMBIANCE_NAMES : list[str]` — slugs (ordre d'affichage), valeurs stockées en base.
- `AMBIANCE_LABELS : dict[str, str]` — slug → label.
- `AMBIANCES : dict[str, str]` — slug → description (consommé par le classifieur).

Descriptions indicatives (pour guider l'IA, ajustables) :
- `cafe-petit-dej` : léger, doux, agréable au réveil / petit-déjeuner.
- `coworking-travail-detente` : rythmé mais non distrayant, fond de travail/concentration.
- `soiree-francophone` : festif/dansant, chansons francophones.
- `soiree-internationale` : festif/dansant, hits internationaux.
- `amour-love-sex` : romantique, sensuel, intime.
- `chanson-francaise` : chanson française (variété, auteurs-compositeurs francophones).
- `melancolie` : mélancolique, doux-amer, introspectif.
- `sport-gym` : entraînant, tempo élevé, motivation sportive.

**2. Classement IA — `claude_client.py` & `classify.py`**

- Le prompt liste **labels + descriptions** (plus naturel pour le modèle).
- L'enum des sorties structurées (`_OUTPUT_SCHEMA`) = **labels** ; on convertit
  label → slug avant insertion en base.
- `classify.py` : ajouter un mapping `label → slug` ; `parse_ambiances` (chemin Ollama)
  et `_classify_par_lots` (chemin Claude) stockent des **slugs**.
- `_SYNONYMES` : nettoyé/réécrit pour pointer vers les nouveaux labels (ex. `travail`,
  `detente`, `romantique`, `melancolique`…). Synonymes obsolètes supprimés.

**3. Export — `playlists.py` (service) + `api/musique/playlists.py`**

- Nouvelle fonction `to_m3u8(tracks, *, titre) -> bytes` :
  - encodage **UTF-8 avec BOM** (`﻿`) ;
  - `#EXTM3U`, puis `#PLAYLIST:<titre>`, puis pour chaque morceau
    `#EXTINF:<durée>,<artiste> - <titre>` + chemin relatif.
  - (Conserver `to_m3u` n'est plus nécessaire ; remplacé par `to_m3u8`.)
- Nouveau endpoint `GET /musique/playlists/export.zip` :
  - construit pour chacune des 8 playlists un `.m3u8` (nom de fichier = label assaini) ;
  - empaquette le tout dans un ZIP en mémoire (`zipfile`, stdlib) ;
  - renvoie `Response(media_type="application/zip")` avec
    `Content-Disposition: attachment; filename="playlists-musique.zip"`.
  - Une playlist vide est tout de même incluse (fichier `.m3u8` avec en-tête seul).
- Supprimer l'ancien endpoint `GET /musique/playlists/{ambiance}/export.m3u`.

**4. `/musique/ambiances` — `api/musique/bibliotheque.py`**

Chaque entrée renvoie désormais `{ "ambiance": <slug>, "label": <label>, "count": <n> }`.
Renvoie toujours les 8 playlists (même à 0 morceau).

**5. Frontend — `frontend/lib/musique.ts` & `frontend/components/musique/Ambiances.tsx`**

- `AmbianceCount` : ajouter `label: string`.
- `musiqueApi` : remplacer `exportUrl(a)` par `exportAllUrl()` →
  `…/musique/playlists/export.zip`.
- `Ambiances.tsx` :
  - état `sel` initialisé au **premier slug** du catalogue (plus `"café"` codé en dur) ;
  - onglets : `key`/valeur = slug, texte affiché = `label` (`{a.label} ({a.count})`) ;
  - remplacer le lien `⬇ .m3u` par un bouton unique
    `<a href={exportAllUrl()} download>⬇ Tout exporter (.zip)</a>`.

**6. Migration / purge — au démarrage**

Au lancement de l'application (hook de démarrage existant ou init DB) :
- supprimer toutes les lignes `track_ambiance` dont `ambiance` n'est pas dans
  `AMBIANCE_NAMES` (anciens noms) ;
- remettre `classified = False` sur les morceaux ainsi orphelinés pour qu'ils repassent
  au classement.

Idempotent : sans ligne inconnue, ne fait rien.

## Flux de données

```
Classement : morceaux non classés
  → prompt (labels+desc) → IA renvoie labels
  → conversion label→slug → INSERT track_ambiance(ambiance=slug)

Affichage onglet : GET /musique/ambiances → [{slug,label,count}]
  → sélection slug → GET /musique/playlists/{slug} → morceaux

Export : clic « Tout exporter » → GET /musique/playlists/export.zip
  → pour chaque slug : to_m3u8(tracks, titre=label) (UTF-8 BOM)
  → zip{label assaini}.m3u8 → 1 seul téléchargement
```

## Gestion d'erreurs

- Slug inconnu sur une route playlist → 404 / liste vide (comportement actuel conservé).
- `set_membership` rejette toujours un slug hors `AMBIANCE_NAMES` (422).
- Export d'une playlist vide → `.m3u8` minimal (en-tête seul), pas d'erreur.
- Échec API Claude au classement → comportement inchangé (interruption + message).

## Tests (TDD)

Backend :
- catalogue : `AMBIANCE_NAMES` (8 slugs), `AMBIANCE_LABELS` cohérent, pas de `/` dans les slugs.
- `to_m3u8` : commence par BOM + `#EXTM3U`, contient `#PLAYLIST:<titre>`, lignes
  `#EXTINF` correctes, durée inconnue → `-1`, sortie `bytes` décodable UTF-8.
- mapping label→slug du classifieur (Claude et Ollama) : insère des slugs.
- endpoint `export.zip` : `Content-Type application/zip`, 8 entrées `.m3u8`, noms de
  fichiers assainis (pas de `/`), contenu d'une entrée commence par BOM+`#EXTM3U`.
- routes playlist/membership fonctionnent avec un slug contenant à l'origine un `/`.
- `/ambiances` renvoie `label` pour chaque entrée.
- purge au démarrage : ligne `ambiance="café"` supprimée + morceau remis `classified=False`.

Frontend :
- `Ambiances` affiche les labels dans les onglets ; le bouton pointe vers `export.zip`
  avec `download`.

Mettre à jour les tests existants (`test_api.py`, `test_playlists.py`) qui référencent
les anciens noms (`café`) et la route `export.m3u`.

## Hors périmètre (YAGNI)

- Pas de migration « intelligente » ancien→nouveau (remplacement total assumé).
- Pas d'édition des labels/descriptions depuis l'UI (catalogue en dur côté backend).
- Pas de changement du modèle `TrackAmbiance` (multi-appartenance déjà supporté).
