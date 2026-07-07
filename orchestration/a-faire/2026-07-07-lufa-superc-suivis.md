# Suivis — Comparaison prix Super C / Adonis / Lufa

Statut : à faire · Créé le 2026-07-07
Suite de : `orchestration/finis/2026-07-06-lufa-superc-comparaison-prix-{design,plan}.md`
(feature livrée, 10 commits `1058fe2..9c37540` sur `main`)

Gaps connus laissés par la livraison initiale, à traiter séparément.

## 1. Scraper circulaire Super C bloqué (refonte nécessaire)

`frontend/.superc_flyer_scrape.mjs` retourne 0 items en conditions réelles : le contenu de
la circulaire `superc.ca/circulaire` est en fait dans un **iframe cross-origin**
(`circulaire.superc.ca`) protégé par un **reCAPTCHA**. Le tuning des sélecteurs CSS ne
suffira pas. Pistes : cibler l'iframe directement (si le reCAPTCHA le permet), ou trouver une
source alternative (agrégateur type Flipp/Reebee qui expose peut-être une API/JSON sans
reCAPTCHA).

## 2. Connexion manuelle Lufa requise (one-time, pas un bug)

`frontend/.lufa_scrape.mjs` utilise un profil Edge persistant (`.lufa_profile/`) mais ne
retournera de vraies données qu'après une connexion manuelle unique (login + choix du point
relais), à faire par l'utilisateur sur sa propre machine — voir les instructions dans le
commentaire du script / le plan archivé. Rien à développer ici, juste une action utilisateur
à faire avant que le cache Lufa se peuple.

## 3. Vérification visuelle du badge non faite

Le badge magasin (`CoursesTab.tsx`) est validé par `tsc`/`eslint` (propre) et une revue de
code ligne par ligne, mais son rendu réel avec des données de recommandation authentiques
n'a jamais été confirmé en navigateur (tentative de création d'une recette de test
abandonnée — le combobox ingrédient ne coopérait pas avec l'automatisation navigateur). À
confirmer visuellement une fois un vrai plan de repas + des caches magasin peuplés.

## 4. Cache Adonis réutilisé = produce-only

Le cache Adonis (`adonis_fruits_legumes.json`, produit par `.adonis_scrape.mjs`) ne couvre
que les fruits/légumes. Les catégories `pantry`, `viande_volume` et `tofu_proteines` n'auront
donc jamais de prix côté Adonis — `recommend_store` retombe correctement sur le seul côté
disponible (Super C), ce n'est pas un crash, mais la comparaison "vs Adonis" pour ces 3
catégories est un no-op tant qu'`.adonis_scrape.mjs` n'est pas étendu au-delà des
fruits/légumes (termes de recherche EN pantry/viande/tofu à ajouter, si souhaité).

## 5. Scraper Lufa : mauvais pattern d'URL (à corriger)

Diagnostic du 2026-07-07 : `.lufa_scrape.mjs` construit l'URL de recherche comme
`${MARKET_URL}?search=${term}`, mais le vrai site n'utilise pas ce paramètre. La structure
réelle est par **catégorie** : `montreal.lufa.com/en/marketplace/category/{slug}` (ex.
`seafood`, `meat`, `pantry`, `veggies`, `fruit`, `dairy-eggs`, `plant-based-alternatives`,
etc. — liste complète trouvée en inspectant les liens de nav). Il faudra soit mapper les
mots-clés EN existants vers ces slugs de catégorie plutôt que vers un terme de recherche
libre, soit trouver le vrai mécanisme de recherche du site (pas encore identifié). À refaire
avant que ce scraper retourne de vraies données, même une fois connecté.
