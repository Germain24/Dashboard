# Mission Control — Plan d'orchestration

> **Document de référence.** Ce fichier décrit l'état du projet, la stack cible,
> et le découpage en conversations indépendantes. À copier-coller au début de
> chaque nouvelle conversation, ou à référencer via son chemin absolu.

## Vision

Créer un robot personnel qui tourne en local sur le PC de Germain : dashboard
de vie pour suivre finance long terme (analyse Buffett mensuelle, rebalancing
trimestriel manuel), nutrition (prise de muscle), garde-robe, agenda, études,
entraînement, budget, cuisine, habitudes et livres. Accessible via un site
web (local + accès distant sécurisé). Agent IA conversationnel intégré.

## Stack effective (post-CONV 1)

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13
- **Python** : ≥ 3.10, gestionnaire `uv`
- **DB** : SQLite (`data/mission-control.db`)
- **Frontend** : Next.js 15.5 + React 19.1 + TailwindCSS 4 + TypeScript 5
- **UI** : style shadcn/ui (composants maison + CSS variables)
- **Imports xlsx** : `python-calamine` (tolérant aux fichiers corrompus)
- **Agent IA** : Anthropic Claude API (tool calling natif), abstraction pour
  permettre Ollama en local plus tard
- **Scheduler** : APScheduler intégré au backend FastAPI
- **Auth** : Tailscale pour l'accès distant (V1), NextAuth.js si besoin
  d'auth applicative ultérieure
- **Tests** : pytest + Vitest/Playwright côté front

## État actuel (snapshot 2026-05-14, post CONV 1)

Repo `mission-control/` opérationnel. Fondation FastAPI + Next.js + SQLite en
place, 17 tables créées, 4 098 lignes legacy importées. `make dev` répond, les
11 pages des modules sont routées (vides). Voir `CONV1_DONE.md` pour les
détails.

Le code Streamlit historique reste disponible en lecture seule dans
`openclaw/mon_espace/` (à garder pendant la phase 2 comme référence métier
pour les portages, puis suppressible).

| Module      | Code Streamlit (référence) | DB peuplée par CONV 1                                       | Migration |
|-------------|-----------------------------|-------------------------------------------------------------|-----------|
| Finance     | UI mature + Buffett 1920 l. | `snapshot_portefeuille` (2246), `watchlist_entry` (1741)    | CONV 4    |
| Garde-robe  | 641 lignes                  | `vetement` (23), `tenue_history` (1)                        | CONV 2    |
| Santé       | 505 lignes                  | `mesure_sante` (9), `plan_nutrition` (10), `aliment` (68)   | CONV 3    |
| Agenda      | Placeholder (18 l.)         | tables vides                                                | CONV 5    |
| Études      | Inexistant                  | tables vides                                                | CONV 6    |
| Entraînement| Inexistant                  | tables vides                                                | CONV 7    |
| Budget      | Inexistant                  | tables vides                                                | CONV 8    |
| Cuisine     | Inexistant                  | tables vides                                                | CONV 9    |
| Habitudes   | Inexistant                  | tables vides                                                | CONV 10   |
| Livres      | Inexistant                  | tables vides                                                | CONV 11   |

## Phases & conversations

L'ordre suit les dépendances. CONV 1 doit être faite avant tout le reste.

### Phase 1 — Fondation

| #     | Titre                                          | Statut                       |
|-------|------------------------------------------------|------------------------------|
| CONV 1| Extraction + bootstrap monorepo + SQLite       | **✅ Terminée 2026-05-14**   |

### Phase 2 — Port des modules existants

| #     | Titre                                          | Statut  |
|-------|------------------------------------------------|---------|
| CONV 2| Module Garde-robe                              | À faire |
| CONV 3| Module Santé / Nutrition                       | À faire |
| CONV 4| Module Finance (suivi + Buffett mensuel)       | À faire |
| CONV 5| Module Agenda (vrai)                           | À faire |
| CONV 6| Module Études                                  | À faire |

### Phase 3 — Nouveaux modules de vie

| #      | Titre                                         | Statut  |
|--------|-----------------------------------------------|---------|
| CONV 7 | Module Entraînement (sport, prise de muscle)  | À faire |
| CONV 8 | Module Budget (dépenses personnelles)         | À faire |
| CONV 9 | Module Cuisine (recettes & meal planning)     | À faire |
| CONV 10| Module Habitudes (habit tracker)              | À faire |
| CONV 11| Module Livres                                 | À faire |

### Phase 4 — Couche intelligente & infra

| #      | Titre                                         | Statut  |
|--------|-----------------------------------------------|---------|
| CONV 12| Agent IA (chat + tool calling)                | À faire |
| CONV 13| Scheduler & jobs automatiques                 | À faire |
| CONV 14| Auth & accès distant (Tailscale)              | À faire |
| CONV 15| Tests, CI, documentation                      | À faire |

Chaque conversation a son brief détaillé dans
`orchestration/CONV<N>_<slug>.md`.

## Architecture cible

