# Mission Control — Plan d'orchestration

> **Document de référence.** Ce fichier décrit l'état du projet, la stack cible,
> et le découpage en conversations indépendantes. À copier-coller au début de
> chaque nouvelle conversation, ou à référencer via son chemin absolu.

## Vision

Créer un robot personnel qui tourne en local sur le PC de Germain : dashboard
de vie pour suivre finance long terme (Warren Buffett, rebalance trimestriel),
nutrition (prise de muscle), garde-robe, agenda, études, entraînement, budget,
cuisine, habitudes et livres. Accessible via un site web (local + accès distant
sécurisé). Agent IA conversationnel intégré.

## Stack cible (décisions prises 2026-05-14)

- **Backend** : Python + FastAPI + SQLModel + Alembic (migrations)
- **DB** : SQLite (locale, fichier `data/mission-control.db`)
- **Frontend** : Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Agent IA** : Anthropic Claude API (tool calling natif), abstraction pour
  permettre Ollama en local plus tard
- **Scheduler** : APScheduler intégré au backend FastAPI
- **Auth** : Tailscale pour l'accès distant (V1), NextAuth.js si besoin
  d'auth applicative ultérieure
- **Tests** : pytest + Vitest/Playwright côté front
- **Repo** : nouveau repo Git `mission-control/`, sorti du clone openclaw

## État actuel (snapshot 2026-05-14)

Une app **Streamlit** monolithique (`Dashboard.py`, 1217 lignes) vit dans
`mon_espace/`, imbriquée dans un clone d'openclaw. **Tout sera réécrit** dans
la nouvelle stack — le Streamlit actuel sert de référence métier (formules,
logiques, données) mais pas de code à conserver.

| Module      | Code Streamlit existant | Migration prévue              |
|-------------|-------------------------|-------------------------------|
| Finance UI  | Mature (~600 lignes)    | CONV 4                        |
| Buffett     | Standalone (1920 lignes)| CONV 4                        |
| Habits      | Très complet (641 l.)   | CONV 2 (renommé "Garde-robe") |
| Santé       | Très complet (505 l.)   | CONV 3                        |
| Agenda      | Placeholder (18 l.)     | CONV 5                        |
| Études      | Inexistant              | CONV 6                        |
| Entraînement| Inexistant              | CONV 7                        |
| Budget      | Inexistant              | CONV 8                        |
| Cuisine     | Inexistant              | CONV 9                        |
| Habitudes   | Inexistant              | CONV 10                       |
| Livres      | Inexistant              | CONV 11                       |

## Phases & conversations

L'ordre suit les dépendances. CONV 1 doit être faite avant tout le reste.

### Phase 1 — Fondation

| #     | Titre                                          | Statut  |
|-------|------------------------------------------------|---------|
| CONV 1| Extraction + bootstrap monorepo + SQLite       | À faire |

### Phase 2 — Port des modules existants

| #     | Titre                                          | Statut  |
|-------|------------------------------------------------|---------|
| CONV 2| Module Garde-robe                              | À faire |
| CONV 3| Module Santé / Nutrition                       | À faire |
| CONV 4| Module Finance (suivi + Buffett trimestriel)   | À faire |
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
│   ├──
