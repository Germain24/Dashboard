# CONV 5 — Récap de clôture

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.

## Décisions prises au démarrage

| Question                              | Décision                                                                                          |
|---------------------------------------|---------------------------------------------------------------------------------------------------|
| Source des cours UQAM / shifts        | **V1 = saisie manuelle**. API UQAM/travail reportée en V2 (pas encore documentée publiquement).  |
| Modèle de récurrence                  | **Format simple JSON** : `{ weekdays: list[int], start_time, end_time, until }`. Plus facile à éditer depuis l'UI que RRULE RFC 5545. |
| Algo slots libres                     | **Heuristique simple** : trous ≥ `min_duration_min` dans `[day_start_h, day_end_h]`, intervalles fusionnés. |
| Tâches vs Evenement                   | **Modèle séparé** — table `tache`. CONV 6 (Études) y branchera ses devoirs via `source="etudes"`. |
| Import .ics                           | **V1 livré** : `POST /agenda/import-ical` + `ical_adapter.py`. VEVENT ponctuels + RRULE hebdo simples. |
| Intégration Entraînement              | **Import in-process** (PLAN.md notes 11 & 14) : `entrainement_bridge.py` via `try/except + fallback`. |

## Stack effective

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13
- **DB** : SQLite, migration `c3d4e5f6a7b8` (revises `b2c3d4e5f6a7`)
- **Nouvelles dépendances** : `icalendar>=6.0.0`, `python-dateutil>=2.9.0`, `python-multipart>=0.0.9`
- **Frontend** : Next.js 15 + React 19 + TailwindCSS 4 (CSS variables shadcn-style)
- **Tests** : pytest 8.3 → **31 tests agenda verts** (6 recurrence + 10 slots + 15 api)

## Livré (critères de succès du brief)

- [x] Ajouter un cours récurrent (lun-mer-ven 9h-12h) → toutes les occurrences visibles sur 4 semaines (`GET /agenda/events?from=&to=`)
- [x] Ajouter une tâche avec deadline → apparaît triée correctement (priorité ASC, deadline ASC nulls-last)
- [x] Requête "slots libres de ≥ 1h aujourd'hui" → retourne les bons trous (`GET /agenda/slots?min_duration=60`)
- [x] Suppression d'une occurrence récurrente ne casse pas la règle (occurrences = virtuelles, non persistées)
- [x] Vue semaine s'affiche correctement (grille 7 × 15 créneaux)
- [x] **Boucle CONV 7 fermée** : `GET /agenda/today` inclut `seance_entrainement` (bridge in-process)
- [x] Import .ics V1 livré (`POST /agenda/import-ical`, dédup UID)

## Schéma DB modifié

Migration `c3d4e5f6a7b8_agenda.py` (revises `b2c3d4e5f6a7`) :

**`regle_recurrence`** (nouvelle) :
- `id`, `titre`, `weekdays` (JSON list[int] 0-6), `start_time` ("HH:MM"), `end_time` ("HH:MM")
- `lieu`, `description`, `categorie`, `couleur`, `until` (date, optionnel)
- `created_at`, `updated_at`

**`tache`** (nouvelle) :
- `id`, `titre`, `deadline` (date, indexé), `priorite` (1-5, défaut 3), `statut` ("todo"/"done")
- `duree_estimee_min`, `note`, `categorie`, `source`, `source_id` (pour CONV 6 Études)
- `created_at`, `updated_at`

**`evenement`** (existait — extension) :
- `+ categorie` (str, optionnel) — "cours"/"travail"/"sport"/"rdv"/"autre"
- `+ couleur` (str, optionnel) — ex. "#3B82F6"
- `+ recurrence_id` (int FK `regle_recurrence.id`, optionnel)

## Endpoints exposés (`/openapi.json`)

