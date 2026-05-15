# Mission Control

Dashboard personnel local pour Germain : finance long terme (Buffett), nutrition,
garde-robe, agenda, études, entraînement, budget, cuisine, habitudes et livres.

> CONV 1 = fondation seule. Aucune fonctionnalité métier n'est implémentée ici,
> seulement la structure, la base de données et la navigation.

## Stack

- **Backend** : Python 3.11+, FastAPI, SQLModel, Alembic, SQLite, `uv`
- **Frontend** : Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui
- **Données** : SQLite dans `data/mission-control.db` (gitignored)

## Prérequis

- Python 3.11+ (uv s'occupe d'installer la bonne version au besoin)
- [uv](https://docs.astral.sh/uv/) : `pip install uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js 20+ et npm

## Installation

```bash
git clone <ce-repo> mission-control
cd mission-control
cp .env.example .env
make install
make migrate
make import      # importe les JSON/CSV/XLSX depuis data/imports/ vers SQLite
```

## Lancer en dev

```bash
make dev
```

- Backend FastAPI sur http://127.0.0.1:8000 (Swagger UI sur `/docs`)
- Frontend Next.js sur http://localhost:3000

## Architecture

```
mission-control/
├── backend/          # FastAPI + SQLModel + Alembic
│   ├── app/
│   │   ├── main.py
│   │   ├── core/     # config, db, logging
│   │   ├── models/   # tables SQLModel
│   │   ├── api/      # routers
│   │   └── services/
│   ├── alembic/      # migrations DB
│   ├── scripts/      # import_legacy, seed
│   └── tests/
├── frontend/         # Next.js 15 + shadcn/ui
│   ├── app/          # App Router (1 dossier par module)
│   ├── components/
│   └── lib/          # api client, types
├── data/             # SQLite + imports (gitignored)
├── orchestration/    # PLAN.md + briefs des CONV
└── Makefile
```

## Modules prévus (11)

Finance, Garde-robe, Santé, Agenda, Études, Entraînement, Budget, Cuisine,
Habitudes, Livres, Robot (chat agent — CONV 12). Voir `orchestration/PLAN.md`
pour le détail des conversations.

## Commandes utiles

| Commande              | Effet                                             |
|-----------------------|---------------------------------------------------|
| `make dev`            | Lance backend + frontend en parallèle             |
| `make migrate`        | Applique les migrations Alembic                   |
| `make migrate-new m=…`| Crée une migration auto à partir des modèles      |
| `make import`         | (Ré)importe les fichiers legacy dans SQLite       |
| `make test`           | Lance pytest (back) + tests front si présents     |
| `make gen-types`      | Régénère les types TS depuis l'OpenAPI            |

## Avancement

Voir `orchestration/PLAN.md` — chaque CONV ajoute un module.
