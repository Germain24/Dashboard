# Mission Control — Completion Design Spec

> **Statut :** Approuvé par Germain le 2026-05-31
> **Scope :** CONV 8 (Budget) + CONV 9 (Cuisine) + CONV 10 (Habitudes) + CONV 11 (Livres) + CONV 13 (Scheduler) + CONV 14 (Auth) + CONV 15 (Tests/CI) + Redesign frontend complet
> **Exclu :** CONV 12 (Agent IA) — supprimé sur décision Germain

---

## Stratégie d'exécution : 3 couches séquentielles

```
COUCHE 1 — Backend (4 agents parallèles)
  Agent A : Budget
  Agent B : Habitudes + Livres
  Agent C : Cuisine
  Agent D : Scheduler + Notifications

COUCHE 2 — Frontend + Redesign (4 agents parallèles, après C1)
  Agent E : Redesign ui-ux-pro-max (layout + composants + tous modules existants)
  Agent F : Budget UI + Habitudes UI + Livres UI
  Agent G : Cuisine UI + Jobs UI
  Agent H : Auth/Tailscale config + next.config.ts

COUCHE 3 — Infra finale (après C2)
  Agent I : Tests (pytest + Vitest) + CI GitHub Actions
```

---

## Architecture cible finale

```
mission-control/
├── backend/
│   └── app/
│       ├── models/
│       │   ├── budget.py         # BudgetTransaction, BudgetCategory, BudgetRule, BudgetEnvelope
│       │   ├── habitudes.py      # Habit, HabitEntry
│       │   ├── livres.py         # Book, BookNote, BookQuote, ReadingSession
│       │   ├── cuisine.py        # Recipe, RecipeIngredient, MealPlan, ShoppingList
│       │   └── scheduler.py      # Notification, JobRun
│       ├── api/
│       │   ├── routes_budget.py
│       │   ├── routes_habitudes.py
│       │   ├── routes_livres.py
│       │   ├── routes_cuisine.py
│       │   ├── routes_scheduler.py
│       │   └── routes_notifications.py
│       ├── services/
│       │   ├── budget/
│       │   │   ├── transactions.py
│       │   │   ├── categories.py
│       │   │   ├── rules.py
│       │   │   ├── envelopes.py
│       │   │   └── imports.py
│       │   ├── habitudes/
│       │   │   ├── habits.py
│       │   │   ├── entries.py
│       │   │   ├── streaks.py
│       │   │   └── heatmap.py
│       │   ├── livres/
│       │   │   ├── books.py
│       │   │   ├── notes.py
│       │   │   ├── sessions.py
│       │   │   └── metadata.py
│       │   ├── cuisine/
│       │   │   ├── recipes.py
│       │   │   ├── ingredients.py
│       │   │   ├── macros.py
│       │   │   ├── meal_plan.py
│       │   │   └── shopping_list.py
│       │   └── scheduler/
│       │       ├── scheduler.py
│       │       ├── runner.py
│       │       └── jobs/
│       │           ├── portfolio_snapshot.py
│       │           ├── nutrition_plan.py
│       │           ├── weather_refresh.py
│       │           ├── buffett_monthly.py
│       │           └── backup_db.py
│       └── jobs/                 # point d'entrée APScheduler
│           └── __init__.py
├── frontend/
│   ├── components/
│   │   ├── ui/                   # primitives redessinées (Button, Card, Tabs, etc.)
│   │   ├── layout/               # Sidebar, Header, PageLayout (nouveaux)
│   │   ├── budget/
│   │   ├── habitudes/
│   │   ├── livres/
│   │   └── cuisine/
│   └── src/app/
│       ├── budget/
│       ├── habitudes/
│       ├── livres/
│       ├── cuisine/
│       └── jobs/
└── backend/tests/
    ├── test_budget/
    ├── test_habitudes/
    ├── test_livres/
    └── test_cuisine/
```

---

## COUCHE 1A — Module Budget

### Modèles SQLModel (`backend/app/models/budget.py`)

```python
class BudgetCategory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    parent_id: int | None = Field(default=None, foreign_key="budgetcategory.id")
    couleur: str = "#6366f1"

class BudgetRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pattern: str          # regex sur marchand
    category_id: int = Field(foreign_key="budgetcategory.id")
    priorite: int = 0
    created_at: datetime

class BudgetTransaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date
    montant: float        # négatif = dépense, positif = revenu
    marchand: str
    description: str = ""
    category_id: int | None = Field(default=None, foreign_key="budgetcategory.id")
    compte: str = "principal"
    devise: str = "CAD"
    auto: bool = False    # True si créée par Cuisine (courses faites)

class BudgetEnvelope(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="budgetcategory.id")
    mois: str             # "2026-05"
    montant: float        # budget alloué
```

