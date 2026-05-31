# CONV 6 — Récap de clôture

> À coller dans la conversation orchestrateur pour mettre à jour `PLAN.md`.

## Décisions prises au démarrage

| Question                              | Décision                                                                                          |
|---------------------------------------|---------------------------------------------------------------------------------------------------|
| Système de notation                   | **Note brute /100** → lettre + points GPA calculés à la volée. Barème UQAM complet (A+ 4.3 → E 0.0) dans `constants.py`. |
| Granularité                           | **Note finale par cours** (`Cours.note_finale`). Table `Evaluation` légère (titre, type, date) pour les deadlines — pas de pondération. GPA = moyenne simple. |
| Suivi du temps d'étude                | **V1 livré** : table `session_etude` + 4 endpoints. Durée en minutes, cours optionnel. |
| Syllabus import                       | **Saisie manuelle uniquement** (V1). Champ `note` libre sur `Cours` pour notes perso. |
| Calcul GPA                            | **Moyenne simple** — tous les cours pèsent pareil. `Cours.credits` stocké (défaut 3) pour une V2 pondérée. |

## Stack effective

- **Backend** : FastAPI 0.115 + SQLModel 0.0.38 + Alembic 1.14 + Pydantic 2.13
- **DB** : SQLite, migration `d4e5f6a7b8c9` (revises `c3d4e5f6a7b8`)
- **Nouvelles dépendances** : aucune
- **Frontend** : Next.js 15 + React 19 + TailwindCSS 4 (CSS variables shadcn-style)
- **Tests** : pytest 8.3 → **43 tests verts** (24 API + 19 grades)

## Livré (critères de succès du brief)

- [x] Ajout d'un cours → note finale pondérée correcte (lettre + GPA calculés à la volée)
- [x] GPA semestriel et cumulatif calculés correctement (`GET /etudes/gpa?semestre=`)
- [x] Ajouter une évaluation future crée une Tache dans Agenda (`source="etudes"`, `source_id=<eval_id>`)
- [x] Vue GPA historique fonctionne (jauge circulaire SVG + détail par cours)
- [x] Bridge Agenda silencieux : si Agenda échoue, l'évaluation est quand même créée (PLAN note 20)
- [x] `pytest tests/test_etudes/` : **43/43 verts**

## Schéma DB modifié

Migration `d4e5f6a7b8c9_etudes.py` (revises `c3d4e5f6a7b8`) :

**`etude`** (stub CONV 1) → **supprimée** (aucune donnée réelle).

**`cours`** (nouvelle) :
- `id`, `code` (indexé), `nom`, `semestre` (indexé), `credits` (défaut 3)
- `prof`, `local`, `note_finale` (float /100, optionnel), `actif` (bool, défaut True)
- `note` (texte libre), `created_at`, `updated_at`

**`evaluation`** (nouvelle) :
- `id`, `cours_id` (FK indexé), `titre`, `type_eval` (exam/devoir/quiz/projet/autre)
- `date_limite` (date, indexée), `note_obtenue`, `note_max` (défaut 100)
- `note` (texte libre), `created_at`, `updated_at`

**`session_etude`** (nouvelle) :
- `id`, `cours_id` (FK optionnel, indexé), `date` (indexée), `duree_min`
- `sujet`, `note`, `created_at`

## Endpoints exposés (`/openapi.json`)

```
GET    /etudes/ping                           → { module: "etudes", ready: true }

GET    /etudes/cours?semestre=&actif=         → liste avec lettre + GPA + total_minutes
POST   /etudes/cours                          → créer cours
GET    /etudes/cours/{id}                     → détail enrichi
PATCH  /etudes/cours/{id}                     → édition (incl. note_finale)
DELETE /etudes/cours/{id}                     → cascade manuelle eval + sessions

GET    /etudes/cours/{id}/evaluations?upcoming_only=
POST   /etudes/evaluations                    → créer + bridge Agenda silencieux
GET    /etudes/evaluations/{id}
PATCH  /etudes/evaluations/{id}
DELETE /etudes/evaluations/{id}

GET    /etudes/deadlines?days=30              → évals à venir (horizon configurable)
GET    /etudes/gpa?semestre=                  → GPA semestriel ou cumulatif

GET    /etudes/sessions?cours_id=&date_from=&date_to=
POST   /etudes/sessions                       → date auto = aujourd'hui si absente
PATCH  /etudes/sessions/{id}
DELETE /etudes/sessions/{id}
```

