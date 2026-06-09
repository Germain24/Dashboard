# Architecture — Mission Control

Vue d'ensemble technique du dashboard. Pour l'usage, voir [README.md](README.md).

## 1. Vue macro

```
Navigateur ──HTTP──> Next.js (App Router, :3000)
                         │  rewrites /api/* ──proxy──> FastAPI (:8000)
                         │  (client direct possible vers le backend en dev)
                         ▼
                     FastAPI ── SQLModel ── SQLite (data/mission-control.db)
                         │
                         └── APScheduler (jobs périodiques)
```

Application **mono-utilisateur, locale, mono-process**. Les choix (SQLite, caches
in-memory, rate limit in-memory) sont adaptés à ce contexte ; un passage
multi-process imposerait Redis/Postgres.

## 2. Backend (`backend/app/`)

Découpage en couches, du plus externe au plus interne :

```
api/        Routers FastAPI (HTTP, validation, codes d'erreur)
services/   Logique métier pure et orchestrations (1 sous-dossier par domaine)
repositories/  Accès données découplé (app/core/repository.py générique)
models/     Tables SQLModel
core/       Briques transverses
```

### `core/` — briques transverses

| Fichier            | Rôle |
|--------------------|------|
| `config.py`        | `Settings` (pydantic-settings, lit `.env`) + propriétés dérivées (listes CORS, iCal…) |
| `db.py`            | Engine SQLite (WAL + busy_timeout), `get_session` |
| `errors.py`        | Handler d'exceptions global → JSON uniforme `{code, detail}` |
| `logging.py`       | Logger structuré (JSON optionnel via `LOG_FORMAT=json`) |
| `cache.py`         | `TTLCache` + `@ttl_cache` (calculs finance coûteux) |
| `pagination.py`    | `limit/offset` + en-têtes `X-Total-Count` / `Content-Range` |
| `query_params.py`  | Tri/filtre génériques réutilisables |
| `rate_limit.py`    | `SlidingWindowLimiter` + dépendance `rate_limit()` → 429 |
| `repository.py`    | Repository générique (CRUD typé) au-dessus de SQLModel |

### `api/` — routers

Montés deux fois : sous `/api/v1` (documenté, versionné) et à la racine
(rétro-compat). Le module Finance est éclaté en sous-routeurs
(`api/finance/{portfolio,risk,transactions,buffett,rebalancing}.py`) ; les autres
modules sont des `routes_<module>.py`.

Les routes coûteuses portent une dépendance `rate_limit(...)` (analyses Buffett).

### `services/` — métier

Un sous-dossier par domaine (`finance/`, `agenda/`, `sante/`, …). Règle : la
logique pure (calculs, conversions) est isolée et testée sans DB ni réseau ;
les accès externes (yfinance, Google, httpx) sont confinés et injectables.

Exemple Finance : `prices.py` (cache cours), `portfolio_state.py` (dérive l'état
du ledger), `risk.py` (HHI, treemap, diversification), `benchmarks.py` (TWR),
`buffett/` (scoring, optimisation, rate limiter sortant vers yfinance).

### Jobs planifiés (`services/scheduler/`)

`scheduler.py:register_all_jobs` enregistre les jobs APScheduler ; chaque job est
un module `jobs/<nom>.py` exposant `run(session) -> str`, exécuté via
`runner.run_job` (journalise un `JobRun`). Jobs : snapshot portefeuille,
analyse Buffett mensuelle, rappels agenda/habitudes, refresh météo, backup DB,
purge, **sync iCal externe** (`ical_sync`, toutes les 6h).

## 3. Frontend (`frontend/`)

```
src/app/        App Router — 1 dossier par module + error.tsx / not-found.tsx
                loading.tsx (skeletons) et template.tsx (transitions) par segment
components/     UI par module + composants partagés (ui/, ErrorBoundary, …)
lib/            api client, types générés, hooks, i18n, env, securityHeaders
__tests__/      Vitest + Testing Library
e2e/            Playwright (parcours clés, snapshots visuels)
```

- **Données** : TanStack Query (cache, retries, invalidation), persistance
  localStorage (offline/SWR). Le client HTTP `lib/api.ts` ajoute timeout +
  AbortController et tolère les réponses vides (204).
- **Types** : `lib/types.ts` est généré depuis l'OpenAPI (`make gen-types`).
- **Config** : `lib/env.ts` valide les variables `NEXT_PUBLIC_*` (zod), requis en prod.
- **Sécurité** : `lib/securityHeaders.ts` appliqué via `next.config.ts` `headers()`.
- **Proxy** : `next.config.ts` réécrit `/api/*` vers le backend.

## 4. Données & migrations

- SQLite unique, schéma versionné par **Alembic** (`backend/alembic/`).
- `tests/test_migrations.py` vérifie que `upgrade head` == modèles (autogenerate vide).
- Import des données legacy via `scripts/import_legacy.py`.

## 5. Déploiement

- **Dev** : `make dev` (hôte) — backend `--reload` + `next dev`.
- **Conteneurs** : `make up` (`docker-compose.yml`) — image backend (uv) + image
  frontend (build Next standalone), SQLite persistée via volume `./data`.
- **Production** : `make prod` (overlay `docker-compose.prod.yml`) — reverse proxy
  Caddy en façade (`Caddyfile`), point d'entrée unique `http://localhost`, services
  non publiés directement. Backend mono-worker (`WEB_CONCURRENCY=1`) car l'état
  (caches, rate limit) est in-memory par process ; scaler imposerait Redis/Postgres.

## 6. Conventions

- **Tests d'abord** (TDD) pour le métier ; logique pure isolée et injectable.
- Les intégrations externes dégradent proprement quand non configurées
  (Google Calendar, cours indisponibles → repli). Pas d'IA : le dashboard ne
  dépend d'aucune API de modèle de langage.
- Messages d'erreur et libellés en français (fr-CA).
- CI : lint advisory (dette suivie séparément), tests + build bloquants.