### Endpoints (`backend/app/api/routes_budget.py`)

```
GET    /api/budget/transactions?from=&to=&category_id=&compte=
POST   /api/budget/transactions
PATCH  /api/budget/transactions/{id}
DELETE /api/budget/transactions/{id}
POST   /api/budget/import              # CSV Desjardins/RBC/générique

GET    /api/budget/categories
POST   /api/budget/categories
PATCH  /api/budget/categories/{id}

GET    /api/budget/rules
POST   /api/budget/rules
DELETE /api/budget/rules/{id}
POST   /api/budget/rules/apply         # ré-appliquer à tout l'historique

GET    /api/budget/envelopes?month=
POST   /api/budget/envelopes

GET    /api/budget/summary?month=      # entrées, sorties, par catégorie
GET    /api/budget/cashflow?from=&to=  # série temporelle mensuelle
GET    /api/budget/disposable?month=   # revenus - dépenses (lu par Finance)
```

### Services

- `imports.py` : détection auto format CSV (Desjardins: col 0=date, 1=desc, 2=débit, 3=crédit ; RBC: similaire ; générique: 3 cols date/desc/montant). Applique les règles immédiatement.
- `rules.py` : `apply_rules(description)` → cherche le premier pattern regex matching par priorité décroissante.
- `envelopes.py` : `get_envelope_status(month)` → pour chaque catégorie, budget alloué vs dépensé réel.

### Catégories initiales seedées

```
Logement > Loyer, Électricité, Internet
Transport > Essence, Transport en commun, Stationnement
Nourriture > Épicerie, Restaurants, Livraison
Santé > Pharmacie, Sport, Médecin
Loisirs > Cinéma, Sorties, Hobbies
Abonnements > Streaming, Cloud, Logiciels
Revenus > Salaire, Freelance, Autres
```

---

## COUCHE 1B — Module Habitudes

### Modèles (`backend/app/models/habitudes.py`)

```python
class Habit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    type: str = "binaire"     # "binaire" | "quantifiable"
    unite: str | None = None  # ex: "minutes", "litres"
    cible: float = 1.0        # 1 pour binaire, N pour quantifiable
    frequence: str = "daily"  # "daily" | "3x_week"
    source_auto: str | None = None  # "entrainement_muscu", "livres_lecture"
    actif: bool = True
    ordre: int = 0

class HabitEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id")
    date: dt.date
    valeur: float = 1.0
    auto: bool = False
    __table_args__ = (UniqueConstraint("habit_id", "date"),)
```

### Endpoints

```
GET    /api/habitudes/habits
POST   /api/habitudes/habits
PATCH  /api/habitudes/habits/{id}
DELETE /api/habitudes/habits/{id}

GET    /api/habitudes/today
POST   /api/habitudes/entries           # upsert (habit_id + date unique)
DELETE /api/habitudes/entries/{id}

GET    /api/habitudes/streaks
GET    /api/habitudes/heatmap?habit_id=&year=
GET    /api/habitudes/stats?from=&to=
```

### Auto-cochage (import in-process, pattern CONV 7)

Dans `backend/app/services/entrainement/sessions.py` (existant), après création d'une séance :
```python
try:
    from app.services.habitudes.entries import auto_check_habit
    auto_check_habit(session_db, source="entrainement_muscu", date=seance.date)
except Exception:
    pass  # silencieux, habitudes optionnelles
```

Même pattern dans `livres/sessions.py` pour "livres_lecture" si durée ≥ 30 min.

### Habitudes initiales seedées

| Nom | Type | Cible | Source auto |
|-----|------|-------|-------------|
| Muscu | binaire | 1 | entrainement_muscu |
| Course | binaire | 1 | entrainement_cardio |
| Lecture | quantifiable | 30 min | livres_lecture |
| Sommeil ≥ 7h | binaire | 1 | manuel |
| Pas de junk food | binaire | 1 | manuel |
| Méditation | binaire | 1 | manuel |

---

## COUCHE 1C — Module Livres

### Modèles (`backend/app/models/livres.py`)

```python
class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    auteur: str = ""
    isbn: str | None = None
    pages: int | None = None
    statut: str = "a_lire"   # "a_lire" | "en_cours" | "lu"
    genre: str = ""
    format: str = "papier"   # "papier" | "ebook" | "audio"
    note: float | None = None  # /5
    date_debut: dt.date | None = None
    date_fin: dt.date | None = None
    couverture_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BookNote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    contenu: str             # Markdown
    tags: str = "[]"         # JSON list

class BookQuote(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    texte: str

class ReadingSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    date: dt.date
    duree_minutes: int
    page_debut: int | None = None
    page_fin: int | None = None
```

