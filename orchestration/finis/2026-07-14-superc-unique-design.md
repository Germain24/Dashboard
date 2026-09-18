# Passage « Super C unique » — courses + optimiseur nutrition

Statut : à faire · Créé le 2026-07-14

## Contexte

Le user veut arrêter de faire plusieurs magasins pour l'épicerie et tout consolider sur
**Super C**. Aujourd'hui deux systèmes utilisent des prix multi-magasins :

1. **Liste de courses hebdo** — `backend/app/services/cuisine/store_pricing.py` annote chaque
   item avec un magasin recommandé (Super C **ou** Adonis) + prix estimé, piloté par la table
   `CATEGORY_STORES`. C'est ce qui force la virée multi-magasins.
2. **Optimiseur nutrition** — `aliments.csv` est prixé **Costco/Kirkland**, avec les
   **fruits/légumes re-tarifés Adonis** (`backend/app/services/sante/adonis_pricing.py`,
   `build_price_overlay`). Ces prix pilotent le calcul de coût qui *choisit* les aliments.

Super C dispose déjà de toute son infra de prix : scrapers `frontend/.superc_scrape.mjs` et
`frontend/.superc_flyer_scrape.mjs`, caches `data/imports/Cuisine/superc.json` /
`superc_flyer.json`, et gestion des promos circulaire (`_best_price`).

## Objectif

Ne garder que Super C partout : liste de courses **et** prix de l'optimiseur, jusqu'à
reconstruire `aliments.csv` sur des prix Super C. Projet découpé en 3 phases livrables
séquentiellement, chacune avec son propre plan d'implémentation.

## Décisions validées avec le user

- **Périmètre** : complet (courses + optimiseur + reconstruction `aliments.csv`).
- **Items que Super C ne vend pas** (suppléments/poudres `Inshape`/`ON`, formats & marques
  `Costco`/`Kirkland`) : **retirés du catalogue** (pas de repli Costco, pas de saisie manuelle).
- **Séquencement** : les 3 phases sont conçues d'abord (ce doc) ; l'implémentation suivra
  phase par phase.

## ⚠️ Risque assumé (Phase 3)

Retirer les protéines/suppléments enlève de l'optimiseur nutrition les **sources de protéines
les moins chères au gramme**. Le user est en objectif de poids à cible protéique élevée :
l'optimiseur pourrait avoir du mal à atteindre les macros de protéines à bas coût, voire rendre
certaines cibles difficiles à satisfaire. Risque **accepté** par le user. Porte de sortie si
gênant à l'usage : rebasculer uniquement ces items en repli Costco (non retenu ici).

---

## Phase 1 — Liste de courses en Super C seul

**Fichier** : `backend/app/services/cuisine/store_pricing.py`

- `CATEGORY_STORES` : toutes les catégories → `"superc"` (fin des tuples de comparaison).
  ```python
  CATEGORY_STORES = {
      "pantry": "superc",
      "viande_volume": "superc",
      "viande_noble": "superc",
      "tofu_proteines": "superc",
      "fruits_legumes": "superc",
  }
  ```
- Supprimer l'exception `FRUITS_LEGUMES_SUPERC_ONLY` (devenue redondante — tout `fruits_legumes`
  est déjà Super C) et la branche correspondante en tête de `recommend_store`.
- `recommend_store` se réduit au chemin mono-magasin (`isinstance(stores, str)`), le chemin de
  comparaison à 2 magasins devient mort → à retirer.
- **Conserver** la logique promo circulaire dans `_best_price` (`superc` + `superc_flyer`).
- La branche `store == "adonis"` de `load_cached_items` devient inutilisée par les courses ;
  la laisser dormante (elle reste appelée par l'optimiseur jusqu'à la Phase 2).
- `refresh_all_if_stale` ne rafraîchit déjà que `superc`/`superc_flyer` → aucun changement.

**Comportement attendu** : chaque item classé recommande Super C avec son prix (courant ou
circulaire, `promo=True` si la circulaire gagne) ; item non classé → pas de badge (inchangé).

