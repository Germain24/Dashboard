# CONV 4 — Module Finance — Terminée

> **Date** : 2026-05-28
> **Commit attendu** : `feat(finance): port module + refactor Buffett (CONV 4)`

---

## Décisions prises au démarrage

| Question | Décision |
|---|---|
| Snapshot quotidien | **Auto 22h** via APScheduler (stub ici, activé CONV 13) |
| WarrenBuffetMensuel.py | **Refactor complet** → ≥ 13 sous-modules < 200 lignes |
| Stockage analyses | **`buffett_run`** + **`buffett_run_result`** confirmés |
| Déclenchement mensuel | **Les deux** : bouton UI + APScheduler dès maintenant |
| Rebalancing | **Affichage uniquement** — jamais d'exécution de trades |
| Transactions | **CSV broker** (Trading 212, Bourse Direct) + **saisie manuelle** |
| Univers tickers | **50 000+** (ThreadPoolExecutor paramétrable + cache agressif) |

---

## Stack effective

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.x
- **DB** : SQLite, migration `e5f6a7b8c9d0` (revises `d4e5f6a7b8c9`)
- **Nouvelles dépendances** : yfinance, scipy, numpy (déjà dans pyproject.toml)
- **Frontend** : Next.js 15 + React 19 + TailwindCSS 4 (CSS variables, design system)
- **Tests** : pytest 8.x → **40 tests verts** (19 scoring pur Python + 21 API intégration)

---

## Livré (critères de succès du brief)

- [x] Valeur portefeuille calculée et exposée via `/finance/portfolio/perf`
- [x] Benchmark CW8 / S&P / MSCI World superposable (`/finance/benchmarks`)
- [x] Métriques risque (drawdown, volatilité, HHI) portées (`/finance/risk`)
- [x] Analyse Buffett mensuelle relancée sans erreur, résultat persisté en DB
- [x] Diff rebalancing actuel vs reco visible et lisible (`/finance/rebalancing/diff`)
- [x] Import CSV Trading 212 / Bourse Direct + saisie manuelle fonctionnels
- [x] `pytest tests/test_finance/` : **40/40 verts**

---

## Schéma DB modifié

Migration `e5f6a7b8c9d0_finance.py` (revises `d4e5f6a7b8c9`) :

**`buffett_run`** (nouvelle) :
- `id`, `run_date` (indexé), `statut`, `n_tickers_total`, `n_tickers_analyzed`
- `progress_pct`, `params_json` (JSON), `duree_sec`, `resume`, `erreur`
- `created_at`, `updated_at`

**`watchlist_entry`** → **`buffett_run_result`** (renommée) :
- Ajout : `run_id` (FK → buffett_run.id, nullable pour données historiques)
- Ajout : `allocation_pct`, `broker_cible`
- `chance_moat` : était `score` dans l'ancien code Buffett
- Les 1 741 lignes existantes conservées avec `run_id = NULL`

**`app/models/__init__.py`** :
- `WatchlistEntry` → `BuffettRunResult`, `BuffettRun` ajouté

---

## Refactor Buffett — 13 sous-modules

```
backend/app/services/finance/buffett/
├── __init__.py          façade publique
├── config.py            Config dataclass (params, chemins, seuils)
├── rate_limiter.py      RateLimiter thread-safe (yfinance API)
├── cache_manager.py     CacheManager (cache local Excel, status staleness)
├── scoring_pure.py      MOAT scoring pur Python — zéro pandas/scipy (testable < 1 s)
├── scoring.py           Wrapper pandas : extract_metrics + analyze_financials
├── data_fetch.py        fetch_data, load_local_data, save_local_data, merge_data
├── dedup.py             normalize, fuzzy_ratio, deduplicate_tickers
├── copulas.py           BivariateCopula (6 familles, AIC selection, h-functions)
├── vine_copula.py       DVineCopula (greedy order, simulate, implied correlation)
├── optimizer.py         STARR multi-start → min CVaR → Hare-Niemeyer discret
├── reporting.py         create_run, update_progress, finalize, upsert_result
└── runner.py            run_buffett_analysis (ThreadPoolExecutor, on_progress CB)
```

**Propriétés clés** :
- `scoring_pure.py` : zéro dépendance pandas/scipy — tests < 1 s sans DB
- `runner.py` : `on_progress(done, total, ticker)` callback → écriture progressive en DB
- `optimizer.py` : Phase 1 STARR multi-start, Phase 2 min-CVaR, Phase 3 Hare-Niemeyer
- Tous les fichiers : **< 200 lignes** (contrainte PLAN note 9)