### Endpoints

```
GET    /api/livres/books?statut=
POST   /api/livres/books
PATCH  /api/livres/books/{id}
DELETE /api/livres/books/{id}
POST   /api/livres/books/from-isbn      # Open Library lookup

GET    /api/livres/books/{id}/notes
POST   /api/livres/books/{id}/notes
PATCH  /api/livres/notes/{id}
DELETE /api/livres/notes/{id}

GET    /api/livres/books/{id}/quotes
POST   /api/livres/books/{id}/quotes
DELETE /api/livres/quotes/{id}

POST   /api/livres/books/{id}/sessions  # → coche habit si >= 30 min
GET    /api/livres/stats
```

### metadata.py

Open Library API (gratuite, sans clé) :
```
GET https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data
```
Fallback : si pas trouvé, retourner `{found: false}` et laisser l'utilisateur remplir manuellement.
Couvertures : `https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg` stockées dans `data/covers/`.

---

## COUCHE 1D — Module Cuisine

### Modèles (`backend/app/models/cuisine.py`)

```python
class Recipe(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    portions: int = 4
    temps_prep: int = 0      # minutes
    temps_cuisson: int = 0
    instructions: str = ""   # Markdown
    source_url: str | None = None
    image_url: str | None = None

class RecipeIngredient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    aliment_id: int | None = Field(default=None, foreign_key="aliment.id")
    nom_libre: str = ""      # si pas dans table aliment
    quantite: float
    unite: str               # "g", "ml", "unité", "c. à soupe"

class MealPlanEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    semaine: str             # "2026-W22"
    jour: int                # 0=lundi ... 6=dimanche
    repas: str               # "petit_dejeuner" | "dejeuner" | "souper"
    recipe_id: int | None = Field(default=None, foreign_key="recipe.id")
    notes: str = ""

class ShoppingListItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    semaine: str
    ingredient: str
    quantite: float
    unite: str
    rayon: str = "Autre"     # "Légumes", "Viandes", "Produits laitiers"...
    achete: bool = False
```

### Endpoints

```
GET    /api/cuisine/recipes?search=
POST   /api/cuisine/recipes
PATCH  /api/cuisine/recipes/{id}
DELETE /api/cuisine/recipes/{id}
GET    /api/cuisine/recipes/{id}/macros
POST   /api/cuisine/recipes/from-url   # JSON-LD parsing

GET    /api/cuisine/meal-plan?week=
POST   /api/cuisine/meal-plan/generate  # algo glouton vs cibles CONV 3
PATCH  /api/cuisine/meal-plan/{id}

GET    /api/cuisine/shopping-list?week=
POST   /api/cuisine/shopping-list/done  # → BudgetTransaction "Nourriture"
PATCH  /api/cuisine/shopping-list/{id}
```

### Algorithme meal_plan glouton

1. Charger cibles nutrition journalières depuis CONV 3 (`plan_nutrition` actif)
2. Pour chaque jour × repas : sélectionner la recette qui minimise `|macros_restantes - macros_recette|`
3. Marquer la recette comme utilisée pour éviter les répétitions sur la semaine
4. Retourner le plan 7 jours

---

## COUCHE 1E — Scheduler

### Activation APScheduler (`backend/app/services/scheduler/scheduler.py`)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def create_scheduler(db_url: str) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Montreal")
    return scheduler
```

Démarré dans `main.py` via `@app.on_event("startup")`.

### Jobs V1

| Job | Cron | Fichier |
|-----|------|---------|
| Snapshot portefeuille | `0 22 * * *` | `jobs/portfolio_snapshot.py` |
| Plan nutrition | `30 6 * * *` | `jobs/nutrition_plan.py` |
| Refresh météo | `0 6,12,18,0 * * *` | `jobs/weather_refresh.py` (Open-Meteo API, gratuite, sans clé — même source que Garde-robe) |
| Analyse Buffett | `0 3 1 * *` | `jobs/buffett_monthly.py` |
| Backup SQLite | `0 0 * * *` | `jobs/backup_db.py` |

### Modèles Notification + JobRun

```python
class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str              # "scheduler", "budget", etc.
    level: str = "info"      # "info" | "warning" | "error"
    titre: str
    message: str = ""
    lu: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class JobRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"  # "running" | "success" | "error"
    log: str = ""
