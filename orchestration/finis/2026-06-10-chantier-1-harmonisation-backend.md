# Chantier 1 — Harmonisation backend : Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tous les modules backend passent au format du package `app/api/finance/` (package par module, schémas extraits, repository câblé, pagination/tri sur les listes), URLs inchangées.

**Architecture:** Migration mécanique module par module : `git mv routes_<m>.py app/api/<m>/routes.py` + `__init__.py` agrégateur + extraction des `BaseModel` inline vers `schemas.py` + branchement du repository existant + `Pagination`/`Sorting` sur les routes de liste. Le contrat OpenAPI est le filet de sécurité (`tests/test_openapi_contract.py`).

**Tech Stack:** FastAPI, SQLModel, pytest. Helpers déjà écrits : `app/core/repository.py`, `app/core/pagination.py`, `app/core/query_params.py`.

**Suivi :** chaque tâche = 1 item de la nouvelle section V de `orchestration/AMELIORATIONS_200.txt`, marqué `← FINIS ✓ (date)` au commit.

**Commandes (depuis `backend/`)** : `python -m pytest tests/test_habitudes -q` (module), `python -m pytest tests/test_openapi_contract.py -q` (contrat).

---

### Task 0: Bookkeeping — nouvelles sections dans AMELIORATIONS_200.txt + élagage IA

**Files:**
- Modify: `orchestration/AMELIORATIONS_200.txt`

- [ ] **Step 1: Marquer les items 236–255 ABANDONNÉ**

Pour chaque item 236 à 255, ajouter en fin de ligne :
`   ← ABANDONNÉ ✗ (2026-06-10 : pas d'IA conversationnelle/agents dans le dashboard — même décision que le module N.)`

- [ ] **Step 2: Ajouter les sections V–Z en fin de fichier**

```
--------------------------------------------------------------------------------
V. HARMONISATION BACKEND (501-517) — design 2026-06-10
--------------------------------------------------------------------------------
501. [S](**) api/habitudes/ en package (routes+schemas) + repository câblé + pagination listes.
502. [S](**) api/agenda/ idem (découper routes_agenda.py 487 lignes en sous-routeurs).
503. [S](**) api/garderobe/ idem (463 lignes, découper).
504. [S](**) api/sante/ idem (411 lignes, découper).
505. [S](**) api/entrainement/ idem (390 lignes, découper).
506. [S](**) api/etudes/ idem.
507. [S](**) api/budget/ idem.
508. [S](**) api/cuisine/ idem.
509. [S](**) api/journal/ idem.
510. [S](**) api/livres/ idem.
511. [S](**) api/musique/ idem.
512. [S](**) api/skincare/ idem.
513. [S](**) api/data/ idem.
514. [S](*) api/scheduler/ idem.
515. [S](*) api/notifications/ idem.
516. [S](*) api/health/ idem (ou justifier de le laisser plat).
517. [S](*) Corriger le cycle d'import app/main.py signalé par graphify.

--------------------------------------------------------------------------------
W. GÉNÉRALISATION FRONTEND + TESTS (518-533) — design 2026-06-10
--------------------------------------------------------------------------------
518-533. [M](**) lib/queries/<module>.ts (TanStack) + error boundary + tests vitest,
un item par module : agenda, budget, cuisine, donnees, entrainement, etudes,
garderobe, habitudes, jobs, journal, livres, musique, sante, skincare ;
+ découpe des composants >400 lignes (RecettesTab, AujourdhuiTab, BuffettTab, MoisTab).

--------------------------------------------------------------------------------
X. MODULES FILMS + SÉRIES TMDB (534-541) — design 2026-06-10
--------------------------------------------------------------------------------
534. [M](***) Modèles WatchItem + SerieProgress + migration Alembic.
535. [M](**) Service TMDB (httpx, cache TTL, dégradation gracieuse sans clé).
536. [M](**) Routes films_series : recherche TMDB, CRUD watchlist, progression, stats.
537. [M](**) Page Films réelle (onglets À voir/En cours/Vus, recherche, fiches).
538. [M](**) Page Séries réelle (idem + compteurs saison/épisode).
539. [S](*) Stats visionnage (vus/an, temps estimé) sur les deux pages.
540. [S](*) Clé TMDB absente → mode manuel complet (test dédié).
541. [S](*) Hooks TanStack + tests vitest pour les deux modules.

--------------------------------------------------------------------------------
Y. RÉORGANISATION UI (542-545) — design 2026-06-10
--------------------------------------------------------------------------------
542. [M](**) Sidebar groupée par domaines (Quotidien/Corps/Culture/Argent/Travail/Système) via lib/modules.ts.
543. [M](**) Page /parametres centralisée (clé TMDB, dossier musique, rétention backups, préférences).
544. [S](*) Store de settings backend (secrets en env, la page indique leur présence).
545. [S](*) Documents le moment venu : groupe Travail renommé.

--------------------------------------------------------------------------------
Z. NOUVEAUX ITEMS (546-549) — design 2026-06-10
--------------------------------------------------------------------------------
546. [M](**) Palette Cmd+K : recherche dans les données (transactions, recettes, livres…).
547. [M](**) Ajout rapide global depuis la palette (dépense, repas, séance).
548. [L](**) Module Documents/Administratif (échéances CNI/passeport, contrats, garanties, rappels scheduler).
549. [S](*) Marquage : vague 2 restante reprise par impact décroissant (***) d'abord.
```

