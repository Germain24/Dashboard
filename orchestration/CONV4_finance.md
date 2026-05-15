# CONV 4 — Module Finance (suivi long terme + Buffett trimestriel)

## Objectif

Porter le module finance vers la nouvelle stack avec **deux usages distincts** :
- **Suivi quotidien passif** : valeur portefeuille, perf vs benchmark, drawdown
- **Revue trimestrielle Buffett** : tous les 3 mois, analyse fondamentale +
  recommandations de rebalancing via `WarrenBuffetMensuel.py`

Le rythme long terme de Germain change la priorité : pas besoin de refresh
temps réel toutes les minutes — un refresh par jour suffit pour le suivi.

## Contexte

Voir `PLAN.md`. Suppose **CONV 1 terminée** (tables `Position`, `Transaction`,
`SnapshotPortefeuille` peuplées depuis les Excel).

## Code de référence

- `mon_espace/finance/logic.py` — `get_hist`, `get_portfolio` (yfinance)
- `mon_espace/finance/WarrenBuffetMensuel.py` — 1920 lignes, optimiseur Buffett
- `mon_espace/finance/params.json` — paramètres optimiseur (PER, PEG, etc.)
- `mon_espace/finance/tickers.csv` — univers d'actions screenées
- `mon_espace/Dashboard.py` lignes 158-403 — UI Streamlit

## Décisions à prendre

1. **Fréquence de refresh** : 1×/jour à 6h ? Toutes les heures pendant les
   heures ouvrées ? Manuel uniquement ?
2. **WarrenBuffetMensuel.py** :
   - On le **refactor** en modules propres (`rate_limiter`, `scoring`,
     `optimizer`, `reporting`) — recommandé.
   - Ou on l'importe quasi tel quel et on l'enveloppe d'une API ?
3. **Rythme Buffett** : auto-trigger 1er du trimestre (CONV 13), ou bouton
   manuel uniquement ?
4. **Diff vs portefeuille** : affichage des deltas suggérés (acheter X, vendre
   Y) avec montants exacts en EUR ?
5. **Transactions** : import depuis CSV broker, ou saisie manuelle ?

## Fonctionnalités

### Backend (`backend/app/services/finance/`)

- `portfolio.py` : valeur actuelle, snapshot quotidien, perf par période
- `benchmarks.py` : CW8, S&P 500, MSCI World — calcul perf comparée
- `risk.py` : volatilité, max drawdown, HHI ajusté, corrélations
- `buffett/` (refactor du script monolithique) :
  - `config.py`, `rate_limiter.py`, `data_fetch.py`, `scoring.py`,
    `copulas.py`, `optimizer.py`, `reporting.py`
- `analysis_runner.py` : orchestre une analyse complète, persiste en DB

### Endpoints

```
GET    /api/finance/portfolio           # positions actuelles
GET    /api/finance/snapshot/latest     # dernière valeur
GET    /api/finance/history             # série temporelle valeur + investi
GET    /api/finance/benchmarks          # CW8, S&P, MSCI World perf comparées
GET    /api/finance/risk                # diversification, drawdown, vol
GET    /api/finance/treemap             # data pour treemap secteurs/pays
POST   /api/finance/buffett/run         # lancer analyse Buffett
GET    /api/finance/buffett/latest      # dernière analyse
GET    /api/finance/buffett/history     # historique trimestres
GET    /api/finance/buffett/diff        # diff actuel vs reco
POST   /api/finance/transactions        # ajouter transaction
GET    /api/finance/transactions        # historique
```

### Frontend (`frontend/app/finance/`)

- Onglet **Suivi** : valeur + graph + benchmark + risque (vu aujourd'hui)
- Onglet **Composition** : treemap secteurs / pays / devises
- Onglet **Buffett** : dernières recos, diff actuel vs cible, bouton "Relancer"
- Onglet **Transactions** : historique, P&L réalisé, import CSV

## Hors-scope

- **Exécution réelle de trades** (jamais — règle absolue PLAN.md)
- Notifications push d'alertes prix (CONV 13 si voulu)
- Trading day-trading / court terme

## Dépendances

- Prérequis : CONV 1.
- Synergique : CONV 13 (scheduler) pour relance auto trimestrielle.

## Suggestions techniques

- Refactor Buffett : commencer par découper le fichier en gros morceaux
  thématiques, garder la logique identique au début, tester avant chaque coupe.
- Snapshot quotidien : un job APScheduler stocke la valeur du portefeuille
  chaque soir → tu reconstruis la courbe sans dépendre des Excel.
- Lancer Buffett en `BackgroundTasks` FastAPI (peut prendre 30 min).

## Critères de succès

- [ ] Valeur portefeuille calculée correctement vs Streamlit
- [ ] Benchmark CW8 superposable
- [ ] Toutes les métriques (HHI, drawdown, corrélation) portées
- [ ] Analyse Buffett relancée sans erreur, résultat persisté en DB
- [ ] Diff actuel vs reco visible et lisible
- [ ] Import d'une transaction CSV broker fonctionne

---

## Prompt d'amorce

```
Je veux porter le module Finance de Mission Control. Lis :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV4_finance.md
3. Logique de référence :
   - C:\Users\germa\Documents\GitHub\openclaw\mon_espace\finance\logic.py
   - C:\Users\germa\Documents\GitHub\openclaw\mon_espace\finance\WarrenBuffetMensuel.py

Pose-moi les 5 questions de "Décisions à prendre" avant d'attaquer.
```
