# Suivis — Comparaison prix Super C / Adonis

Statut : à faire · Créé le 2026-07-06, mis à jour le 2026-07-07
Suite de : `orchestration/finis/2026-07-06-lufa-superc-comparaison-prix-{design,plan}.md`
(feature livrée, 10 commits `1058fe2..9c37540` sur `main`)

Gaps connus laissés par la livraison initiale, à traiter séparément.

## 0. Lufa retiré (2026-07-07, décision user)

Impossible de créer un compte Lufa sans passer une commande — le user ne veut pas être
forcé d'acheter juste pour permettre le scraping. **Lufa a donc été entièrement retiré** :
`frontend/.lufa_scrape.mjs` supprimé, `frontend/.lufa_profile/` supprimé, entrée `.gitignore`
retirée, `store_pricing.py`/`store_categories.py` nettoyés. Les catégories qui comparaient
contre Lufa (`viande_noble`, `fruits_legumes` hors exception patate douce/oignon) retombent
maintenant sur Adonis seul, sans comparaison (voir point 1 ci-dessous pour la limite que ça
implique). Les points 2 et 5 de la version précédente de ce fichier (connexion manuelle Lufa,
mauvais pattern d'URL du scraper) sont donc **caducs**, retirés.

## 1. Scraper circulaire Super C bloqué (refonte nécessaire)

`frontend/.superc_flyer_scrape.mjs` retourne 0 items en conditions réelles : le contenu de
la circulaire `superc.ca/circulaire` est en fait dans un **iframe cross-origin**
(`circulaire.superc.ca`) protégé par un **reCAPTCHA**. Le tuning des sélecteurs CSS ne
suffira pas, et contourner un reCAPTCHA est explicitement hors limites (pas quelque chose que
l'assistant fera). Pistes restantes : cibler l'iframe directement si un accès légitime existe
sans passer par le CAPTCHA, ou trouver une source alternative (agrégateur type Flipp/Reebee
qui expose peut-être une API/JSON sans reCAPTCHA).

## 2. Vérification visuelle du badge non faite

Le badge magasin (`CoursesTab.tsx`) est validé par `tsc`/`eslint` (propre) et une revue de
code ligne par ligne, mais son rendu réel avec des données de recommandation authentiques
n'a jamais été confirmé en navigateur (tentative de création d'une recette de test
abandonnée — le combobox ingrédient ne coopérait pas avec l'automatisation navigateur). À
confirmer visuellement une fois un vrai plan de repas + le cache Super C peuplés.

## 3. Cache Adonis réutilisé = produce-only (impact accru sans Lufa)

Le cache Adonis (`adonis_fruits_legumes.json`, produit par `.adonis_scrape.mjs`) ne couvre
que les fruits/légumes. Sans Lufa, ça veut dire :
- `pantry`, `viande_volume`, `tofu_proteines` : comparaison Super C vs Adonis, mais le côté
  Adonis ne matchera jamais (fonctionne quand même via Super C seul, `recommend_store`
  retombe correctement dessus).
- `viande_noble` : Adonis est maintenant la SEULE source (Lufa retiré, Super C exclu par
  design). Comme Adonis n'a aucune donnée viande, cette catégorie ne produira **aucune**
  recommandation tant qu'`.adonis_scrape.mjs` n'est pas étendu au-delà des fruits/légumes.
- `fruits_legumes` (hors exception patate douce/oignon) : inchangé, Adonis fonctionne déjà
  bien ici (données réelles).

Étendre `.adonis_scrape.mjs` avec des termes de recherche EN pantry/viande/tofu (même
principe que Super C) résoudrait `viande_noble` et améliorerait les 3 autres catégories —
non cadré ici, à faire si souhaité.