- [ ] **Step 3: Commit**

```powershell
git add orchestration/AMELIORATIONS_200.txt
git commit -m "docs(ameliorations): sections V-Z (design 2026-06-10) + elagage items IA 236-255"
```

---

### Task 1: Module de référence — `api/habitudes/` en package (#501)

**Files:**
- Create: `backend/app/api/habitudes/__init__.py`
- Create: `backend/app/api/habitudes/schemas.py`
- Move: `backend/app/api/routes_habitudes.py` → `backend/app/api/habitudes/routes.py`
- Modify: `backend/app/api/__init__.py:18` (import) et `:40` (montage)
- Modify: `backend/app/api/habitudes/routes.py` (repository + pagination sur GET /habits)
- Test: `backend/tests/test_habitudes/test_api_pagination.py` (nouveau)

- [ ] **Step 1: Baseline verte**

Run: `cd backend; python -m pytest tests/test_habitudes tests/test_openapi_contract.py -q`
Expected: PASS (état avant migration).

- [ ] **Step 2: Test rouge — pagination sur GET /habitudes/habits**

```python
# backend/tests/test_habitudes/test_api_pagination.py
"""#501 — pagination standardisée sur la liste des habitudes."""


def test_habits_list_exposes_total_count(client, session):
    from app.models.habitudes import Habit
    for i in range(3):
        session.add(Habit(nom=f"h{i}"))
    session.commit()

    r = client.get("/api/v1/habitudes/habits?limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.headers["X-Total-Count"] == "3"


def test_habits_list_default_unchanged(client, session):
    """Rétro-compat : sans query params, tout est renvoyé (corps = tableau)."""
    from app.models.habitudes import Habit
    session.add(Habit(nom="seule"))
    session.commit()
    r = client.get("/api/v1/habitudes/habits")
    assert r.status_code == 200
    assert [h["nom"] for h in r.json()] == ["seule"]
```

(Adapter les fixtures aux conventions de `tests/test_habitudes/` existantes — reprendre le `client`/`session` du `conftest.py` du dossier.)

Run: `python -m pytest tests/test_habitudes/test_api_pagination.py -q`
Expected: FAIL (`X-Total-Count` absent).

- [ ] **Step 3: Créer le package**

```powershell
git mv backend/app/api/routes_habitudes.py backend/app/api/habitudes/routes.py
```

```python
# backend/app/api/habitudes/__init__.py
"""Routes Habitudes — package par module (#501). URLs inchangées."""
from fastapi import APIRouter

from . import routes

router = APIRouter(tags=["habitudes"])
router.include_router(routes.router)
```

```python
# backend/app/api/habitudes/schemas.py
"""Schémas du module Habitudes (extraits de routes_habitudes.py)."""
import datetime as dt

from pydantic import BaseModel


class HabitCreate(BaseModel):
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"
    couleur: str | None = None
    icone: str | None = None


class EntryCreate(BaseModel):
    habit_id: int
    date: dt.date
    valeur: float = 1.0
```

Dans `routes.py` : supprimer les deux classes inline, importer `from app.api.habitudes.schemas import HabitCreate, EntryCreate`.