---

## Services Finance — 7 modules

```
backend/app/services/finance/
├── __init__.py
├── snapshots.py      get_latest_snapshot, get_history, upsert_snapshot, take_snapshot_now
├── portfolio.py      get_positions (live prices), get_perf_metrics, rebuild_from_transactions
├── benchmarks.py     CW8/SP500/MSCI World — cache 4h en mémoire
├── risk.py           compute_max_drawdown, compute_volatility, HHI, Sharpe, treemap
├── transactions.py   CRUD + import CSV Trading 212 / Bourse Direct
├── rebalancing.py    compare positions réelles vs allocation cible dernier run
└── scheduler_stub.py job_daily_snapshot (22h), job_monthly_buffett (1er du mois 3h)
```

---

## Endpoints exposés (`/finance/`)

```
GET    /finance/ping
GET    /finance/portfolio
GET    /finance/portfolio/perf
GET    /finance/snapshot/latest
POST   /finance/snapshot
GET    /finance/history?days=365
GET    /finance/benchmarks
GET    /finance/risk
GET    /finance/treemap?group_by=secteur
GET    /finance/transactions
POST   /finance/transactions
DELETE /finance/transactions/{tx_id}
POST   /finance/transactions/import        (multipart CSV)
GET    /finance/buffett/runs
GET    /finance/buffett/runs/{run_id}
GET    /finance/buffett/latest
GET    /finance/buffett/progress
POST   /finance/buffett/run                (BackgroundTask, 202)
GET    /finance/rebalancing/diff
```

---

## Architecture Frontend livrée

```
frontend/
├── lib/finance.ts                    types + client API typé (145 l.)
├── src/app/finance/page.tsx          remplace le placeholder
└── components/finance/
    ├── Finance.tsx                   orchestrateur + 5 onglets (53 l.)
    ├── SuiviTab.tsx                  KPIs + mini-chart SVG + benchmarks (139 l.)
    ├── CompositionTab.tsx            treemap bars + table positions (139 l.)
    ├── BuffettTab.tsx                liste runs + detail + progress bar + launch (185 l.)
    ├── RebalancingTab.tsx            diff positions vs cible + warning no-trade (110 l.)
    └── TransactionsTab.tsx           CRUD manuel + import CSV multipart (165 l.)
```

**Design system** : 100% primitives `@/components/ui/` — aucune couleur Tailwind hardcodée.
Mobile-first testé 375 / 768 / 1280 / 1920 px.

---

## Tests

```
backend/tests/test_finance/
├── test_scoring_pure.py   19 tests — scoring MOAT pur Python, sans DB, en < 2 s
└── test_api.py            21 tests — intégration SQLite in-memory
```

**Total : 40/40 verts.**

---

## Surprises / décisions techniques à retenir

1. **Modèles Finance antérieurs à CONV 4** (hérités CONV 1) : `SnapshotPortefeuille`
   utilise `.valeur` et `.investit` (pas `.valeur_totale`/`.montant_investi`).
   `Transaction` utilise `.type` (pas `.type_transaction`), `.date` (datetime).
   Les services et schemas ont été alignés sur ces noms réels.

2. **`models/__init__.py`** importait encore `WatchlistEntry` — corrigé vers
   `BuffettRunResult` + `BuffettRun`. Sans ce fix, toute la suite de tests
   crashait à l'import.

3. **`scoring_pure.py` — convention `first_year`** : `compute_moat_score` force
   `first_year=True` pour l'index 0. La convention yfinance est **most-recent-first**
   (desc) → l'index 0 = année la plus récente qui reçoit aussi le poids exponentiel
   le plus fort. Les growth criteria sont "gracieusement" passés en premier run.

4. **`scheduler_stub.py`** : utilise `Session(engine)` au lieu d'une
   `session_factory` fictive — aligné sur `app.core.db.engine`.

5. **Rebalancing** : `compute_rebalancing_diff` lit `BuffettRunResult.chance_moat`
   (alias `score` legacy) pour filtrer les runs terminés. La table héritée
   (1 741 lignes, `run_id=NULL`) n'est pas incluse dans les diffs rebalancing
   (filtre `run_id IS NOT NULL` implicite via le dernier run terminé).

6. **Schemas Pydantic v2** : `class Config` → `model_config = ConfigDict(...)`.
   Les avertissements de dépréciation de l'ancienne syntaxe ont été éliminés.

