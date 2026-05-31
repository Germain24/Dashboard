# CONV 4 — Module Finance (suivi + analyse Buffett + rebalancing)

## Objectif

Porter le module finance vers la nouvelle stack avec **trois usages distincts
et trois cadences distinctes** :

1. **Suivi quotidien passif** (auto, ~1×/jour) : valeur portefeuille, perf
   vs benchmark, drawdown, snapshot stocké en DB.
2. **Analyse Buffett mensuelle** (auto, 1er du mois, batch nocturne) :
   `WarrenBuffetMensuel.py` lit `tickers.csv` (univers mondial à terme),
   score MOAT + optimisation sous contraintes → produit une allocation cible
   et persiste tout en DB. **Heavy compute** (potentiellement plusieurs
   heures sur ~50k tickers).
3. **Rebalancing trimestriel** (manuel, décision humaine) : tu compares ton
   portefeuille réel aux 3 dernières allocations cibles, tu décides des
   trades à faire chez ton broker. Pas d'exécution automatique.

Le rythme long terme = pas besoin de refresh prix toutes les minutes ; un
snapshot quotidien suffit pour le suivi.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée**. État SQLite après CONV 1 :
- `snapshot_portefeuille` : **2 246 lignes** (historique valeur depuis
  `Historique_portefeuille.xlsx`)
- `watchlist_entry` : **1 741 lignes** (la sortie d'une analyse Buffett
  précédente — actions scorées MOAT — pas un journal de transactions comme
  on le pensait au planning ; à renommer en `buffett_run_result`)
- `transaction` : **vide** (à remplir depuis CSV broker)
- `position` : **vide** (à reconstruire depuis les transactions)

**Implication majeure** : la structure du module Finance s'articule autour
de trois concepts distincts :
1. **Watchlist** = univers d'actions à analyser (déjà peuplé, ~1741 lignes,
   à terme tout l'univers monde via `tickers.csv` ~50k stocks)
2. **Positions / Transactions** = portefeuille réel (à importer depuis CSV
   broker)
3. **Snapshots** = valeur historique (déjà peuplé, alimenté quotidiennement
   par CONV 13)

## Code de référence

- `legacy_code/finance/logic.py` — `get_hist`, `get_portfolio` (yfinance)
- `legacy_code/finance/WarrenBuffetMensuel.py` — 1920 lignes, optimiseur Buffett
- `legacy_code/finance/params.json` — paramètres optimiseur (PER, PEG, etc.)
- `legacy_code/finance/tickers.csv` — univers d'actions screenées
- `legacy_code/Dashboard.py` lignes 158-403 — UI Streamlit

## Décisions à prendre

1. **Snapshot quotidien** : 1×/jour à 22h ? Manuel uniquement ? Pas du tout
   (on calcule à la demande) ?
2. **WarrenBuffetMensuel.py** :
   - On le **refactor** en modules propres (`rate_limiter`, `scoring`,
     `optimizer`, `reporting`) — recommandé pour pouvoir le piloter depuis
     FastAPI et tester chaque morceau.
   - Ou on l'importe quasi tel quel et on l'enveloppe d'une API ?
3. **Stockage des analyses mensuelles** : une table `buffett_run` (1 ligne =
   1 analyse, avec params + date + résumé) + `buffett_run_result` (1 ligne =
   1 ticker scoré pour cette analyse). Confirme le modèle ?
4. **Triggering de l'analyse mensuelle** : 100% automatique via scheduler
   (CONV 13, 1er de chaque mois 3h), 100% manuel via bouton "Lancer", ou
   les deux (auto + override manuel) ?
5. **Rebalancing trimestriel** : interface dédiée qui compare positions
   réelles vs allocation cible de la dernière analyse, affiche les deltas
   suggérés en EUR. Pas d'exécution réelle. OK avec ce design ?
6. **Transactions** : import depuis CSV broker (Trading 212, Bourse Direct),
   saisie manuelle, ou les deux ?
7. **Taille de `tickers.csv`** : aujourd'hui ~1741 lignes, tu vises combien
   à terme ? Si > 10k, la durée d'analyse devient critique et il faut
   peut-être paralléliser plus agressivement.

## Fonctionnalités

### Backend (`backend/app/services/finance/`)

- `portfolio.py` : valeur actuelle, snapshot quotidien, perf par période,
  positions / transactions
- `benchmarks.py` : CW8, S&P 500, MSCI World — calcul perf comparée
- `risk.py` : volatilité, max drawdown, HHI ajusté, corrélations
- `buffett/` (refactor du script monolithique) :
  - `config.py`, `rate_limiter.py`, `data_fetch.py`, `scoring.py`,
    `copulas.py`, `optimizer.py`, `reporting.py`
