# Restructuration modulaire (feature-sliced) du dépôt

**Date :** 2026-06-27
**Statut :** Design validé (en attente de relecture finale avant plan d'implémentation)

## Contexte & objectif

Le dépôt est aujourd'hui **organisé par couche** : `backend/` (une app FastAPI :
`api/`, `services/`, `models/`, `repositories/`, `core/`, chacun découpé par
domaine) et `frontend/` (une app Next.js : `src/app/` pour les routes,
`components/`, `lib/` par domaine), plus `data/` à la racine et `orchestration/`.

Objectif : passer à une organisation **par feature (module)** pour pouvoir
travailler chaque sous-module isolément — tout son code (front + back + data) au
même endroit. **But = ergonomie/colocation**, pas des modules déployables
séparément : on garde **une seule app Next + une seule app FastAPI** dessous,
câblées par alias d'import (front) et auto-enregistrement des routers (back).

## Décisions validées (brainstorming)

| Décision | Choix |
|---|---|
| Nature | Colocation, **app unique** (1 Next + 1 FastAPI), pas de services séparés |
| Migration | **Big-bang** (tout d'un coup, sur une branche, derrière un gate de vérif) |
| Taxonomie | **Nouveau jeu de 7 catégories** (voir ci-dessous) |
| Racine | wrapper **`modules/`** + dossier **`shell/`** (glue d'app) |
| Granularité | **sous-module = domaine backend cohérent** ; peut exposer plusieurs pages front ; pages agrégatrices dans leur catégorie d'UX |
| Noms de dossiers | **slugs ASCII** (les noms d'affichage avec accents/« & » restent dans `lib/modules.ts`) |
| Import root Python | racine du dépôt : `shell.backend.*` et `modules.<cat>.<sous>.backend.*` ; `uvicorn shell.backend.main:app` |
| Data | scoping par portée (multi-catégories → `data/` ; multi-sous-modules → `modules/<cat>/data/` ; un seul → `…/<sous>/data/`) ; **la DB SQLite unique reste partagée** dans `data/` |

## Structure cible (racine)

```
mission-control/
├── shell/
│   ├── frontend/        # App Next : src/app/ (routes minces), accueil + Deck/répartition, UI partagée, config
│   └── backend/         # FastAPI : main.py, core/, auto-enregistrement des routers de modules
├── data/                # data partagée par PLUSIEURS catégories (DB SQLite, settings globaux, backups)
├── modules/
│   ├── quotidien/       # agenda + pages agrégatrices (score, journal, snapshot, vue-360, bilan)
│   ├── corps/           # entrainement, cuisine, sante, skincare
│   ├── culture/         # musique, films_series, livres, gaming
│   ├── argent/          # budget, finance, patrimoine
│   ├── travail/         # etudes, travail, objectifs
│   ├── systeme/         # documents, scheduler (jobs+routines), donnees, parametres
│   └── style_horizons/  # garderobe, langues
└── orchestration/       # inchangé (graphify, specs, plans, logs)
```

## Layout interne d'un sous-module

```
modules/<categorie>/
├── data/                       # partagée entre sous-modules de la catégorie (si besoin)
└── <sous-module>/              # nommé d'après le DOMAINE backend (ex. films_series)
    ├── backend/
    │   ├── __init__.py
    │   ├── router.py           # expose `router` (APIRouter)
    │   ├── services/           # logique métier (ancien services/<domaine>/)
    │   ├── models.py           # tables SQLModel du domaine
    │   └── repository.py       # si présent
    ├── frontend/
    │   ├── page.tsx            # (ou page_film.tsx / page_series.tsx si plusieurs routes)
    │   ├── components/
    │   └── lib.ts              # client API + types (ancien lib/<domaine>.ts, lib/queries/<domaine>.ts)
    └── data/                   # data propre à ce sous-module
```

## Mapping catégories → sous-modules (par domaine backend)

| Catégorie (dossier) | Affichage | Sous-modules (domaine backend) |
|---|---|---|
| `quotidien` | Quotidien | `agenda` ; pages agrégatrices : `journal` (domaine backend) + pages front-only `score`, `snapshot`, `vue-360`, `bilan` ; `habitudes` (domaine backend, complétion quotidienne) |
| `corps` | Corps | `entrainement`, `cuisine`, `sante` (inclut le calcul `score`), `skincare` |
| `culture` | Culture | `musique`, `films_series` (routes front `film` + `series`), `livres`, `gaming` |
| `argent` | Argent | `budget`, `finance` (Investissement), `patrimoine` |
| `travail` | Travail | `etudes`, `travail`, `objectifs` |
| `systeme` | Système | `documents`, `scheduler` (routes front `jobs` + `routines`), `donnees` (domaine backend `data`/`data_io`), `parametres` (domaine backend `settings`) |
| `style_horizons` | Style & Horizons | `garderobe`, `langues` |

### Pages agrégatrices (front lit plusieurs backends)

`score`, `vue-360`, `bilan`, `snapshot` sont des pages front qui agrègent
plusieurs domaines. Règle : **la page vit dans sa catégorie d'UX** (`quotidien`)
et importe les données via les **interfaces publiques** des modules concernés
(ex. le client API `sante` exposé par `modules/corps/sante/frontend/lib`). Le
calcul `score` (backend `sante/score.py`) reste dans `modules/corps/sante/backend`.

### Cross-cutting → `shell/backend` (PAS des modules)

`core/` (config, db, errors, logging, cache, pagination, query_params,
rate_limit, repository générique), `health`, `search`, `notifications`,
le montage du routeur agrégé, et la CORS/middleware. Côté front, l'accueil
(Deck, répartition), le layout, le Dock, la palette de commandes, les
breadcrumbs, et `lib/modules.ts` (source de vérité de la nav) vivent dans
`shell/frontend`.

## Câblage (conventions)

- **Routes Next (thin re-export).** L'`app/` unique reste dans la coquille ;
  chaque route est un ré-export :
  `shell/frontend/src/app/film/page.tsx` →
  `export { default } from '@modules/culture/films_series/frontend/page_film'`.
  Idem `loading.tsx` si besoin. Le vrai composant vit dans le module.
- **Routers FastAPI (auto-enregistrement).** Chaque
  `modules/<cat>/<sous>/backend/router.py` expose `router`.
  `shell/backend/main.py` les découvre (parcours de `modules/*/*/backend/router.py`)
  et fait `app.include_router(router)` — plus de liste manuelle. Les deux montages
  actuels (`/api/v1` versionné + racine rétro-compat) sont conservés.

## Schéma d'import (réécriture mécanique)

- **Backend Python.** Racine d'import = racine du dépôt. `__init__.py` dans
  `shell/`, `shell/backend/`, `modules/`, chaque catégorie et chaque sous-module.
  - `from app.core.X` → `from shell.backend.core.X`
  - `from app.api.<dom>` / `from app.services.<dom>` / `from app.models.<dom>`
    → `from modules.<cat>.<dom>.backend…`
  - Lancement : `uvicorn shell.backend.main:app` depuis la racine (CWD = racine).
  - `pyproject.toml` configuré pour la découverte des packages `shell` + `modules`.
- **Frontend TS.** Nouveaux alias dans `tsconfig.json` (+ `vitest.config`,
  `next.config` si besoin) :
  - `@shell/*` → `shell/frontend/*`
  - `@modules/*` → `modules/*`
  - `@/components/X` / `@/lib/X` → `@shell/components/X` ou
    `@modules/<cat>/<sous>/frontend/…` selon l'appartenance.

## Data scoping (application de la règle)

| Donnée actuelle | Portée | Destination |
|---|---|---|
| `mission-control.db` (+ `-wal`/`-shm`) | toutes catégories | `data/` |
| `app_settings.json`, `backups/` | app-wide | `data/` |
| `account_balances.json` | finance + patrimoine | `modules/argent/data/` |
| `financials_by_company/`, cache finance (`cache_status.json`) | finance | `modules/argent/finance/data/` |
| `imports/Finances/…` | finance | `modules/argent/finance/data/imports/` |
| `imports/Cuisine/…` | cuisine | `modules/corps/cuisine/data/imports/` |
| `sante_photos/` | sante | `modules/corps/sante/data/` |
| `entrainement_mesocycle.json` | entrainement | `modules/corps/entrainement/data/` |
| `garderobe_photos/` | garderobe | `modules/style_horizons/garderobe/data/` |
| `mes_livres.json` | livres | `modules/culture/livres/data/` |
| `etudes_goal.json` | etudes | `modules/travail/etudes/data/` |
| `*_reminded.json` (agenda, habitudes) | quotidien | `modules/quotidien/…/data/` |

La **DB SQLite est un fichier unique partagé** (un engine, toutes les tables) :
elle reste dans `data/`. Le scoping data porte sur les fichiers/JSON/assets, pas
sur le schéma DB. Les chemins de data sont aujourd'hui dérivés de la config
(`core/config.py`) ; la migration introduit des helpers de résolution de chemin
par module plutôt que des chemins en dur.

## Gate de vérification (rien n'est « fini » sans ça)

Après la migration, tout doit passer **vert** :
1. `tsc --noEmit` (frontend) — 0 erreur.
2. `next build` — build de prod réussi (valide la résolution des routes/alias).
3. `vitest run` — suite front (114 tests actuels) verte.
4. `pytest` — suite backend verte.
5. Boot `uvicorn shell.backend.main:app` + génération `openapi.json` sans erreur
   (valide l'auto-enregistrement des routers).
6. Re-run `graphify update .` — graphe régénéré sur la nouvelle arbo.
7. Lancement manuel (dev.ps1 / docker compose) : l'accueil charge, une page de
   chaque catégorie répond.

## Configs à mettre à jour (big-bang)

`tsconfig.json`, `next.config.ts`, `vitest.config.mts`, `playwright.config.ts`,
`components.json` (shadcn), `pyproject.toml`, `uv.lock` (si besoin),
`backend/Dockerfile` + `frontend/Dockerfile`, `docker-compose*.yml`, `Caddyfile`,
`Makefile`, `dev.ps1`, génération openapi, `alembic` (chemins/target), et les
références de chemins dans `CLAUDE.md` / `orchestration/` (graphify).

## Risques & rollback

- **Très haute churn / blast radius** : ~1462 imports backend + ~320 fichiers
  front + toutes les configs. Réécriture **scriptée et mécanique** (pas à la
  main) pour limiter les erreurs ; `git mv` pour préserver l'historique.
- **Aucune valeur fonctionnelle** ajoutée : pur réagencement. Le bénéfice est
  l'ergonomie de maintenance. Risque assumé (choix big-bang).
- **Rollback** : toute la migration sur une branche dédiée ; si le gate ne passe
  pas et n'est pas réparable raisonnablement, on abandonne la branche (l'état
  actuel reste intact sur la branche d'origine).
- **alembic / DB** : la DB et son historique de migrations ne bougent pas de
  schéma ; seuls les chemins d'import des modèles changent — vérifier
  qu'`alembic` retrouve les métadonnées (`target_metadata`).

## Hors périmètre (YAGNI)

- Tout changement fonctionnel (comportement, UI, endpoints) — migration **iso-fonctionnelle**.
- Modules déployables séparément / microservices.
- Passage Postgres/Redis, multi-process.
- Refonte de `lib/modules.ts` au-delà de l'ajout des slugs/catégories ASCII ↔ affichage.
- La finalisation de la branche Deck (`feat/ameliorations-section-e`) reste une décision séparée en attente.

## Décomposition (note)

Bien que mené en big-bang, le **plan d'implémentation** sera séquencé par phases
vérifiables : (1) échafaudage `shell/` + `modules/` + `__init__.py` + configs/alias ;
(2) déplacements `git mv` backend par catégorie + réécriture imports ; (3) idem
frontend + thin re-exports ; (4) data scoping ; (5) auto-enregistrement routers ;
(6) gate de vérification complet. Chaque phase se termine sur un état buildable
autant que possible.