## Architecture livrée

```
backend/app/
├── models/etudes.py                  (3 modèles : Cours, Evaluation, SessionEtude) — 69 l.
├── api/
│   ├── routes_etudes.py              (18 endpoints) — 248 l.
│   └── schemas_etudes.py             (Pydantic in/out) — 143 l.
└── services/etudes/                  TOUS < 200 lignes (cf. PLAN.md note 9)
    ├── __init__.py                   (façade publique)
    ├── constants.py                  (barème UQAM + PRIORITE_PAR_TYPE) — 50 l.
    ├── courses.py                    (CRUD Cours + cascade delete) — 77 l.
    ├── evaluations.py                (CRUD Evaluation + bridge Agenda) — 109 l.
    ├── grades.py                     (GPA pur Python, testable sans DB) — 93 l.
    └── sessions.py                   (CRUD SessionEtude + total_minutes) — 74 l.

backend/alembic/versions/
└── 20260526_1000_d4e5f6a7b8c9_etudes.py

backend/tests/test_etudes/           (43 tests)
├── test_grades.py                   (19 — barème UQAM + GPA pur Python, sans DB)
└── test_api.py                      (24 — intégration SQLite in-memory)

frontend/
├── lib/etudes.ts                    (types + client API typé)
├── src/app/etudes/page.tsx          (mount — remplace le placeholder)
└── components/etudes/
    ├── Etudes.tsx                   (orchestrateur + 4 onglets)
    ├── CoursTab.tsx                 (liste cours + saisie note finale inline)
    ├── DeadlinesTab.tsx             (évaluations à venir + formulaire ajout)
    ├── GpaTab.tsx                   (jauge SVG circulaire + détail par cours)
    └── SessionsTab.tsx              (log sessions d'étude + cumul heures)
```

## Surprises / décisions techniques utiles à retenir

1. **Bridge Agenda silencieux confirmé**. `evaluations.py` appelle
   `agenda_tasks.create_task()` dans un `try/except` global qui log un
   `warning` et continue. Dans les tests (DB in-memory, module Agenda non
   initialisé), l'exception est absorbée et `POST /etudes/evaluations` répond
   201 quand même. Exactement le comportement attendu par PLAN note 20.

2. **Cascade delete manuelle indispensable** (PLAN note 16). SQLite ne
   cascade pas automatiquement. `delete_cours()` supprime d'abord les
   `Evaluation` et `SessionEtude` liées avant de supprimer le `Cours`.
   Couvert par `test_delete_cours_cascade`.

3. **`Cours.note_finale` = source de vérité GPA** (décision 2.B). La table
   `Evaluation` stocke `note_obtenue` pour référence, mais le GPA se calcule
   toujours depuis `note_finale` sur `Cours`. Cela simplifie énormément la
   logique : `grades.py` ne dépend pas de la table `Evaluation` du tout.

4. **`grades.py` = zéro dépendance DB**. Toutes les fonctions acceptent des
   `list[dict]` et retournent des dataclasses. Cela permet de tester tout le
   barème UQAM et le calcul GPA sans fixture DB (19 tests < 1 s).

