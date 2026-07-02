# Module Skincare — Implementation Plan (Phase 1/6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer un module Skincare autonome (produits, routines AM/PM ordonnées, fréquence par produit, stock/péremption/coût) avec API + UI, prêt à alimenter l'orchestrateur hebdomadaire des phases suivantes.

**Architecture:** On suit le pattern des modules existants (ex. habitudes/livres) : modèles SQLModel → migration Alembic → couche service (logique pure testable) → routes FastAPI → tests d'intégration in-memory → lib + composant frontend. Aucune dépendance au solveur (phases 3+).

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest (backend) ; Next.js 15 (App Router), React 19, TypeScript (frontend).

**Conventions repérées (à respecter) :**
- Modèles dans `app/models/<module>.py`, enregistrés dans `app/models/__init__.py`.
- Services dans `app/services/<module>/`, logique pure sans web.
- Routes dans `app/api/routes_<module>.py`, montées dans `app/api/__init__.py` avec `prefix="/<module>"`.
- Tests d'intégration : `TestClient` + SQLite `StaticPool` in-memory + override de `get_session` (voir `tests/test_etudes/test_api.py`).
- Front : `frontend/lib/<module>.ts` (fetch relatif `"/api/<module>"`), composant `frontend/components/<module>/`, page `frontend/src/app/<module>/page.tsx` + `loading.tsx`, entrée dans `frontend/lib/modules.ts`.

---

### Task 1 : Modèles SkincareProduct + SkincareLog

**Files:**
- Create: `backend/app/models/skincare.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_skincare/test_models.py` (+ `backend/tests/test_skincare/__init__.py`)

- [ ] **Step 1: Écrire le test qui échoue**

Create `backend/tests/test_skincare/__init__.py` (vide) et `backend/tests/test_skincare/test_models.py` :

```python
from app.models.skincare import SkincareProduct, SkincareLog


def test_skincare_product_defaults():
    p = SkincareProduct(nom="Sérum vitamine C", type="serum", moment="AM")
    assert p.ordre == 0
    assert p.frequence_type == "quotidien"
    assert p.actif is True
    assert p.cout == 0.0


def test_skincare_log_fields():
    log = SkincareLog(date_jour=__import__("datetime").date(2026, 6, 2), moment="PM", produits_ids="1,2,3")
    assert log.moment == "PM"
    assert log.produits_ids == "1,2,3"
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_models.py -q`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.models.skincare'`

- [ ] **Step 3: Créer les modèles**

Create `backend/app/models/skincare.py` :

```python
import datetime as dt
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint


class SkincareProduct(SQLModel, table=True):
    __tablename__ = "skincare_product"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    type: str = "autre"  # nettoyant|serum|hydratant|spf|exfoliant|masque|retinoide|autre
    moment: str = "AM"   # AM|PM|les_deux
    ordre: int = 0       # position dans la routine du moment
    # Fréquence
    frequence_type: str = "quotidien"  # quotidien|hebdo_jours|n_par_semaine
    frequence_jours: str | None = None  # ex. "0,3" (lun, jeu) si hebdo_jours
    frequence_n: int | None = None      # ex. 2 si n_par_semaine
    # Contraintes de placement (pour l'orchestrateur, phases suivantes)
    apres_douche: bool = False
    soir_seulement: bool = False
    pas_avant_soleil: bool = False
    duree_min: int = 2
    # Stock / péremption / coût
    stock_qte: float | None = None
    unite: str | None = None
    date_ouverture: dt.date | None = None
    date_peremption: dt.date | None = None
    cout: float = 0.0
    actif: bool = True


class SkincareLog(SQLModel, table=True):
    __tablename__ = "skincare_log"
    id: int | None = Field(default=None, primary_key=True)
    date_jour: dt.date
    moment: str  # AM|PM
    produits_ids: str = ""  # CSV des ids appliqués
    note: str | None = None
    __table_args__ = (UniqueConstraint("date_jour", "moment"),)
```

Modify `backend/app/models/__init__.py` — ajouter après la ligne `from app.models.scheduler import ...` :

