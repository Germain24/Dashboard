# CONV 1 — Fondation : extraction + bootstrap monorepo

## Objectif

Sortir le projet du clone openclaw, créer un nouveau monorepo
`mission-control/` avec **backend FastAPI** + **frontend Next.js 15** + **SQLite**.
Migrer les données existantes (sante.json, vetements.json, tenues_history.json,
ToutBroker.xlsx, Historique_portefeuille.xlsx) vers SQLite.

**Aucune fonctionnalité n'est implémentée dans cette CONV.** L'objectif est
uniquement de poser une fondation solide, navigable, avec des pages vides
mais routables, et toutes les données existantes importées.

## Contexte

Voir `orchestration/PLAN.md` à la racine pour la vision globale, la stack
cible, l'architecture et les règles transverses.

État actuel : `mon_espace/` à l'intérieur de `C:\Users\germa\Documents\GitHub\openclaw\`.
Cible : `C:\Users\germa\Documents\GitHub\mission-control\`.

## Décisions à prendre au démarrage

1. **Git history** : repartir d'un commit initial propre, ou préserver
   l'historique via `git filter-repo` ?
2. **Gestionnaire Python** : `uv` (rapide, moderne, recommandé), `poetry`,
   ou `pip` + venv ?
3. **shadcn/ui ou autre kit UI Next.js** ? (shadcn recommandé.)
4. **Données métier sensibles** (`sante.json`, transactions broker) : importées
   en SQLite *avec* le contenu réel, ou structure vide + à remplir manuellement
   après ?
5. **Excel finance** : tu continues à travailler avec ces Excel comme source
   de vérité côté broker, ou on migre tout en SQLite et tu n'ouvres plus
   les Excel ?

## Livrable attendu

```
mission-control/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py   # tables vides pour tous les modules
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI app, CORS
│   │   ├── core/
│   │   │   ├── config.py         # settings (Pydantic), timezone, locale
│   │   │   ├── db.py             # session SQLite + SQLAlchemy
│   │   │   └── logging.py
│   │   ├── models/               # SQLModel : Garderobe, Sante, Finance...
│   │   ├── api/
│   │   │   ├── routes_health.py  # /health
│   │   │   └── __init__.py       # router prêt par module (squelettes)
│   │   └── services/             # vide pour l'instant
│   ├── scripts/
│   │   ├── import_legacy.py      # JSON & Excel → SQLite (one-shot)
│   │   └── seed_dev.py           # données de dev
│   └── tests/
│       └── test_health.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── components.json           # shadcn config
│   ├── app/
│   │   ├── layout.tsx            # nav globale, theme dark/light
│   │   ├── page.tsx              # dashboard d'accueil (cards vides)
│   │   ├── finance/page.tsx      # placeholder
│   │   ├── garderobe/page.tsx
│   │   ├── sante/page.tsx
│   │   ├── agenda/page.tsx
│   │   ├── etudes/page.tsx
│   │   ├── entrainement/page.tsx
│   │   ├── budget/page.tsx
│   │   ├── cuisine/page.tsx
│   │   ├── habitudes/page.tsx
│   │   ├── livres/page.tsx
│   │   └── robot/page.tsx
│   ├── components/
│   │   └── ui/                   # shadcn components
│   └── lib/
│       ├── api.ts                # client HTTP
│       └── types.ts              # générés depuis OpenAPI
├── data/
│   ├── mission-control.db        # créé par migration
│   └── imports/.gitkeep
├── orchestration/                # ce dossier, copié depuis l'ancien
├── docker-compose.yml            # optionnel, pour iso le dev
├── Makefile                      # make dev, make migrate, make test
├── .env.example
├── .gitignore                    # data/*.db, .env, node_modules, __pycache__
└── README.md
```

## Tâches détaillées

1. **Créer le nouveau repo Git** à `C:\Users\germa\Documents\GitHub\mission-control\`.
2. **Bootstrapper backend** :
   - `uv init backend` (ou poetry init)
   - Dépendances : `fastapi`, `uvicorn[standard]`, `sqlmodel`, `alembic`,
     `pydantic-settings`, `python-dotenv`, `pandas`, `openpyxl`, `yfinance`,
     `scipy`, `numpy`, `tzdata`, `httpx`, `pytest`, `pytest-asyncio`.
   - Configurer Alembic avec SQLModel.
3. **Modèles SQLModel initiaux** (vides en données mais schémas définis) :
   - `Vetement`, `TenueHistory` (depuis vetements.json)
   - `MesureSante`, `PlanNutrition`, `Aliment` (depuis sante.json + aliments.csv)
   - `Transaction`, `Position`, `SnapshotPortefeuille` (depuis ToutBroker.xlsx)
   - Tables vides pour Agenda, Etudes, Entrainement, Budget, Cuisine,
     Habitudes, Livres (les CONV concernées les rempliront).
4. **Script de migration `import_legacy.py`** :
   - Lit `mon_espace/habits/vetements.json` → table Vetement
   - Lit `mon_espace/sante/sante.json` → table MesureSante + PlanNutrition
   - Lit `mon_espace/sante/aliments.csv` → table Aliment
   - Lit `mon_espace/finance/Historique_portefeuille.xlsx` → SnapshotPortefeuille
   - Lit `mon_espace/finance/ToutBroker.xlsx` → Position
   - Idempotent (peut être relancé sans dupliquer).
5. **Bootstrapper frontend** :
   - `npx create-next-app@latest frontend --typescript --tailwind --app`
   - `npx shadcn@latest init`
   - Layout avec sidebar gauche : liens vers les 11 pages (incluant Robot)
   - Page d'accueil : cards vides pour chaque module
6. **Wiring API → Front** :
   - `/health` côté FastAPI
   - Page frontend qui consomme `/health` au chargement → "Backend OK"
   - Génération du client TypeScript depuis l'OpenAPI (`openapi-typescript`).
7. **Dev workflow** :
   - `make dev` lance les deux (concurrently)
   - Backend sur `:8000`, frontend sur `:3000`
8. **Suppression de `mon_espace/`** dans le repo openclaw (après vérif que
   tout est bien sorti).

## Hors-scope

- Implémenter la moindre fonctionnalité métier (autres CONV).
- Auth, agent IA, scheduler.
- Beau design (juste navigation fonctionnelle).
- Tests exhaustifs (juste `/health`).

## Dépendances

- Prérequis : aucune.
- Débloque : toutes les autres CONV.

## Suggestions techniques

- **uv** est très supérieur à pip pour ce genre de projet (rapidité, lockfile).
- **SQLModel** = SQLAlchemy + Pydantic, parfait pour FastAPI.
- **Alembic** pour les migrations dès le départ — pas plus tard.
- **openapi-typescript** pour générer un client TS depuis l'OpenAPI FastAPI.
  Évite de réécrire les types des deux côtés.
- **shadcn/ui** : copie des composants dans ton repo, zéro lock-in.
- **Concurrently** ou **turbo** pour lancer back + front en dev.

## Critères de succès

- [ ] Le repo `mission-control/` existe avec backend + frontend
- [ ] `make dev` lance les deux serveurs sans erreur
- [ ] La page d'accueil Next.js liste les 11 modules avec navigation
- [ ] Cliquer sur un module charge sa page (vide mais routée)
- [ ] La DB SQLite contient toutes les données legacy importées
- [ ] `pytest` passe (au moins le test `/health`)
- [ ] `mon_espace/` a disparu du repo openclaw
- [ ] Le README explique comment installer et lancer

---

## Prompt d'amorce (à copier en début de nouvelle conversation)

```
Je commence un nouveau projet "Mission Control" — un dashboard de vie
personnel. Avant toute action, lis ces deux fichiers pour le contexte :

1. C:\Users\germa\Documents\GitHub\openclaw\mon_espace\orchestration\PLAN.md
2. C:\Users\germa\Documents\GitHub\openclaw\mon_espace\orchestration\CONV1_fondation.md

Le second contient l'objectif précis de cette conversation : extraction du
projet vers son propre repo + bootstrap monorepo FastAPI + Next.js + SQLite,
sans aucune fonctionnalité métier.

Commence par lire ces fichiers, puis pose-moi les 5 questions de la section
"Décisions à prendre au démarrage". Une fois mes réponses obtenues, attaque
la fondation étape par étape.
```