- `buffett/runner.py` : orchestre **une analyse complète mensuelle** —
  écrit en `buffett_run` + `buffett_run_result`, logue progression + erreurs.
  **Doit pouvoir tourner en background pendant des heures sans bloquer
  l'API.**
- `rebalancing.py` : compare positions réelles à la dernière allocation
  cible (dernier `buffett_run`), produit le diff acheter/vendre en EUR.

### Endpoints

```
GET    /api/finance/portfolio           # positions actuelles
GET    /api/finance/snapshot/latest     # dernière valeur
GET    /api/finance/history             # série temporelle valeur + investi
GET    /api/finance/benchmarks          # CW8, S&P, MSCI World perf comparées
GET    /api/finance/risk                # diversification, drawdown, vol
GET    /api/finance/treemap             # data pour treemap secteurs/pays

POST   /api/finance/buffett/run         # lancer une analyse (BackgroundTask)
GET    /api/finance/buffett/runs        # tous les runs (1 par mois)
GET    /api/finance/buffett/runs/{id}   # détail d'un run
GET    /api/finance/buffett/latest      # dernier run terminé
GET    /api/finance/buffett/progress    # progression du run en cours

GET    /api/finance/rebalancing/diff    # positions actuelles vs cible du
                                        # dernier run Buffett, en EUR
GET    /api/finance/rebalancing/history # historique des rebalancings effectués

POST   /api/finance/transactions        # ajouter transaction
GET    /api/finance/transactions        # historique
POST   /api/finance/transactions/import # CSV broker
```

### Frontend (`frontend/app/finance/`)

- Onglet **Suivi** : valeur + graph + benchmark + risque (vu aujourd'hui)
- Onglet **Composition** : treemap secteurs / pays / devises
- Onglet **Buffett** :
  - Liste des runs mensuels (date, durée, n_tickers analysés, statut)
  - Détail d'un run : top 50 par score, allocation cible recommandée
  - Bouton "Lancer un nouveau run" (avec warning : durée plusieurs heures)
  - Si un run est en cours : barre de progression live
- Onglet **Rebalancing** : tableau positions réelles vs cible dernier run,
  diff en EUR, suggestions acheter/vendre. Pas d'exécution réelle, juste
  affichage des trades à faire chez le broker.
- Onglet **Transactions** : historique, P&L réalisé, import CSV

## Hors-scope

- **Exécution réelle de trades** (jamais — règle absolue PLAN.md)
- Notifications push d'alertes prix (CONV 13 si voulu)
- Trading day-trading / court terme

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 13 (scheduler) pour relance auto mensuelle.

## Suggestions techniques

- **Refactor Buffett** : commencer par découper le fichier en gros morceaux
  thématiques, garder la logique identique au début, tester avant chaque coupe.
  Bonne occasion d'ajouter des tests unitaires sur le scoring MOAT et
  l'optimiseur.
- **Snapshot quotidien** : un job APScheduler stocke la valeur du portefeuille
  chaque soir → tu reconstruis la courbe sans dépendre des Excel.
- **Run Buffett mensuel** : lancer comme un `BackgroundTask` FastAPI avec
  écriture progressive en DB (chaque ticker scoré → ligne `buffett_run_result`
  immédiatement). Permet de voir la progression live, et de reprendre si crash.
- **Limite tickers** : si `tickers.csv` dépasse ~10k lignes, considérer un
  `ThreadPoolExecutor` plus large + cache plus agressif des `info` yfinance.
  Au-delà de 30k, envisager une alternative à yfinance (par ex. EOD Historical
  Data, payant mais ~10$/mois et plus rapide).
- **Garder l'ancien `WarrenBuffetMensuel.py` accessible** pendant le refactor :
  produire le même output bit-pour-bit que le standalone, puis seulement
  migrer.

## Critères de succès

- [ ] Valeur portefeuille calculée correctement vs Streamlit
- [ ] Benchmark CW8 superposable
- [ ] Toutes les métriques (HHI, drawdown, corrélation) portées
- [ ] Analyse Buffett mensuelle relancée sans erreur, résultat persisté en DB
- [ ] Diff rebalancing actuel vs reco visible et lisible
- [ ] Import d'une transaction CSV broker fonctionne

---

## Prompt d'amorce

```
Je veux porter le module Finance de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV4_finance.md
3. Logique de référence :
   - C:\Users\germa\Documents\GitHub\mission-control\legacy_code\finance\logic.py
   - C:\Users\germa\Documents\GitHub\mission-control\legacy_code\finance\WarrenBuffetMensuel.py

Pose-moi les 7 questions de "Décisions à prendre" avant d'attaquer.
```