```python
from app.models.skincare import SkincareProduct, SkincareLog  # noqa: F401
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_models.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/skincare.py backend/app/models/__init__.py backend/tests/test_skincare/
git commit -m "feat(skincare): modèles SkincareProduct + SkincareLog"
```

---

### Task 2 : Migration Alembic des tables skincare

**Files:**
- Create: `backend/alembic/versions/<auto>_skincare.py` (généré)
- Test: réutilise `backend/tests/test_migrations.py` (déjà présent)

- [ ] **Step 1: Générer la migration via autogenerate**

Run:
```bash
cd backend && ALEMBIC_DB_URL="sqlite:///./data/_skincaremig.db" ./.venv/Scripts/python.exe -m alembic upgrade head \
 && ALEMBIC_DB_URL="sqlite:///./data/_skincaremig.db" ./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "skincare module" \
 && rm -f ./data/_skincaremig.db
```
Expected: un fichier `alembic/versions/*_skincare_module.py` créé, contenant `op.create_table('skincare_product', ...)` et `op.create_table('skincare_log', ...)`.

- [ ] **Step 2: Vérifier le contenu de la migration**

Ouvrir le fichier généré. Confirmer qu'il crée bien `skincare_product` et `skincare_log` (et **aucune** suppression de table existante). Supprimer toute opération parasite `alter_column` de type TEXT→AutoString si présente.

- [ ] **Step 3: Lancer le test de contrôle des migrations**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_migrations.py -q`
Expected: PASS (1 passed) — le schéma issu de `upgrade head` correspond aux modèles.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(skincare): migration Alembic des tables skincare"
```

---

### Task 3 : Logique de fréquence (pure, testable)

**Files:**
- Create: `backend/app/services/skincare/__init__.py` (vide)
- Create: `backend/app/services/skincare/frequency.py`
- Test: `backend/tests/test_skincare/test_frequency.py`

- [ ] **Step 1: Écrire le test qui échoue**

Create `backend/tests/test_skincare/test_frequency.py` :

```python
import datetime as dt
from app.models.skincare import SkincareProduct
from app.services.skincare.frequency import is_due_on, is_flexible

# 2026-06-01 est un lundi (weekday 0), 2026-06-04 est un jeudi (weekday 3)
LUNDI = dt.date(2026, 6, 1)
MARDI = dt.date(2026, 6, 2)
JEUDI = dt.date(2026, 6, 4)


def test_quotidien_due_every_day():
    p = SkincareProduct(nom="x", frequence_type="quotidien")
    assert is_due_on(p, LUNDI) is True
    assert is_due_on(p, MARDI) is True


def test_hebdo_jours_matches_weekday():
    p = SkincareProduct(nom="x", frequence_type="hebdo_jours", frequence_jours="0,3")
    assert is_due_on(p, LUNDI) is True   # lundi = 0
    assert is_due_on(p, MARDI) is False  # mardi = 1
    assert is_due_on(p, JEUDI) is True   # jeudi = 3


def test_n_par_semaine_is_flexible_not_due_specific_day():
    p = SkincareProduct(nom="x", frequence_type="n_par_semaine", frequence_n=2)
    assert is_due_on(p, LUNDI) is False
    assert is_flexible(p) is True


def test_quotidien_not_flexible():
    p = SkincareProduct(nom="x", frequence_type="quotidien")
    assert is_flexible(p) is False
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_frequency.py -q`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.skincare.frequency'`

- [ ] **Step 3: Implémenter la logique**

Create `backend/app/services/skincare/__init__.py` (vide).
Create `backend/app/services/skincare/frequency.py` :