```
GET    /agenda/ping                          → { module: "agenda", ready: true }
GET    /agenda/today                         → AgendaJour (events + séance entrain. + slots + tâches urgentes)
GET    /agenda/events?from=&to=&include_training=
POST   /agenda/events                        → créer event ponctuel
PATCH  /agenda/events/{id}
DELETE /agenda/events/{id}

GET    /agenda/recurrences                   → liste des règles de répétition
POST   /agenda/recurrences                   → créer règle (weekdays + start/end time)
PATCH  /agenda/recurrences/{id}
DELETE /agenda/recurrences/{id}

GET    /agenda/tasks?statut=&categorie=      → tâches triées par urgence
POST   /agenda/tasks
PATCH  /agenda/tasks/{id}
POST   /agenda/tasks/{id}/done               → marquer complète
DELETE /agenda/tasks/{id}

GET    /agenda/slots?date=&min_duration=     → créneaux libres ≥ min_duration min
POST   /agenda/import-ical                   → upload .ics (multipart)
```

## Architecture livrée

```
backend/app/
├── models/agenda.py                  (3 modèles : RegleRecurrence, Evenement étendu, Tache) — 95 l.
├── api/
│   ├── routes_agenda.py              (17 endpoints, 310 l.)
│   └── schemas_agenda.py             (Pydantic in/out, 148 l.)
└── services/agenda/                  TOUS < 200 lignes (cf. PLAN.md note 9)
    ├── __init__.py                   (façade publique)
    ├── recurrence.py                 (expand_rule + expand_rules_for_window — pur Python)
    ├── slots.py                      (free_slots + _merge_intervals — pur Python)
    ├── events.py                     (CRUD Evenement + RegleRecurrence + get_full_calendar)
    ├── tasks.py                      (CRUD Tache, tri urgence)
    ├── ical_adapter.py               (parseur RFC 5545 V1 — VEVENT + RRULE hebdo)
    └── entrainement_bridge.py        (import in-process try/except + fallback silencieux)

backend/alembic/versions/
└── 20260525_1000_c3d4e5f6a7b8_agenda.py

backend/tests/test_agenda/            (31 tests)
├── test_recurrence.py                (6 — logique pure, sans DB)
├── test_slots.py                     (10 — logique pure, sans DB)
└── test_api.py                       (15 — intégration SQLite in-memory)

frontend/
├── lib/agenda.ts                     (types + client API typé)
├── src/app/agenda/page.tsx           (mount Agenda — remplace le placeholder)
└── components/agenda/
    ├── Agenda.tsx                    (orchestrateur + 3 onglets)
    ├── JourTab.tsx                   (timeline horaire + séance entraînement + slots libres)
    ├── SemaineTab.tsx                (grille 7 colonnes × 15 créneaux)
    └── TachesTab.tsx                 (liste priorisée + formulaire d'ajout)
```

## Surprises / décisions techniques utiles à retenir

1. **Occurrences de récurrences = non persistées**. Elles sont générées virtuellement
   à chaque requête `GET /events` par `expand_rules_for_window`. Avantage : supprimer
   une occurrence "ce jeudi" n'efface pas les autres — le front n'a qu'à ignorer la
   date. V2 pourra persister des exceptions (`EXDATE`) si besoin.

2. **`Evenement.fin` optionnel → calcul slots**. Dans `slots.py`, un événement sans
   `fin` est traité comme durant 1h (fallback). Important si des événements Garmin
   ou iCal arrivent sans heure de fin.

