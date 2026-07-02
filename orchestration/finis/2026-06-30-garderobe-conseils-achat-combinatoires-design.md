# Conseils d'achat combinatoires — Design

**Date :** 2026-06-30
**Statut :** approuvé (design)

## Objectif

Remplacer le contenu de l'onglet **Recommandations** (4 heuristiques actuelles) par un modèle **combinatoire** : pour chaque achat possible (slot de base × couleur), calculer combien de **nouvelles tenues** il débloque, et classer par gain. Répond à « quelle couleur acheter pour débloquer le plus de tenues ».

## Définition d'une tenue

Une tenue = un triplet **(Haut, Pantalon, Chaussures)** — les 3 slots `ALWAYS` de `SLOTS` — dont les couleurs sont **2-à-2 compatibles** via `colors_compat` (déjà dans `app/services/garderobe/style.py`). Les pièces remplissent un slot selon leur `categorie` (listes `categories` des slots ALWAYS). Les slots météo/optionnels (manteau, accessoires…) ne comptent pas.

Le décompte porte sur les **triplets de pièces réelles** (deux hauts bleus distincts = 2 combinaisons). La couleur ne sert qu'à la compatibilité ; conséquence naturelle : une couleur neutre (compatible avec tout) débloque le plus de tenues, ce qui en fait un bon conseil d'achat.

## Backend — fonctions pures

Nouveau module `app/services/garderobe/purchase_combos.py` :

- `base_slot_of(item: dict) -> str | None` : renvoie `"Haut"` / `"Pantalon"` / `"Chaussures"` selon `item["categorie"]` (via les `categories` des slots ALWAYS de `SLOTS`), sinon `None`.
- `count_outfits(wardrobe: list[dict]) -> int` : regroupe les pièces par slot de base, énumère les triplets (Haut × Pantalon × Chaussures), compte ceux dont les 3 couleurs sont 2-à-2 `colors_compat`. (Quelques dizaines de triplets → coût négligeable.)
- `purchase_advice(wardrobe: list[dict], top: int = 5) -> list[dict]` :
  - `base = count_outfits(wardrobe)`.
  - pour chaque `slot ∈ {"Haut","Pantalon","Chaussures"}` × chaque `couleur ∈ PALETTE` (= `NEUTRES + SECONDAIRES + ACCENTS`) :
    - item virtuel `{"categorie": slot, "couleur": couleur}` ;
    - `gain = count_outfits(wardrobe + [virtuel]) - base`.
  - garde les `gain > 0`, trie par `gain` décroissant (tie-break déterministe : ordre des slots puis ordre `PALETTE`), renvoie le top N : `{"slot", "couleur", "debloque": gain, "total_apres": base + gain}`.

(Les `categories` exactes des slots virtuels — `"Haut"`, `"Pantalon"`, `"Chaussures"` — appartiennent bien aux listes `categories` des slots ALWAYS, donc `base_slot_of` les reconnaît.)

## API

`GET /garderobe/recommendations` est **repointé** vers le modèle combinatoire.

- Nouvelle réponse `ConseilsAchatResponse` :
  ```
  { "total_tenues": int, "conseils": [ {"slot": str, "couleur": str, "debloque": int, "total_apres": int} ] }
  ```
- `insights.py` : la route construit `items = [vetement_to_dict(v) …]`, `base = count_outfits(items)`, `conseils = purchase_advice(items)`, renvoie `ConseilsAchatResponse(total_tenues=base, conseils=[ConseilAchat(**c) …])`.

**Suppression de l'ancien** (heuristiques) :
- supprimer `app/services/garderobe/recommendations.py` et `backend/tests/test_garderobe/test_recommendations.py` ;
- retirer l'import + l'export `get_purchase_recommendations` de `app/services/garderobe/__init__.py` ;
- retirer/remplacer `RecommendationOut` dans `schemas.py` par `ConseilAchat` + `ConseilsAchatResponse`.

(Le `useRecommendations` de `vue-360` vient de `routines` — sans rapport, non touché.)

## Frontend

- `lib/garderobe.ts` : remplacer le type `Recommendation` par
  ```ts
  export type ConseilAchat = { slot: string; couleur: string; debloque: number; total_apres: number };
  export type ConseilsAchat = { total_tenues: number; conseils: ConseilAchat[] };
  ```
  et `garderobeApi.recommendations()` renvoie `ConseilsAchat`.
- `lib/queries/garderobe.ts` : `useGarderobeRecommendations` inchangé dans sa forme (le type de retour suit l'API).
- `Garderobe.tsx` : `recsQ.data` est désormais un objet ; passer `data` (et non `?? []`) à `RecommandationsTab` (avec un défaut `{ total_tenues: 0, conseils: [] }`).
- `RecommandationsTab.tsx` : afficher « Tu as actuellement **N** tenues possibles » puis la liste des conseils : « Ajouter **[slot] [couleur]** → **+K** tenues » avec la barre de progression (proportionnelle au `debloque` max). Si `conseils` est vide : message « Ajoute d'abord des hauts/pantalons/chaussures pour débloquer des tenues » (cas garde-robe trop incomplète).
- `__tests__/queries/garderobe.test.tsx` : mettre à jour le mock `recommendations` vers la nouvelle forme.

## Flux

1. L'onglet Recommandations appelle `GET /recommendations`.
2. Le backend compte les tenues actuelles et évalue chaque (slot × couleur) de la palette.
3. La réponse classe les achats par tenues débloquées ; l'onglet les affiche.

## Gestion d'erreur / cas limites

- Garde-robe sans triplet possible (ex. 0 chaussure) → `total_tenues = 0`, `conseils` peut rester vide (un seul ajout ne forme pas un triplet) → message d'invite.
- Couleur déjà très présente : `gain` reflète le marginal réel (souvent élevé pour les neutres polyvalents).

## Tests

- Backend purs (`purchase_combos`) : `base_slot_of` (catégories de chaque slot, hors-slot → None) ; `count_outfits` (compte les triplets compatibles, exclut les incompatibles) ; `purchase_advice` (gain marginal correct, tri décroissant déterministe, top N, gains nuls exclus, neutre polyvalent en tête).
- Backend API : `GET /recommendations` renvoie la nouvelle forme `{total_tenues, conseils}` sur une mini-garde-robe ; structure des conseils.
- Frontend : `RecommandationsTab` rend le total + au moins un conseil ; mock query mis à jour.

## Décomposition

1. Fonctions pures `purchase_combos.py` + tests.
2. API repointée + schémas + suppression de l'ancien (recommendations.py, test, export) + tests API.
3. Frontend : types + `Garderobe.tsx` + `RecommandationsTab.tsx` + mock test.

Sous-projet cohérent unique.