```python
"""Logique de fréquence des produits skincare (pure, sans DB).

- quotidien      : dû chaque jour.
- hebdo_jours    : dû les jours de semaine listés (frequence_jours, ex. "0,3").
- n_par_semaine  : flexible — la répartition exacte est décidée par
                   l'orchestrateur hebdomadaire (phases suivantes), pas ici.
"""

from __future__ import annotations

import datetime as dt

from app.models.skincare import SkincareProduct


def is_due_on(product: SkincareProduct, date: dt.date) -> bool:
    if product.frequence_type == "quotidien":
        return True
    if product.frequence_type == "hebdo_jours":
        jours = _parse_jours(product.frequence_jours)
        return date.weekday() in jours
    # n_par_semaine : pas attaché à un jour précis
    return False


def is_flexible(product: SkincareProduct) -> bool:
    """True si la fréquence ne fixe pas de jour précis (n_par_semaine)."""
    return product.frequence_type == "n_par_semaine"


def _parse_jours(raw: str | None) -> set[int]:
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_frequency.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/skincare/ backend/tests/test_skincare/test_frequency.py
git commit -m "feat(skincare): logique de fréquence (quotidien/hebdo/n_par_semaine)"
```

---

### Task 4 : Service produits (CRUD) + routine du jour + rachat

**Files:**
- Create: `backend/app/services/skincare/products.py`
- Test: `backend/tests/test_skincare/test_products.py`

- [ ] **Step 1: Écrire le test qui échoue**

Create `backend/tests/test_skincare/test_products.py` :

```python
import datetime as dt
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.models.skincare import SkincareProduct
from app.services.skincare import products as svc


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_and_list(session):
    svc.create_product(session, {"nom": "Nettoyant", "type": "nettoyant", "moment": "AM", "ordre": 0})
    svc.create_product(session, {"nom": "Hydratant", "type": "hydratant", "moment": "AM", "ordre": 1})
    items = svc.list_products(session)
    assert [p.nom for p in items] == ["Nettoyant", "Hydratant"]  # triés par moment puis ordre


def test_routine_for_moment_is_ordered(session):
    svc.create_product(session, {"nom": "B", "moment": "PM", "ordre": 2})
    svc.create_product(session, {"nom": "A", "moment": "PM", "ordre": 1})
    routine = svc.routine_for(session, "PM")
    assert [p.nom for p in routine] == ["A", "B"]


def test_due_today_excludes_inactive_and_wrong_weekday(session):
    # 2026-06-02 = mardi (weekday 1)
    svc.create_product(session, {"nom": "Quotidien", "moment": "AM", "frequence_type": "quotidien"})
    svc.create_product(session, {"nom": "Lundi seulement", "moment": "AM",
                                 "frequence_type": "hebdo_jours", "frequence_jours": "0"})
    due = svc.due_on(session, dt.date(2026, 6, 2))
    noms = {p.nom for p in due}
    assert "Quotidien" in noms
    assert "Lundi seulement" not in noms


def test_products_to_repurchase_flags_low_stock_and_expired(session):
    svc.create_product(session, {"nom": "Presque vide", "stock_qte": 0.0})
    svc.create_product(session, {"nom": "Périmé", "stock_qte": 5.0,
                                 "date_peremption": dt.date(2020, 1, 1)})
    svc.create_product(session, {"nom": "OK", "stock_qte": 5.0})
    noms = {p.nom for p in svc.to_repurchase(session, today=dt.date(2026, 6, 2))}
    assert noms == {"Presque vide", "Périmé"}
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_products.py -q`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.skincare.products'`

- [ ] **Step 3: Implémenter le service**

Create `backend/app/services/skincare/products.py` :