```

---

## COUCHE 2 — Frontend Redesign (Linear/Notion)

### Layout (`frontend/components/layout/`)

```typescript
// PageLayout.tsx — wrapper commun pour toutes les pages
// Sidebar.tsx — redessinée : 240px, groupes, icônes Lucide, active state
// Header.tsx — titre page + slot actions droite
// NotificationsWidget.tsx — cloche en haut, badge nombre non lus
```

**Sidebar groupes :**
```
📊 Dashboard
─── Vie quotidienne
    🎯 Habitudes
    📚 Livres
    👕 Garde-robe
    🍽️ Cuisine
─── Santé & Sport
    🏥 Santé
    💪 Entraînement
─── Organisation
    📅 Agenda
    🎓 Études
─── Finances
    💰 Finance
    💳 Budget
─── Système
    ⚙️ Jobs
```

### Design tokens (extension DESIGN.md existant)

- Sidebar bg : `var(--sidebar)` (nouvelle variable, légèrement différente de `--background`)
- Active item : `var(--accent)` bg + `var(--accent-foreground)` text
- Border radius global : `8px` (moins agressif que arrondi actuel)
- Font chiffres : `font-mono` pour toutes les valeurs numériques (finances, stats)
- Tabs style Linear : underline actif 2px, pas de box

### Nouvelles pages frontend

**Budget** (`/budget`) : 5 onglets
- Mois : cards revenus/dépenses/solde + pie catégories + top 5 transactions
- Transactions : table avec filtre, inline recatégorisation, bouton import CSV
- Enveloppes : progress bars rouge/vert par catégorie
- Tendances : bar chart 12 mois par catégorie
- Règles : liste regex → catégorie, CRUD

**Habitudes** (`/habitudes`) : 3 onglets
- Aujourd'hui : checklist verticale, streak badge, bouton check/uncheck
- Heatmap : grille 52 semaines × 7 jours (une par habitude, sélectionnable)
- Stats : taux complétion bar chart, comparaison habitudes

**Livres** (`/livres`) : 2 onglets
- Bibliothèque : Kanban 3 colonnes (À lire / En cours / Lu), cards avec couverture
- Stats : pages/an, livres/mois, top genres, top auteurs

**Cuisine** (`/cuisine`) : 4 onglets
- Recettes : grille cards avec macros, filtre, bouton import URL
- Plan semaine : grille 7 × 3 avec recettes assignées, bouton "Générer"
- Courses : checklist groupée par rayon, bouton "Tout acheté" → Budget
- Inventaire : simple liste texte (MVP)

**Jobs** (`/jobs`) : 1 page
- Table jobs avec statut, dernier run, prochain run
- Boutons Run / Pause par job
- Historique 10 derniers runs

---

## COUCHE 2H — Auth / Tailscale

Tailscale = config réseau, aucun code applicatif requis.

**next.config.ts** :
```typescript
const nextConfig = {
  // Allow requests from Tailscale subnet
  async headers() {
    return [{
      source: "/api/:path*",
      headers: [{ key: "X-Frame-Options", value: "SAMEORIGIN" }]
    }]
  }
}
```

**Documentation** dans `orchestration/logs/ACTIVITY.md` : instructions d'installation Tailscale sur la machine Windows + accès depuis mobile.

---

## COUCHE 3 — Tests & CI

### Backend (pytest)

Tests prioritaires (logique critique) :
- `test_budget/` : règles regex, catégorisation auto, calcul disposable
- `test_habitudes/` : calcul streak, auto-cochage inter-modules
- `test_livres/` : lookup ISBN, trigger habitude ≥ 30 min
- `test_cuisine/` : calcul macros, algo meal plan, déduplication liste courses

### Frontend (Vitest)

- `lib/budget.ts` : formatage montants, parsing dates
- `lib/habitudes.ts` : calcul streak côté client

### CI (`.github/workflows/ci.yml`)

```yaml
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv run pytest tests/ -q
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd frontend && npm ci && npm run test
```

---

## Règles transverses respectées

1. Patterns < 200 lignes par fichier service
2. Logique pure dans `*_pure.py` séparée des dépendances lourdes (pattern CONV 4)
3. Import in-process pour les intégrations inter-modules (try/except silencieux)
4. Pas de couleurs Tailwind hardcodées — CSS variables uniquement
5. Upsert + `IntegrityError` catchés partout (pattern CONV 7)
6. Mobile-first : tester 375 / 768 / 1280 / 1920 px
7. Données réelles jamais commitées (`data/` gitignored)