Dans `backend/app/api/__init__.py` : remplacer `routes_habitudes` par
`from app.api.habitudes import router as habitudes_router` et monter
`api_router.include_router(habitudes_router, prefix="/habitudes")` (le tag est porté par le package).

- [ ] **Step 4: Câbler repository + pagination dans routes.py**

`GET /habits` passe au pattern de `api/finance/transactions.py:23-44` :

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from app.core.pagination import Pagination, paginate
from app.core.query_params import Sorting, apply_sort
from app.repositories.habitudes import HabitRepository


@router.get("/habits")
def list_habits(
    response: Response,
    page: Pagination = Depends(),
    sorting: Sorting = Depends(),
    session: Session = Depends(get_session),
):
    stmt = select(Habit).where(Habit.actif == True)
    if sorting.sort:
        stmt = apply_sort(stmt, Habit, sorting, allowed={"nom", "ordre", "frequence"})
    else:
        stmt = stmt.order_by(Habit.ordre)
    return paginate(session, stmt, response, page)
```

CRUD simples (`create/update/delete habit`, `delete entry`) passent par `HabitRepository(session)` (`repo.get(id)`, `repo.delete(h)`, etc. — voir l'API dans `app/core/repository.py`).

- [ ] **Step 5: Vert + contrat intact**

Run: `python -m pytest tests/test_habitudes tests/test_openapi_contract.py -q`
Expected: PASS, y compris le nouveau test de pagination.

- [ ] **Step 6: Commit + marquage**

Marquer `501.` avec `← FINIS ✓ (2026-06-10)` dans `orchestration/AMELIORATIONS_200.txt`.

```powershell
git add -A backend/app/api orchestration/AMELIORATIONS_200.txt backend/tests/test_habitudes
git commit -m "refactor(habitudes): #501 api/habitudes/ en package + repository + pagination"
```

---

### Tasks 2–15: Modules restants (#502–#515) — même recette instanciée

Un commit par module, **dans cet ordre** (gros fichiers d'abord) :

| Task | Item | Source à déplacer | Package cible | Tests module |
|------|------|-------------------|---------------|--------------|
| 2 | #502 | `app/api/routes_agenda.py` (487 l.) | `app/api/agenda/` | `tests/test_agenda` |
| 3 | #503 | `app/api/routes_garderobe.py` (463 l.) | `app/api/garderobe/` | `tests/test_garderobe` |
| 4 | #504 | `app/api/routes_sante.py` (411 l.) | `app/api/sante/` | `tests/test_sante` |
| 5 | #505 | `app/api/routes_entrainement.py` (390 l.) | `app/api/entrainement/` | `tests/test_entrainement` |
| 6 | #506 | `app/api/routes_etudes.py` (258 l.) | `app/api/etudes/` | `tests/test_etudes` |
| 7 | #507 | `app/api/routes_budget.py` | `app/api/budget/` | `tests/test_budget` |
| 8 | #508 | `app/api/routes_cuisine.py` | `app/api/cuisine/` | `tests/test_cuisine` |
| 9 | #509 | `app/api/routes_journal.py` | `app/api/journal/` | `tests/test_journal` |
| 10 | #510 | `app/api/routes_livres.py` | `app/api/livres/` | `tests/test_livres` |
| 11 | #511 | `app/api/routes_musique.py` | `app/api/musique/` | `tests/test_musique` |
| 12 | #512 | `app/api/routes_skincare.py` | `app/api/skincare/` | `tests/test_skincare` |
| 13 | #513 | `app/api/routes_data.py` | `app/api/data/` | `tests/test_data_io` |
| 14 | #514 | `app/api/routes_scheduler.py` | `app/api/scheduler_api/`¹ | `tests/test_scheduler` |
| 15 | #515 | `app/api/routes_notifications.py` | `app/api/notifications/` | — (tests transverses) |

¹ `scheduler_api` pour éviter la collision d'import avec `app/services/scheduler`
si elle se présente ; sinon `app/api/scheduler/` (vérifier que
`from app.api.scheduler import router` ne masque rien).

Pour CHAQUE module, dérouler exactement les étapes de la Task 1 en remplaçant `habitudes` :

- [ ] **Step A: Baseline** — `python -m pytest tests/test_<module> tests/test_openapi_contract.py -q` → PASS.
- [ ] **Step B: Inventaire des routes de liste** — `Select-String -Path backend/app/api/routes_<module>.py -Pattern '@router.get'`. Routes candidates à la pagination = celles dont le handler se termine par `.all()` sur un `select(...)` sans agrégation. Les routes de calcul/synthèse (stats, dashboards, optimiseurs) ne sont PAS paginées.
- [ ] **Step C: Test rouge pagination** — même squelette que `test_api_pagination.py` de la Task 1, instancié sur LA route de liste principale du module (modèle + URL réels). S'il n'y a aucune route de liste paginable, sauter C et le noter dans le message de commit.
- [ ] **Step D: Package** — `git mv` vers `app/api/<module>/routes.py`, `__init__.py` agrégateur identique à la Task 1 (tag = nom du module), `schemas.py` avec TOUS les `BaseModel` inline du fichier. Si un `app/api/schemas_<module>.py` plat existe (agenda, entrainement, etudes, finance, garderobe, sante) : le déplacer en `app/api/<module>/schemas.py` et poser un alias de réimport dans l'ancien chemin (`from app.api.<module>.schemas import *  # noqa: F401,F403 — compat`) si d'autres fichiers l'importent (vérifier avec `Select-String -Path backend -Pattern 'schemas_<module>'`). Mettre à jour `app/api/__init__.py`.
- [ ] **Step E: Repository** — si `app/repositories/<module>.py` existe, remplacer les `session.get`/`select` CRUD directs des handlers par le repository. Ne PAS toucher aux appels de services (`*_svc`) : la logique métier reste dans les services.
- [ ] **Step F: Découpage (gros modules seulement)** — agenda, garderobe, sante, entrainement : si `routes.py` > 300 lignes après extraction des schémas, découper en sous-routeurs thématiques (comme `finance/` : un fichier par groupe d'URLs cohérent), tous montés dans `__init__.py`. Les modules plus petits gardent un seul `routes.py`.
- [ ] **Step G: Vert** — `python -m pytest tests/test_<module> tests/test_openapi_contract.py -q` → PASS.
- [ ] **Step H: Commit + marquage** — `← FINIS ✓ (date)` sur l'item, message `refactor(<module>): #50X api/<module>/ en package + repository + pagination`.

---

### Task 16: `api/health/` ou justification (#516)

**Files:**
- Inspect: `backend/app/api/routes_health.py`

- [ ] **Step 1:** Lire `routes_health.py`. S'il fait < 80 lignes et n'a ni schéma inline ni liste : le laisser plat, marquer #516 `← FINIS ✓ (date — laissé plat : module trivial sans schémas ni listes)`. Sinon, dérouler la recette des Tasks 2-15.
- [ ] **Step 2:** Commit (`docs` ou `refactor` selon le cas).

---

### Task 17: Cycle d'import main.py (#517)

**Files:**
- Inspect/Modify: `backend/app/main.py`

- [ ] **Step 1: Reproduire** — graphify signale `main.py -> main.py`. Chercher les imports tardifs/locaux : `Select-String -Path backend/app/main.py -Pattern 'import'`. Identifier tout import de `app.main` depuis un module importé par `main.py` (`Select-String -Path backend/app -Pattern 'from app.main|import app.main' -Recurse`).
- [ ] **Step 2: Corriger** — déplacer la dépendance fautive vers `app/core/` (le besoin typique : accéder à `app`/settings → passer par `app.core.config` ou une injection). Si aucune occurrence réelle (faux positif graphify sur un import conditionnel), marquer l'item `← FINIS ✓ (faux positif : <explication>)`.
- [ ] **Step 3: Vert global** — `python -m pytest -q` (suite complète backend) → PASS.
- [ ] **Step 4: Commit + marquage.**

---

### Task 18: Clôture du chantier

- [ ] **Step 1: Suite complète** — `cd backend; python -m pytest -q` → PASS.
- [ ] **Step 2: Vérifier qu'aucun `routes_*.py` ne reste** (sauf décision #516) : `Get-ChildItem backend/app/api -Filter routes_*.py`.
- [ ] **Step 3: Régénérer les types front** — `make gen-types` (le contrat n'a pas bougé, le diff doit être vide ; sinon, investiguer avant de continuer).
- [ ] **Step 4: Commit final éventuel** (types régénérés) + passage au plan du Chantier 2.
