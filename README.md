# Mission Control

Dashboard personnel local : finance long terme (Buffett), santé/nutrition,
garde-robe, agenda, études, entraînement, budget, cuisine, habitudes, livres,
et skincare. Pensé pour tourner en local sur une machine, sans dépendance à une IA externe.

## Stack

- **Backend** : Python 3.11+, FastAPI, SQLModel, Alembic, SQLite, `uv`
- **Frontend** : Next.js 15 (App Router), TypeScript, Tailwind v4, shadcn/ui, TanStack Query
- **Données** : SQLite dans `data/mission-control.db` (gitignored)
- **Jobs** : APScheduler (snapshots finance, rappels agenda, sync iCal, backups…)

Détail de l'architecture : voir [ARCHITECTURE.md](ARCHITECTURE.md).

## Prérequis

- Python 3.11+ (uv installe la bonne version au besoin)
- [uv](https://docs.astral.sh/uv/) : `pip install uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 20+ et npm

## Installation

```bash
git clone <ce-repo> mission-control
cd mission-control
cp .env.example .env
make install
make migrate
make import      # importe les JSON/CSV/XLSX depuis data/imports/ vers SQLite (optionnel)
```

## Lancer en dev

```bash
make dev
```

- Backend FastAPI sur http://127.0.0.1:8000 (Swagger UI sur `/docs`)
- Frontend Next.js sur http://localhost:3000

## Lancer avec Docker

```bash
make up      # backend :8000 + frontend :3000 (docker compose up --build)
make prod    # + reverse proxy Caddy → point d'entrée unique http://localhost
make down    # arrêt
```

La base SQLite est persistée dans `./data`. En production (`make prod`), Caddy
route `/api/*` vers le backend et le reste vers le front. Le backend tourne avec
**1 worker** (caches et rate limit in-memory par process — voir
`docker-compose.prod.yml`).

## Modules livrés

| Module        | Aperçu |
|---------------|--------|
| **Finance**   | Portefeuille (cours yfinance, cache quotidien), analyse Buffett, rebalancing, risque/diversification, TWR vs benchmark, dividendes, projection, backtest |
| **Santé**     | Poids/mesures, journal alimentaire, macros cibles (TDEE), qualité nutritionnelle, hydratation, sommeil, photos de progression, plan de repas |
| **Garde-robe**| Inventaire, score thermique, suggestion de tenue selon météo, fréquence de port, photos + couleur dominante |
| **Agenda**    | Événements, récurrences, tâches, planner de cycle, conflits, **import Google Calendar (OAuth) et iCal externe (Agendrix) avec synchro auto** |
| **Études**    | Sessions, deadlines, évaluations |
| **Entraînement** | Programmes, séances, dépense calorique (pont vers Santé) |
| **Budget**    | Transactions, enveloppes, analytics |
| **Cuisine**   | Recettes, liste de courses (dérivée des cibles nutrition) |
| **Habitudes** | Suivi, rappels, complétion hebdo |
| **Livres**    | Bibliothèque, statut de lecture |
| **Skincare**  | Routine du jour |

## Configuration (`.env`)

Tout est optionnel — les modules dégradent proprement si non configurés. Voir
[.env.example](.env.example). Principaux réglages :

- `GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN` — Google Calendar (OAuth ; le refresh
  token s'obtient via `backend/scripts/google_oauth_setup.py`).
- `ICAL_SYNC_URLS` — calendriers iCal externes re-synchronisés toutes les 6h (ex. Agendrix).
- `CORS_ORIGINS/METHODS/HEADERS` — origines/méthodes/en-têtes autorisés (pas de wildcard).

## Sécurité (local)

- CORS restreint (origines/méthodes/en-têtes explicites).
- En-têtes de sécurité front (CSP `frame-ancestors 'none'`, X-Frame-Options, nosniff…).
- Rate limiting sur les routes coûteuses (analyses finance) → 429.

## Commandes utiles

| Commande              | Effet                                             |
|-----------------------|---------------------------------------------------|
| `make dev`            | Lance backend + frontend en parallèle             |
| `make migrate`        | Applique les migrations Alembic                   |
| `make migrate-new m=…`| Crée une migration auto à partir des modèles      |
| `make import`         | (Ré)importe les fichiers legacy dans SQLite       |
| `make test`           | pytest (back) + vitest (front)                    |
| `make gen-types`      | Régénère les types TS depuis l'OpenAPI            |
| `make hooks`          | Installe les hooks pre-commit (ruff-format + prettier) |
| `make wait-health`    | Attend que `/health` réponde (post-démarrage)     |
| `make lint` / `fmt`   | Lint / formate back + front                       |

## Tests & CI

- Backend : `cd backend && uv run pytest`
- Frontend : `cd frontend && npm test` (vitest), `npx tsc --noEmit`, `npm run build`
- CI GitHub Actions (`.github/workflows/ci.yml`) : lint (advisory) + tests + build à chaque push.

## Avancement

`orchestration/PLAN.md` (conversations de build) et `orchestration/AMELIORATIONS_200.txt`
(améliorations incrémentales).