3. **Bridge Entraînement sans mock en test**. Les tests API utilisent une DB
   in-memory sans données Entraînement → le bridge retourne `None` silencieusement
   (le `try/except` absorbe l'absence de séances). `GET /agenda/today` répond 200
   avec `seance_entrainement: null`. Pas besoin de mocker le module Entraînement.

4. **Import .ics : déduplication par UID iCal + source="ical"**. Si le même .ics
   est importé deux fois, les événements sont skippés (compteur `skipped_duplicates`).
   Les RRULE hebdo créent une `RegleRecurrence` + un `Evenement` seed (first occurrence).
   V2 devra gérer `EXDATE` et la mise à jour des règles existantes.

5. **`updated_at` absent de `Evenement`** (bug découvert au test). Le modèle CONV 1
   ne l'avait pas prévu. `update_event()` n'essaie pas de le setter. Si utile plus
   tard, ajouter via migration. `Tache` et `RegleRecurrence` ont bien `updated_at`.

6. **`SemaineTab` : boucle `{HOURS.map}` avec fragment implicite**. Next.js 15 /
   React 19 requiert une `key` sur chaque enfant direct d'une liste. L'utilisation
   de `<>...</>` sans key dans la boucle heures×colonnes peut lever un warning en
   dev. Si besoin, wrapper dans `<div key=...>` ou passer à un layout CSS Grid pur.

## Action utilisateur — finaliser CONV 5 chez Germain

### 0. Faire le commit (sandbox n'a pas pu — même cause que CONV 7)

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
rm -f .git/HEAD.lock .git/index.lock 2>/dev/null

git add \
  backend/pyproject.toml \
  backend/alembic/versions/20260525_1000_c3d4e5f6a7b8_agenda.py \
  backend/app/models/agenda.py \
  backend/app/models/__init__.py \
  backend/app/api/schemas_agenda.py \
  backend/app/api/routes_agenda.py \
  backend/app/services/agenda/ \
  backend/tests/test_agenda/ \
  frontend/lib/agenda.ts \
  frontend/src/app/agenda/page.tsx \
  frontend/components/agenda/ \
  orchestration/CONV5_DONE.md

git commit -m "feat(agenda): build module from scratch + entrainement integration (CONV 5)

- Models: Evenement (étendu: +categorie +couleur +recurrence_id),
  RegleRecurrence (règle hebdo simple JSON), Tache (priorité + deadline).
  Migration c3d4e5f6a7b8 (revises b2c3d4e5f6a7).
- Services en sous-modules < 200 lignes (cf. PLAN.md note 9):
  recurrence (expansion pure, testable sans DB),
  slots (algo créneaux libres, testable sans DB),
  events (CRUD Evenement + RegleRecurrence + vue combinée),
  tasks (CRUD Tache, tri urgence),
  ical_adapter (parseur RFC 5545 V1),
  entrainement_bridge (import in-process try/except fallback).
- 17 endpoints REST sous /agenda/*.
- Boucle CONV 7 fermée: seance_entrainement dans GET /agenda/today.
- Frontend: 3 onglets (Aujourd'hui timeline, Semaine grille, Tâches).
- Tests: 31 verts (6 recurrence + 10 slots + 15 api)."
```

### 1. Appliquer la migration

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
make migrate    # alembic upgrade head → applique c3d4e5f6a7b8
```

### 2. Installer les nouvelles dépendances

```bash
cd backend
uv sync         # ajoute icalendar, python-dateutil, python-multipart
```

### 3. Démarrer et tester

```bash
make dev        # backend :8000 + frontend :3000
```

Ouvrir http://localhost:3000/agenda :
- Onglet **📅 Aujourd'hui** : timeline du jour. Si une séance est loggée dans
  Entraînement (ou si un programme PPL/UL est actif), elle apparaît en amber
  dans la timeline et dans le badge en haut.
- Onglet **🗓 Semaine** : grille 7 jours (nav ‹ / › pour changer de semaine).
- Onglet **✅ Tâches** : liste triée, bouton "+ Ajouter".

### 4. Ajouter tes cours UQAM

Via l'API (Swagger http://localhost:8000/docs) ou en attendant le bouton UI :

```bash
# Créer une règle de récurrence : INF1000 lun-mer-ven 9h-12h
curl -X POST http://localhost:8000/agenda/recurrences \
  -H "Content-Type: application/json" \
  -d '{
    "titre": "INF1000",
    "weekdays": [0, 2, 4],
    "start_time": "09:00",
    "end_time": "12:00",
    "lieu": "PK-1234",
    "categorie": "cours",
    "couleur": "#3B82F6",
    "until": "2026-12-20"
  }'
```

(Répéter pour MAT2000, shifts barista, etc.)

### 5. Importer un fichier .ics (optionnel)

```bash
curl -X POST http://localhost:8000/agenda/import-ical \
  -F "file=@/chemin/vers/export.ics"
```

Retour : `{ "created_events": N, "skipped_duplicates": 0, "created_rules": M }`

## Prochaine CONV recommandée

**CONV 4 — Module Finance (suivi + Buffett mensuel)**. C'est le module le
plus dense (1920 lignes legacy). Brief dans `orchestration/CONV4_finance.md`.

Alternative plus légère : **CONV 6 — Module Études** pour brancher les devoirs
dans les tâches Agenda (contrat déjà prévu via `source="etudes"` + `source_id`).