```
mission-control/
├── backend/                       # FastAPI + Python
│   ├── pyproject.toml             # géré par uv
│   ├── alembic.ini
│   ├── alembic/versions/          # migrations DB
│   ├── app/
│   │   ├── main.py                # FastAPI app
│   │   ├── core/                  # config, db, deps
│   │   ├── models/                # SQLModel
│   │   ├── api/                   # routers par module
│   │   ├── services/              # logique métier
│   │   └── agent/                 # CONV 12
│   ├── jobs/                      # CONV 13
│   └── tests/
├── frontend/                      # Next.js 15
│   ├── package.json
│   ├── app/                       # App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx               # Dashboard global
│   │   ├── finance/
│   │   ├── garderobe/
│   │   ├── sante/
│   │   ├── agenda/
│   │   ├── etudes/
│   │   ├── entrainement/
│   │   ├── budget/
│   │   ├── cuisine/
│   │   ├── habitudes/
│   │   ├── livres/
│   │   └── robot/                 # chat agent
│   ├── components/                # shadcn/ui (maison)
│   └── lib/                       # API client, utils
├── data/
│   ├── mission-control.db         # SQLite
│   └── imports/                   # CSV brokers, .ics, etc.
├── orchestration/                 # ce dossier
├── docker-compose.yml             # backend + frontend dev (optionnel)
├── Makefile                       # make dev, make test...
└── README.md
```

## Notes héritées de CONV 1 (à respecter dans toutes les CONV suivantes)

1. **Pydantic 2.13 + SQLModel 0.0.38 : un champ nommé `date` clash avec
   `datetime.date`.** Workaround : `import datetime as dt` et utiliser
   `dt.date`. À respecter dans tous les modèles à venir.
2. **`python-calamine`** est le lecteur xlsx privilégié (résiste aux fichiers
   légèrement corrompus). Pas `openpyxl` par défaut.
3. **`ToutBroker.xlsx` n'est pas un journal de transactions** — c'est la
   **sortie d'une analyse Buffett précédente** (1741 actions scorées MOAT),
   importée temporairement dans la table `watchlist_entry`. La table sera
   renommée `buffett_run_result` lors de CONV 4 pour refléter sa vraie nature.
4. **Workflow Buffett — 3 cadences distinctes** :
   - `tickers.csv` = univers d'analyse (à terme tout l'univers monde,
     ~50k stocks visés).
   - `WarrenBuffetMensuel.py` = analyse fondamentale + optimisation, **tourne
     1×/mois en batch nocturne** (plusieurs heures, géré par CONV 13 scheduler).
     Sortie persistée en tables `buffett_run` + `buffett_run_result`.
   - **Rebalancing trimestriel = action humaine** : Germain compare son
     portefeuille réel à la dernière allocation cible, décide quoi acheter/
     vendre. CONV 4 fournit le diff visuel, jamais d'exécution automatique.
5. **Snapshot portefeuille quotidien** : ce job (CONV 13) est ce qui va
   alimenter `snapshot_portefeuille` après l'import initial — il faut donc
   l'activer avant que les données ne deviennent stales.
6. **Code legacy de référence** : tant que les CONV 2 à 6 ne sont pas faites,
   garder `openclaw/mon_espace/{habits,sante,finance,agenda}/` accessible
   en lecture seule. Une fois la Phase 2 complète, suppression OK.
7. **Schéma DB de CONV 1** : 17 tables au total. Voir `CONV1_DONE.md` pour
   le détail. Les tables vides seront peuplées par les CONV correspondantes.

## Règles transverses

1. **Données réelles jamais commitées.** `data/` est gitignored sauf
   `data/imports/.gitkeep`. Sauvegardes via SQLite backup file (CONV 13).
2. **Schémas SQLModel = source de vérité.** Toute donnée passe par SQLModel.
   Plus de JSON brut éparpillé.
3. **API contract first.** Endpoints FastAPI documentés via OpenAPI auto-gen,
   le frontend Next.js génère son client TypeScript depuis ce schéma.
4. **Pas de logique métier dans Next.js.** Le frontend appelle l'API et
   affiche. Toute optimisation, calcul, validation = backend.
5. **Pas de secrets en clair.** `.env` gitignored, exemple dans `.env.example`.
6. **Timezone unique** : `America/Montreal`. Locale unique : `fr-CA`. Définies
   dans `core/config.py`.
7. **Versions pinnées.** `pyproject.toml` pour Python, lockfile à jour côté
   front.
8. **Tests obligatoires sur la logique critique** : calculs nutrition, scoring
   Buffett, score thermique garde-robe, optimiseur. Front : tests E2E sur les
   flows critiques.

## Comment je travaille (orchestrateur)

Cette conversation **ne touche pas au code**. Mon rôle :

- Maintenir ce PLAN.md à jour quand l'une des CONV se termine.
- Mettre à jour le statut dans les tables de phases.
- Rédiger / ajuster les briefs des CONV.
- Arbitrer les décisions transverses qui touchent plusieurs modules.
- Reformuler en prompt clair tout ce que tu veux confier à une autre conversation.

Pour me notifier qu'une CONV est terminée, copie-moi le récap final de l'autre
Claude (ou uploade le fichier `CONVN_DONE.md`) et je mets à jour ce document.