```python
"""Service produits skincare : CRUD, routine ordonnée, dû du jour, rachat."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.skincare import SkincareProduct
from app.services.skincare.frequency import is_due_on


def list_products(session: Session, *, actifs_only: bool = True) -> list[SkincareProduct]:
    q = select(SkincareProduct)
    if actifs_only:
        q = q.where(SkincareProduct.actif == True)  # noqa: E712
    q = q.order_by(SkincareProduct.moment, SkincareProduct.ordre)
    return list(session.exec(q).all())


def create_product(session: Session, data: dict) -> SkincareProduct:
    p = SkincareProduct(**data)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def update_product(session: Session, product_id: int, data: dict) -> SkincareProduct | None:
    p = session.get(SkincareProduct, product_id)
    if not p:
        return None
    for k, v in data.items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def delete_product(session: Session, product_id: int) -> bool:
    """Suppression logique (actif=False)."""
    p = session.get(SkincareProduct, product_id)
    if not p:
        return False
    p.actif = False
    session.add(p)
    session.commit()
    return True


def routine_for(session: Session, moment: str) -> list[SkincareProduct]:
    """Produits actifs d'un moment (AM/PM), dans l'ordre d'application.
    Inclut les produits 'les_deux'."""
    q = (
        select(SkincareProduct)
        .where(SkincareProduct.actif == True)  # noqa: E712
        .where(SkincareProduct.moment.in_([moment, "les_deux"]))  # type: ignore[attr-defined]
        .order_by(SkincareProduct.ordre)
    )
    return list(session.exec(q).all())


def due_on(session: Session, date: dt.date) -> list[SkincareProduct]:
    """Produits actifs dus à une date (hors n_par_semaine, géré par l'orchestrateur)."""
    return [p for p in list_products(session) if is_due_on(p, date)]


def to_repurchase(session: Session, today: dt.date | None = None) -> list[SkincareProduct]:
    """Produits à racheter : stock épuisé (<=0) ou périmés."""
    today = today or dt.date.today()
    out: list[SkincareProduct] = []
    for p in list_products(session):
        low = p.stock_qte is not None and p.stock_qte <= 0
        expired = p.date_peremption is not None and p.date_peremption < today
        if low or expired:
            out.append(p)
    return out
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_products.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/skincare/products.py backend/tests/test_skincare/test_products.py
git commit -m "feat(skincare): service produits (CRUD, routine, dû du jour, rachat)"
```

---

### Task 5 : Routes FastAPI + montage du routeur

**Files:**
- Create: `backend/app/api/routes_skincare.py`
- Modify: `backend/app/api/__init__.py`
- Test: couvert par Task 6

- [ ] **Step 1: Créer le routeur**

Create `backend/app/api/routes_skincare.py` :

```python
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.models.skincare import SkincareLog
from app.services.skincare import products as svc

router = APIRouter(prefix="", tags=["skincare"])


class ProductCreate(BaseModel):
    nom: str
    type: str = "autre"
    moment: str = "AM"
    ordre: int = 0
    frequence_type: str = "quotidien"
    frequence_jours: str | None = None
    frequence_n: int | None = None
    apres_douche: bool = False
    soir_seulement: bool = False
    pas_avant_soleil: bool = False
    duree_min: int = 2
    stock_qte: float | None = None
    unite: str | None = None
    date_ouverture: dt.date | None = None
    date_peremption: dt.date | None = None
    cout: float = 0.0


class LogCreate(BaseModel):
    date_jour: dt.date
    moment: str
    produits_ids: str = ""
    note: str | None = None


@router.get("/ping")
def ping():
    return {"module": "skincare", "ready": True}


@router.get("/products")
def list_products(session: Session = Depends(get_session)):
    return svc.list_products(session)


@router.post("/products", status_code=201)
def create_product(body: ProductCreate, session: Session = Depends(get_session)):
    return svc.create_product(session, body.model_dump())


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: dict, session: Session = Depends(get_session)):
    p = svc.update_product(session, product_id, body)
    if not p:
        raise HTTPException(404, f"Produit {product_id} introuvable")
    return p


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    if not svc.delete_product(session, product_id):
        raise HTTPException(404, f"Produit {product_id} introuvable")


@router.get("/routine")
def routine(moment: str, session: Session = Depends(get_session)):
    if moment not in ("AM", "PM"):
        raise HTTPException(422, "moment doit être AM ou PM")
    return svc.routine_for(session, moment)


@router.get("/today")
def today(session: Session = Depends(get_session)):
    today_d = dt.date.today()
    return {
        "date": str(today_d),
        "AM": svc.routine_for(session, "AM"),
        "PM": svc.routine_for(session, "PM"),
        "due": svc.due_on(session, today_d),
    }


@router.get("/to-repurchase")
def to_repurchase(session: Session = Depends(get_session)):
    return svc.to_repurchase(session)


@router.post("/log", status_code=201)
def create_log(body: LogCreate, session: Session = Depends(get_session)):
    log = SkincareLog(**body.model_dump())
    session.add(log)
    session.commit()
    session.refresh(log)
    return log
```

