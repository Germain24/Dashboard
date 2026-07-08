# Progression live de l'optimisation de portefeuille Buffett (phase DE)

Statut : à faire · Créé le 2026-07-07

## Contexte

Le run automatique Buffett (`job_monthly_buffett` → `runner.py`) a deux phases :
1. **Scoring des tickers** (yfinance, rate-limité) — a une barre de progression (`/finance/buffett/progress`, `progress_pct` 0→100).
2. **Optimisation du portefeuille** (Differential Evolution multi-seed + Monte-Carlo/copule de
   Vine, `optimizer.py::optimize_portfolio_de`) — peut prendre des heures (10 seeds × jusqu'à
   2000 générations, ~144s/seed en pratique) et **n'affiche rien** pendant tout ce temps.

Un module de progression (`optimization_progress.py`, barre génération/convergence) existe déjà
mais n'est câblé que sur le bouton manuel « Créer le portefeuille optimal »
(`POST /finance/portfolio/create`), pas sur le run automatique — qui est justement celui qui
dure des heures.

**Bug découvert en creusant la question du user** : `BuffettRunResult` est une ligne par
*ticker* (pas par run), réutilisée entre runs via upsert par ticker (`reporting.py::
upsert_result`, `WHERE ticker == ticker` sans filtre `run_id`). Le `run_id` d'une ligne est donc
réassigné au run courant dès qu'un ticker est re-scoré, **avant** que l'allocation du nouveau
run soit calculée. Résultat : l'écran « run en cours » affiche en fait l'`allocation_pct` laissée
par le run précédent, ré-étiquetée comme si elle appartenait au run en cours — trompeur.

## Objectif

1. Barre de progression (génération / convergence) visible pendant la phase DE du run
   automatique, comme celle qui existe déjà pour le bouton manuel.
2. Le portefeuille affiché pour un run en cours reflète le **meilleur trouvé jusqu'ici, toutes
   seeds DE confondues**, avec le détail complet (actions/pies par broker), mis à jour à chaque
   nouveau meilleur — pas une donnée périmée du run précédent.
3. Cette donnée est persistée en base (survit à un refresh de page), pas seulement en mémoire.
4. Corollaire : plus besoin de rester sur la page pour que l'analyse avance — elle tourne déjà
   en tâche de fond côté serveur ; on rend simplement visible où elle en est à tout moment.

## Architecture

### 1. `optimizer.py` — `optimize_portfolio_de`

- Extraire la conversion « vecteur DE brut `x` → matrice d'allocation par broker `W` »
  (clip ≥0, normalisation simplexe, `project_lookthrough_hard`, remap vers la liste complète
  des tickers, `split_budget_to_brokers`) dans une fonction interne réutilisée pour :
  - le résultat final (comportement inchangé, même sortie qu'aujourd'hui),
  - les mises à jour progressives (nouveau).
- Nouveau paramètre optionnel `on_new_best: Callable[[np.ndarray, float], None] | None`.
- `global_best_energy` initialisé à `+inf`, **partagé entre les 10 seeds** (pas réinitialisé à
  chaque `for k in range(n_seeds)`). À chaque génération (`for _ in solver:`), si
  `solver.population_energies[0]` bat ce record global, on appelle `on_new_best(W, starr)` —
  avec un throttle **2 secondes minimum** entre deux appels (les premières générations
  s'améliorent souvent très vite, pas besoin d'écrire en base à cette fréquence).
- Appel supplémentaire après le polish Nelder-Mead final si celui-ci améliore encore le dernier
  meilleur connu.

### 2. `runner.py` — `job_monthly_buffett` (chemin du run automatique)

- Avancer le calcul de `prices = latest_prices(cd, t_opt)` et `total_cap` **avant** l'appel à
  `optimize_portfolio_de` (aujourd'hui calculés après, uniquement pour la discrétisation
  finale).
- Câbler `optimization_progress` (déjà utilisé par le bouton manuel) sur ce chemin :
  `optimization_progress.start(run_id=run_id)` avant l'optimisation,
  `progress_cb=optimization_progress.update_de`, `optimization_progress.finish()` après.
- `on_new_best(W, starr)` : `discretize_allocation(t_opt, W, active_b, prices, total_cap)` puis
  `update_allocations(session, run_id, alloc, reset=True)`. Le `reset=True` efface les valeurs
  périmées attribuées au run courant avant d'écrire les nouvelles — ce qui règle le bug de la
  section Contexte dès la première mise à jour progressive (quelques secondes après le début de
  la phase DE).
- `on_new_best` protégé par try/except (même pattern que `_report` existant) : une erreur de
  persistance ne doit jamais interrompre l'optimisation.

### 3. Backend — aucun nouvel endpoint

`GET /finance/buffett/runs/{run_id}` (existant) filtre déjà `allocation_cible` par `run_id` +
`allocation_pct is not None` → reflète automatiquement les mises à jour progressives.
`GET /finance/portfolio/progress` (existant) reflète déjà génération/convergence → le run
automatique les alimente désormais aussi. Un seul run/optimisation actif à la fois
(`is_analysis_running()`), donc pas d'ambiguïté sur quelle optimisation la barre représente.

### 4. Frontend — `BuffettTab.tsx`

Une fois le scoring des tickers à 100 % et `progress.active` toujours vrai, démarre aussi le
polling de `financeApi.portfolioProgress()` (même cadence 3s) et affiche la barre
génération/convergence (composant extrait de `BuffettActionsPanel.tsx`, réutilisé tel quel) à la
place du libellé « Analyse en cours... » → « Scoring terminé — optimisation du portefeuille en
cours... ».

### 5. Frontend — `BuffettRunDetailView.tsx`

Quand `selected.run.statut === "en_cours"` : polling de `financeApi.buffettRun(id)` toutes les
~5s pour rafraîchir `allocation_cible` en direct, bandeau « 🔄 Optimisation en cours — ce
portefeuille s'améliore en direct » au lieu de traiter les données comme définitives. Arrêt du
polling dès que `statut` passe à `"termine"`.

## Tests

- Unitaire : la fonction extraite `x → W` produit la même sortie qu'aujourd'hui pour un vecteur
  fixe donné (non-régression du résultat final).
- Unitaire : séquence d'appels `on_new_best` strictement décroissante en énergie (jamais de
  régression affichée).
- Intégration manuelle : run sur univers réduit (`STARR_DE_MAX_GENERATIONS` abaissé pour le
  test) et vérifier que la page de détail du run affiche au moins deux allocations différentes
  avant la fin.

## Hors scope

- Ne touche pas au bouton manuel « Créer le portefeuille optimal » (déjà fonctionnel).
- Ne cherche pas à rendre `BuffettRunResult` réellement versionné par run (le bug contourné ici
  est un effet de bord du modèle actuel « une ligne par ticker » ; le refonte du modèle de
  données est un chantier séparé si jugé utile).
