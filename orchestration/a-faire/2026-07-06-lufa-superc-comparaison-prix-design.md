# Comparaison de prix Super C / Adonis / Lufa pour la liste de courses

Statut : à faire · Créé le 2026-07-06

## Contexte

Aujourd'hui, deux systèmes distincts gèrent les prix des aliments :
1. **Catalogue nutrition** `aliments.csv` — prixé Costco + overlay Adonis (fruits/légumes) via
   `backend/app/services/sante/adonis_pricing.py`, utilisé par l'optimiseur nutritionnel.
2. **Liste de courses hebdo** `backend/app/services/cuisine/shopping_list.py` — générée depuis
   le plan de repas (`MealPlanEntry` → `RecipeIngredient`), groupée par rayon (`RAYON_MAP`),
   sans notion de magasin ni de prix.

Le user veut ajouter Super C et la Ferme Lufa (point relais) comme sources de prix/promos
pour la liste de courses réelle, avec un système de comparaison par catégorie d'aliment.
**Portée de cette phase : la liste de courses hebdo uniquement.** `aliments.csv` et
l'optimiseur nutrition restent inchangés (phase 2 potentielle, hors scope ici).

## Règle de comparaison (validée avec le user)

Pour chaque item de la liste de courses, on détermine sa catégorie d'achat, puis on compare
le prix entre les 2 magasins pertinents (le 3e est exclu) :

| Catégorie          | Comparé            | Exclu   |
|--------------------|---------------------|---------|
| Pantry/Staples     | Super C vs Adonis   | Lufa    |
| Viandes (Volume)   | Adonis vs Super C   | Lufa    |
| Viandes (Nobles)   | Lufa vs Adonis      | Super C |
| Tofu/Protéines     | Adonis vs Super C   | Lufa    |
| Fruits/Légumes     | Adonis vs Lufa      | —       |
| F&L exception : patates, oignons | toujours Super C, pas de comparaison | — |

Le magasin gagnant est celui avec le prix matché le plus bas pour cet item cette semaine.
Un item sans catégorie connue ou sans prix matché dans aucun des 2 magasins comparés garde
le comportement actuel (rayon simple, pas de badge magasin).

## Architecture

### 1. Scrapers (Playwright, pattern `.adonis_scrape.mjs`)

- `frontend/.superc_scrape.mjs` — vitrine Instacart `instacart.ca/store/super-c`, recherche
  par terme, même logique d'extraction (prix, unit_price, format, promo) que l'existant.
- `frontend/.superc_flyer_scrape.mjs` — circulaire hebdo Super C (superc.ca ou agrégateur
  type Flipp/Reebee), pour capter les rabais ponctuels non reflétés sur Instacart.
- `frontend/.lufa_scrape.mjs` — lufa.com, **profil Edge persistant**
  (`chromium.launchPersistentContext`) pour réutiliser une session déjà connectée avec point
  relais choisi (login manuel une fois, comme pour Adonis/Instacart aujourd'hui).
- Sortie JSON dans `data/imports/Cuisine/{superc,superc_flyer,lufa}.json`, même format que
  `adonis_fruits_legumes.json` (liste d'items avec name/price/unit_price/unit/format/on_sale).

### 2. Termes de recherche dynamiques

Pas de liste fixe de termes (contrairement au `TERMS` actuel d'Adonis, limité aux
fruits/légumes). Les termes de recherche pour les 3 scrapers sont dérivés de la liste de
courses agrégée de la semaine courante (sortie de `compute_shopping()`), pour rester rapide
et automatiquement à jour avec le plan de repas.

### 3. Classification catégorie d'achat

Nouveau module `backend/app/services/cuisine/store_categories.py` : dict
`{nom_ingredient_fr: categorie}` avec `categorie` ∈
`{pantry, viande_volume, viande_noble, fruits_legumes, tofu_proteines}`. Ingrédients non
mappés → comportement actuel inchangé (rayon simple `RAYON_MAP`, pas de comparaison).

### 4. Service de comparaison

Nouveau module `backend/app/services/cuisine/store_pricing.py` (miroir de
`adonis_pricing.py`) :
- charge les caches JSON des 3 sources (+ le cache Adonis existant, réutilisé tel quel),
- pour chaque item de la liste de courses, résout sa catégorie, applique la règle du tableau
  ci-dessus, matche le nom contre les items scrapés (même logique de matching mots-clés que
  `_matches()` dans `adonis_pricing.py`), retient le prix le plus bas entre les 2 candidats,
- retourne un overlay `{ingredient: {magasin, prix, promo: bool}}`.

### 5. Rafraîchissement au démarrage

Au démarrage du backend (évènement startup FastAPI), déclenche un rafraîchissement
best-effort des 3 nouveaux scrapers (même garde `refresh_if_stale`/max-age configurable que
l'existant Adonis) — ne bloque jamais le démarrage, échoue silencieusement si node/Edge/
réseau absent, conserve le cache existant en cas d'échec.

### 6. Intégration liste de courses

`compute_shopping()` (`shopping_list.py`) applique l'overlay `store_pricing` sur chaque
item retourné : ajoute `magasin_recommande`, `prix_estime`, `promo`. Le frontend (page
courses) affiche un badge magasin + prix par ligne, avec un indicateur visuel si `promo`.

## Hors scope (phase 2 potentielle, non traitée ici)

- Intégration au catalogue `aliments.csv` / optimiseur nutrition.
- Circulaires Costco (le catalogue nutrition reste Costco-only, hors scope).
- Historique de prix / tendance dans le temps.

## Tests

- Tests unitaires purs pour `store_categories` (classification) et `store_pricing` (règle de
  comparaison + matching), suivant le pattern de `test_adonis_pricing.py` — best-effort,
  jamais bloquant si un cache est absent.
- Pas de test end-to-end des scrapers Playwright (comme l'existant Adonis) — best-effort par
  design, testé manuellement.