- [ ] **Step 2: Monter le routeur**

Modify `backend/app/api/__init__.py` :
- Ajouter `routes_skincare,` dans le bloc d'import `from app.api import ( ... )`.
- Ajouter après la ligne du routeur notifications :

```python
api_router.include_router(routes_skincare.router, prefix="/skincare", tags=["skincare"])
```

- [ ] **Step 3: Vérifier que l'app démarre**

Run: `cd backend && ./.venv/Scripts/python.exe -c "from app.main import app; print('routes', sum('/skincare' in getattr(r,'path','') for r in app.routes))"`
Expected: affiche un nombre > 0 (les routes skincare sont montées, ×2 à cause du montage racine + /api/v1).

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes_skincare.py backend/app/api/__init__.py
git commit -m "feat(skincare): routes FastAPI + montage du routeur"
```

---

### Task 6 : Tests d'intégration API

**Files:**
- Test: `backend/tests/test_skincare/test_api.py`

- [ ] **Step 1: Écrire les tests d'intégration**

Create `backend/tests/test_skincare/test_api.py` :

```python
"""Tests d'intégration — API Skincare avec SQLite in-memory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import create_app
from app.core.db import get_session


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        yield c


def test_ping(client):
    r = client.get("/skincare/ping")
    assert r.status_code == 200
    assert r.json()["module"] == "skincare"


def test_create_list_update_delete(client):
    r = client.post("/skincare/products", json={"nom": "Sérum", "type": "serum", "moment": "AM"})
    assert r.status_code == 201
    pid = r.json()["id"]

    r = client.get("/skincare/products")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.patch(f"/skincare/products/{pid}", json={"ordre": 5})
    assert r.status_code == 200
    assert r.json()["ordre"] == 5

    r = client.delete(f"/skincare/products/{pid}")
    assert r.status_code == 204
    # suppression logique → plus dans la liste des actifs
    assert client.get("/skincare/products").json() == []


def test_routine_ordered_and_includes_les_deux(client):
    client.post("/skincare/products", json={"nom": "B", "moment": "AM", "ordre": 2})
    client.post("/skincare/products", json={"nom": "A", "moment": "AM", "ordre": 1})
    client.post("/skincare/products", json={"nom": "SPF", "moment": "les_deux", "ordre": 3})
    r = client.get("/skincare/routine?moment=AM")
    assert [p["nom"] for p in r.json()] == ["A", "B", "SPF"]


def test_today_structure(client):
    r = client.get("/skincare/today")
    body = r.json()
    assert set(body.keys()) == {"date", "AM", "PM", "due"}


def test_update_404(client):
    assert client.patch("/skincare/products/999", json={"ordre": 1}).status_code == 404
```

- [ ] **Step 2: Lancer les tests**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_api.py -q`
Expected: PASS (5 passed)

- [ ] **Step 3: Lancer toute la suite skincare**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare -q`
Expected: PASS (tous verts)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_skincare/test_api.py
git commit -m "test(skincare): tests d'intégration API"
```

---

### Task 7 : Frontend — lib/skincare.ts

**Files:**
- Create: `frontend/lib/skincare.ts`

- [ ] **Step 1: Créer le client + types**

Create `frontend/lib/skincare.ts` :

```typescript
// Types + client API pour le module Skincare (proxy Next -> backend)
const BASE = "/api/skincare";

export interface SkincareProduct {
  id: number;
  nom: string;
  type: string;
  moment: "AM" | "PM" | "les_deux";
  ordre: number;
  frequence_type: "quotidien" | "hebdo_jours" | "n_par_semaine";
  frequence_jours?: string | null;
  frequence_n?: number | null;
  apres_douche: boolean;
  soir_seulement: boolean;
  pas_avant_soleil: boolean;
  duree_min: number;
  stock_qte?: number | null;
  unite?: string | null;
  date_ouverture?: string | null;
  date_peremption?: string | null;
  cout: number;
  actif: boolean;
}

export interface SkincareToday {
  date: string;
  AM: SkincareProduct[];
  PM: SkincareProduct[];
  due: SkincareProduct[];
}

export const skincareApi = {
  list: (): Promise<SkincareProduct[]> => fetch(`${BASE}/products`).then((r) => r.json()),
  today: (): Promise<SkincareToday> => fetch(`${BASE}/today`).then((r) => r.json()),
  toRepurchase: (): Promise<SkincareProduct[]> => fetch(`${BASE}/to-repurchase`).then((r) => r.json()),
  create: (data: Partial<SkincareProduct>): Promise<SkincareProduct> =>
    fetch(`${BASE}/products`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => r.json()),
  update: (id: number, data: Partial<SkincareProduct>): Promise<SkincareProduct> =>
    fetch(`${BASE}/products/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => r.json()),
  remove: (id: number): Promise<Response> => fetch(`${BASE}/products/${id}`, { method: "DELETE" }),
};
```

- [ ] **Step 2: Vérifier le typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/skincare.ts
git commit -m "feat(skincare): client API frontend (lib/skincare.ts)"
```

---

### Task 8 : Frontend — composant, page, enregistrement du module

**Files:**
- Create: `frontend/components/skincare/Skincare.tsx`
- Create: `frontend/src/app/skincare/page.tsx`
- Create: `frontend/src/app/skincare/loading.tsx`
- Modify: `frontend/lib/modules.ts`

- [ ] **Step 1: Créer le composant**

Create `frontend/components/skincare/Skincare.tsx` :

```tsx
"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { skincareApi, type SkincareProduct, type SkincareToday } from "@/lib/skincare";

export function Skincare() {
  const [today, setToday] = useState<SkincareToday | null>(null);
  const [repurchase, setRepurchase] = useState<SkincareProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([skincareApi.today(), skincareApi.toRepurchase()])
      .then(([t, r]) => {
        setToday(t);
        setRepurchase(r);
      })
      .catch((e) => setError(e?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-[var(--destructive)]">⚠ {error}</div>;

  const renderRoutine = (label: string, items: SkincareProduct[]) => (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold tracking-tight">{label}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucun produit.</p>
      ) : (
        <ol className="space-y-1.5">
          {items.map((p, i) => (
            <li
              key={p.id}
              className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm card-hover"
            >
              <span className="text-xs text-[var(--muted-foreground)] w-5">{i + 1}.</span>
              <span className="font-medium">{p.nom}</span>
              <span className="text-xs text-[var(--muted-foreground)]">· {p.type}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 shrink-0" />
          <h1 className="text-xl font-semibold tracking-tight">Skincare</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Routines &amp; produits</p>
      </div>

      <div className="p-6 grid gap-6 sm:grid-cols-2 animate-fade-in-up">
        {renderRoutine("Routine matin (AM)", today?.AM ?? [])}
        {renderRoutine("Routine soir (PM)", today?.PM ?? [])}
      </div>

      {repurchase.length > 0 && (
        <div className="px-6 pb-6">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-sm font-semibold mb-2">À racheter</h2>
            <ul className="text-sm text-[var(--muted-foreground)] space-y-1">
              {repurchase.map((p) => (
                <li key={p.id}>• {p.nom}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Créer la page + loading**

Create `frontend/src/app/skincare/page.tsx` :

```tsx
import { Skincare } from "@/components/skincare/Skincare";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export default function SkincarePage() {
  return (
    <ErrorBoundary label="Skincare">
      <Skincare />
    </ErrorBoundary>
  );
}
```

Create `frontend/src/app/skincare/loading.tsx` :

```tsx
import PageSkeleton from "@/components/PageSkeleton";

export default function Loading() {
  return <PageSkeleton />;
}
```

- [ ] **Step 3: Enregistrer le module dans la liste**

Modify `frontend/lib/modules.ts` :
- Ajouter `Sparkles` à l'import depuis `lucide-react` (ordre alphabétique).
- Ajouter une entrée dans le tableau `MODULES` :

```typescript
  {
    slug: "skincare",
    label: "Skincare",
    description: "Routines matin/soir, produits, fréquence.",
    icon: Sparkles,
    conv: "CONV 6",
    ready: true,
  },
```

- [ ] **Step 4: Vérifier le typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/skincare/ frontend/src/app/skincare/ frontend/lib/modules.ts
git commit -m "feat(skincare): page, composant routines AM/PM + à racheter, enregistrement module"
```

---

### Task 9 : Données de démo (seed) + mise à jour du graphe

**Files:**
- Modify: `backend/app/services/skincare/products.py` (ajout `seed_skincare`)
- Modify: `backend/app/main.py` (appel du seed au démarrage, dans le `lifespan`)
- Test: `backend/tests/test_skincare/test_seed.py`

- [ ] **Step 1: Écrire le test du seed**

Create `backend/tests/test_skincare/test_seed.py` :

```python
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.skincare.products import seed_skincare, list_products


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_seed_is_idempotent(session):
    seed_skincare(session)
    n1 = len(list_products(session))
    seed_skincare(session)
    n2 = len(list_products(session))
    assert n1 > 0
    assert n1 == n2  # pas de doublons au second appel
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare/test_seed.py -q`
Expected: FAIL avec `ImportError: cannot import name 'seed_skincare'`

- [ ] **Step 3: Implémenter le seed**

Ajouter à la fin de `backend/app/services/skincare/products.py` :

```python
DEFAULT_PRODUCTS = [
    {"nom": "Nettoyant doux", "type": "nettoyant", "moment": "les_deux", "ordre": 0},
    {"nom": "Sérum vitamine C", "type": "serum", "moment": "AM", "ordre": 1},
    {"nom": "Hydratant", "type": "hydratant", "moment": "les_deux", "ordre": 2},
    {"nom": "SPF 50", "type": "spf", "moment": "AM", "ordre": 3, "pas_avant_soleil": False},
    {"nom": "Rétinoïde", "type": "retinoide", "moment": "PM", "ordre": 4, "soir_seulement": True,
     "frequence_type": "n_par_semaine", "frequence_n": 3},
    {"nom": "Exfoliant", "type": "exfoliant", "moment": "PM", "ordre": 5,
     "frequence_type": "n_par_semaine", "frequence_n": 2},
]


def seed_skincare(session: Session) -> None:
    """Insère des produits de démo si la table est vide (idempotent)."""
    existing = session.exec(select(SkincareProduct)).first()
    if existing:
        return
    for data in DEFAULT_PRODUCTS:
        session.add(SkincareProduct(**data))
    session.commit()
```

- [ ] **Step 4: Brancher le seed au démarrage**

Modify `backend/app/main.py` — dans `lifespan`, après le bloc `Seed habitudes par défaut`, ajouter :

```python
        # Seed produits skincare par défaut
        try:
            from app.services.skincare.products import seed_skincare
            seed_skincare(session)
        except Exception as exc:
            log.warning("Seed skincare: %s", exc)
```

- [ ] **Step 5: Lancer le test + la suite complète skincare**

Run: `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare -q`
Expected: PASS (tous verts)

- [ ] **Step 6: Mettre à jour le graphe de code**

Run: `graphify update .`
Expected: « Code graph updated ».

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/skincare/products.py backend/app/main.py backend/tests/test_skincare/test_seed.py orchestration/graphify/
git commit -m "feat(skincare): seed de démo + branchement au démarrage"
```

---

## Vérification finale (après toutes les tâches)

- [ ] `cd backend && ./.venv/Scripts/python.exe -m pytest tests/test_skincare tests/test_migrations.py -q` → tout vert
- [ ] `cd frontend && npx tsc --noEmit` → aucune erreur
- [ ] Lancer l'app (`make dev`) et ouvrir `/skincare` → routines AM/PM affichées, section « À racheter » visible si stock/péremption.

## Notes pour les phases suivantes (hors périmètre de ce plan)
- Les champs `apres_douche`, `soir_seulement`, `pas_avant_soleil`, `duree_min`, et la fréquence `n_par_semaine` sont **persistés mais pas encore exploités** : ils alimenteront le solveur (Phase 3) et les contributors (Phase 4).
- `SkincareLog` est créable via l'API mais l'UI de complétion détaillée viendra avec la vue « Ma semaine » (Phase 6).