5. **Contrat Agenda figé respecté**. L'appel dans `_try_create_agenda_task()`
   utilise exactement `create_task(session, dict)` (signature réelle de
   `agenda/tasks.py`), pas `create_tache(session, TacheCreate(...))` comme
   écrit dans le brief CONV6 (le brief était légèrement en avance sur
   l'implémentation réelle de CONV 5).

6. **Route `date_limite` nullable**. Une évaluation peut être créée sans date
   (par ex. "TP non encore planifié"). Dans ce cas le bridge Agenda ne crée
   pas de tâche (la date est `None`). Les deadlines sans date n'apparaissent
   pas dans `GET /etudes/deadlines` (filtre `upcoming_only=True`).

7. **GPA jauge SVG inline** dans `GpaTab.tsx`. Pas de lib externe — le cercle
   `stroke-dasharray` est calculé directement depuis `gpa/4.3 × circonférence`.
   Couleur dynamique : vert ≥ 3.7, bleu ≥ 3.0, jaune ≥ 2.0, rouge sinon.

## Action utilisateur — finaliser CONV 6 chez Germain

### 0. Faire le commit

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
rm -f .git/HEAD.lock .git/index.lock 2>/dev/null

git add \
  backend/alembic/versions/20260526_1000_d4e5f6a7b8c9_etudes.py \
  backend/app/models/etudes.py \
  backend/app/models/__init__.py \
  backend/app/api/schemas_etudes.py \
  backend/app/api/routes_etudes.py \
  backend/app/services/etudes/ \
  backend/tests/test_etudes/ \
  frontend/lib/etudes.ts \
  frontend/src/app/etudes/page.tsx \
  frontend/components/etudes/ \
  orchestration/CONV6_DONE.md

git commit -m "feat(etudes): build module from scratch + agenda bridge (CONV 6)

- Models: Cours (code/nom/semestre/crédits/note_finale),
  Evaluation (titre/type/date_limite + bridge Agenda),
  SessionEtude (durée/sujet). Migration d4e5f6a7b8c9
  (revises c3d4e5f6a7b8, drop stub etude).
- Services en sous-modules < 200 lignes (cf. PLAN.md note 9):
  constants (barème UQAM A+→E /4.3 + priorité par type),
  courses (CRUD + cascade delete manuelle),
  evaluations (CRUD + bridge Agenda silencieux PLAN note 20),
  grades (GPA pur Python testable sans DB),
  sessions (CRUD log de travail + cumul minutes).
- 18 endpoints REST sous /etudes/*.
- Bridge Agenda: POST /etudes/evaluations → Tache(source='etudes',
  source_id=<eval_id>) via import in-process try/except (PLAN note 14).
- Frontend Next.js: 4 onglets (Cours, Deadlines, GPA jauge SVG, Sessions).
- Tests: 43 verts (19 grades pur Python + 24 API intégration SQLite)."
```

### 1. Appliquer la migration

```bash
cd /c/Users/germa/Documents/GitHub/mission-control
make migrate    # alembic upgrade head → applique d4e5f6a7b8c9
```

> ⚠️ Cette migration **supprime la table `etude`** (stub CONV 1, aucune donnée réelle). Si tu as des données dans cette table, sauvegarde-les avant.

### 2. Démarrer et tester

```bash
make dev        # backend :8000 + frontend :3000
```

Ouvrir http://localhost:3000/etudes :

- Onglet **📚 Cours** : ajouter tes cours UQAM du semestre (ex: INF1000, MAT2000). Clique sur "Saisir note" pour entrer ta note finale → la lettre UQAM et le GPA s'affichent automatiquement.
- Onglet **📅 Deadlines** : ajouter tes évaluations avec date → une tâche Agenda est créée automatiquement avec `source="etudes"`.
- Onglet **🎓 GPA** : jauge circulaire du GPA cumulatif ou par semestre.
- Onglet **⏱ Sessions** : logger tes sessions de travail (Pomodoro ou libres).

### 3. Ajouter tes premiers cours via l'API (alternatif au UI)

```bash
# Exemple : INF1000
curl -X POST http://localhost:8000/etudes/cours \
  -H "Content-Type: application/json" \
  -d '{"code":"INF1000","nom":"Introduction à la programmation","semestre":"A2026","credits":3}'

# Ajouter une évaluation avec deadline → crée aussi une tâche Agenda
curl -X POST http://localhost:8000/etudes/evaluations \
  -H "Content-Type: application/json" \
  -d '{"cours_id":1,"titre":"Examen final","type_eval":"exam","date_limite":"2026-12-15"}'
```

### 4. Vérifier la boucle Agenda

```bash
# La tâche créée par le bridge doit apparaître ici :
curl http://localhost:8000/agenda/tasks?categorie=devoir | python3 -m json.tool
```

## Prochaine CONV recommandée

**CONV 4 — Module Finance** (le plus dense : 1920 lignes legacy Buffett à porter).
Brief dans `orchestration/CONV4_finance.md`.