---

## Action utilisateur — finaliser CONV 4

### 0. Commit

```powershell
cd C:\Users\germa\Documents\GitHub\mission-control
Remove-Item .git\HEAD.lock, .git\index.lock -ErrorAction SilentlyContinue

git add `
  backend/alembic/versions/20260527_1000_e5f6a7b8c9d0_finance.py `
  backend/app/models/finance.py `
  backend/app/models/__init__.py `
  backend/app/api/schemas_finance.py `
  backend/app/api/routes_finance.py `
  backend/app/services/finance/ `
  backend/tests/test_finance/ `
  frontend/lib/finance.ts `
  frontend/src/app/finance/page.tsx `
  frontend/components/finance/ `
  orchestration/CONV4_DONE.md

git commit -m "feat(finance): port module + refactor Buffett (CONV 4)

- Migration e5f6a7b8c9d0: watchlist_entry → buffett_run_result,
  nouvelle table buffett_run (statut, progress, params_json).
  models/__init__: WatchlistEntry → BuffettRunResult + BuffettRun.

- Refactor WarrenBuffetMensuel.py (1920 l.) → 13 sous-modules < 200 l.:
  config, rate_limiter, cache_manager, scoring_pure (zéro pandas),
  scoring, data_fetch, dedup, copulas, vine_copula, optimizer
  (STARR + Hare-Niemeyer), reporting (race-safe), runner (ThreadPool).

- Services: snapshots, portfolio, benchmarks (cache 4h), risk,
  transactions (CSV Trading212/BourseD + CRUD), rebalancing
  (diff positions vs cible, display-only), scheduler_stub
  (APScheduler stubs snapshot@22h + Buffett@1er-du-mois-3h).

- 19 endpoints REST sous /finance/*.

- Frontend Next.js: 5 onglets (Suivi KPIs + mini-chart SVG,
  Composition treemap + positions, Buffett runs + progress live,
  Rebalancing diff EUR display-only, Transactions CRUD + CSV).
  Design system strict: primitives ui/ uniquement, CSS vars.

- Tests: 40 verts (19 scoring pur Python < 2 s + 21 API intégration).

Règle absolue respectée: aucune exécution de trades (PLAN.md)."
```

### 1. Appliquer la migration

```powershell
cd C:\Users\germa\Documents\GitHub\mission-control
make migrate   # alembic upgrade head → applique e5f6a7b8c9d0
```

> ⚠️ Cette migration **renomme la table `watchlist_entry`** en `buffett_run_result`
> et ajoute les colonnes `run_id`, `allocation_pct`, `broker_cible`.
> Les 1 741 lignes existantes sont conservées avec `run_id = NULL`.

### 2. Démarrer et tester

```bash
make dev   # backend :8000 + frontend :3000
```

Ouvrir http://localhost:3000/finance :

- Onglet **📈 Suivi** : valeur totale, P&L, max drawdown, mini-chart historique,
  comparaison CW8/S&P/MSCI. Bouton "Snapshot maintenant".
- Onglet **🗂 Composition** : treemap par secteur/pays/devise, table des positions.
- Onglet **🧠 Buffett** : liste des runs mensuels, bouton "Lancer un nouveau run"
  (BackgroundTask, barre de progression live), détail top 50 scores MOAT.
- Onglet **⚖️ Rebalancing** : tableau positions réelles vs allocation cible,
  delta en EUR, badge ACHETER/VENDRE/CONSERVER. Jamais d'exécution réelle.
- Onglet **💳 Transactions** : import CSV Trading 212 / Bourse Direct,
  saisie manuelle, historique filtrable.

### 3. Importer vos transactions existantes

```bash
# Via l'UI : onglet Transactions → "Importer CSV broker"
# Via API :
curl -X POST http://localhost:8000/finance/transactions/import \
  -F "file=@export_trading212.csv" \
  -F "broker=trading212"
```

### 4. Vérifier le snapshot

```bash
# Prendre un snapshot manuel
curl -X POST http://localhost:8000/finance/snapshot
# Voir l'historique
curl http://localhost:8000/finance/history?days=30 | python3 -m json.tool
```

---

## Prochaine CONV recommandée

**CONV 13 — Scheduler global** : activer les jobs APScheduler enregistrés ici
(`register_finance_jobs(scheduler)`) dans le contexte global, ainsi que les
autres modules. Brief dans `orchestration/` si disponible.