**Tests** (`backend/tests/` — répliquer le style des tests store_pricing existants) :
- chaque catégorie de `CATEGORY_STORES` → magasin « Super C » ;
- circulaire moins chère que le prix courant → gagne, `promo=True` ;
- item hors catégorie / sans match → `recommend_store` renvoie `None`, item non annoté ;
- `apply_recommendations` reste best-effort (une exception sur un item ne casse pas la liste).

---

## Phase 2 — Prix produits de l'optimiseur en Super C

**Fichiers** : `backend/app/services/sante/` (autour de `adonis_pricing.py`) + site d'appel de
l'overlay.

- Généraliser la construction d'overlay en une fonction **paramétrée par le cache magasin**,
  réutilisant `PRODUCE_MAP` (mots-clés EN + fraction comestible) et la conversion CAD/100 g
  comestible (`adonis_price_per_100g_edible` → version neutre `price_per_100g_edible`).
- Nouvel overlay Super C lisant `superc.json` (via `store_pricing.load_cached_items("superc")`
  ou lecture directe du cache), produisant le même `dict[nom_FR → CAD/100 g]`.
- Basculer le **site d'appel** : `apply_adonis_produce_prices` (`adonis_pricing.py:231`, qui
  fait `apply_overlay_to_df(df, build_price_overlay(items))`) est appelé depuis
  `backend/app/api/sante/plan.py:168`. Le remplacer/dupliquer en une variante Super C
  (`apply_superc_produce_prices`) et mettre à jour l'appel dans `plan.py`. Vérifier s'il existe
  d'autres consommateurs de l'overlay Adonis avant de le retirer.
- Base non-produits = Costco (inchangée à ce stade, remplacée en Phase 3).

**Tests** :
- overlay Super C : CAD/100 g comestible correct depuis des items `superc.json` factices ;
- item produce sans match Super C → absent de l'overlay (le prix de base reste) ;
- le catalogue chargé reflète les prix Super C pour les fruits/légumes.

---

## Phase 3 — `aliments.csv` entièrement Super C

**Fichiers** : mapping catalogue↔Super C, `frontend/.superc_scrape.mjs`, script de
reconstruction d'`aliments.csv`, `data/imports/Cuisine/` (ou emplacement d'`aliments.csv`).

- Étendre le mapping type `PRODUCE_MAP` à **tous** les ~71 items du catalogue :
  `item_FR → { termes Super C EN, fraction comestible, conversion d'unité }`, conforme aux
  conventions de `README_aliments.md`.
- Étendre la liste de termes de recherche de `.superc_scrape.mjs` à tout le catalogue (au lieu
  des seuls mots-clés de la liste de courses de la semaine), scraper, mettre en cache.
- Construire le prix CAD/100 g (ou par unité selon la convention de la colonne) pour chaque item.
- **Politique de retrait** : tout item sans match Super C fiable est **retiré** d'`aliments.csv`
  (suppléments `Inshape`/`ON`, items `Costco`/`Kirkland`). Journaliser la liste des retirés.
- Reconstruire `aliments.csv` : prix Super C pour les items conservés, base Costco supprimée.
- Une fois `aliments.csv` en Super C, l'overlay Phase 2 peut être simplifié/retiré si les
  fruits/légumes sont déjà prixés Super C dans le CSV (à trancher dans le plan Phase 3).

**Tests** :
- construction de prix depuis un `superc.json` factice → CAD/100 g attendus ;
- items non matchés → exclus du CSV reconstruit, présents dans le log des retirés ;
- garde-fou optimiseur : le catalogue reconstruit reste chargeable et l'optimiseur tourne
  (signaler explicitement si une cible protéique devient infaisable — cf. risque).

---

## Hors scope

- Aucun autre magasin (Adonis, Lufa, Costco) comme source de prix pour les courses.
- Pas de repli Costco ni de saisie manuelle pour les items retirés (décision user).
- Pas de refonte de la génération de la liste de courses elle-même (plan de repas → items) :
  seule la couche prix/magasin change.
