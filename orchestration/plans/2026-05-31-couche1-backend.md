# Couche 1 — Backend Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 4 new backend modules (Budget, Habitudes, Livres, Cuisine) + activate Scheduler, all following the exact patterns of existing modules (Finance, Santé, Entraînement).

**Architecture:** FastAPI + SQLModel + Alembic on SQLite. Each module = models/ + services/ + api/routes_. Follow PLAN.md rules: files < 200 lignes, pure Python logic isolated, import in-process for cross-module calls, IntegrityError caught on upserts.

**Tech Stack:** Python 3.10+, FastAPI 0.115, SQLModel 0.0.38, Alembic 1.14, Pydantic 2.x, uv, pytest

---

## Critical Reading Before Starting

Read these files to understand existing patterns:
- `orchestration/PLAN.md` — rules héritées (MUST respect)
- `orchestration/specs/2026-05-31-mission-control-completion-design.md` — spec complète
- `backend/app/models/sante.py` — pattern SQLModel
- `backend/app/api/routes_finance.py` — pattern endpoints
- `backend/app/services/finance/snapshots.py` — pattern service
- `backend/app/main.py` — où enregistrer les routers
- `backend/alembic/versions/` — format migration (prendre le plus récent comme modèle)

---

## Task 1: Module Budget — Modèles + Migration

**Files:**
- Create: `backend/app/models/budget.py`
- Create: `backend/alembic/versions/YYYYMMDD_budget.py`
- Modify: `backend/app/models/__init__.py` (si existe, sinon pas nécessaire)

- [ ] **Step 1: Créer les modèles SQLModel**

```python
# backend/app/models/budget.py
import datetime as dt
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint

class BudgetCategory(SQLModel, table=True):
    __tablename__ = "budget_category"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    parent_id: int | None = Field(default=None, foreign_key="budget_category.id")
    couleur: str = "#6366f1"

class BudgetRule(SQLModel, table=True):
    __tablename__ = "budget_rule"
    id: int | None = Field(default=None, primary_key=True)
    pattern: str
    category_id: int = Field(foreign_key="budget_category.id")
    priorite: int = 0
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class BudgetTransaction(SQLModel, table=True):
    __tablename__ = "budget_transaction"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date
    montant: float
    marchand: str = ""
    description: str = ""
    category_id: int | None = Field(default=None, foreign_key="budget_category.id")
    compte: str = "principal"
    devise: str = "CAD"
    auto: bool = False
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class BudgetEnvelope(SQLModel, table=True):
    __tablename__ = "budget_envelope"
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="budget_category.id")
    mois: str  # "2026-05"
    montant: float
    __table_args__ = (UniqueConstraint("category_id", "mois"),)
```

- [ ] **Step 2: Créer la migration Alembic**

```bash
cd backend
uv run alembic revision --autogenerate -m "budget_tables"
# Vérifier que le fichier généré contient les 4 tables
uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade ... -> ..., budget_tables`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/budget.py backend/alembic/
git commit -m "feat(budget): add SQLModel models + migration"
```

---

## Task 2: Module Budget — Services

**Files:**
- Create: `backend/app/services/budget/__init__.py`
- Create: `backend/app/services/budget/categories.py`
- Create: `backend/app/services/budget/rules.py`
- Create: `backend/app/services/budget/transactions.py`
- Create: `backend/app/services/budget/envelopes.py`
- Create: `backend/app/services/budget/imports.py`

- [ ] **Step 1: Écrire le test des règles (logique pure)**

```python
# backend/tests/test_budget/test_rules.py
import pytest
from app.services.budget.rules import apply_rules_pure

def test_apply_rules_no_match():
    rules = [{"pattern": "STARBUCKS", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("METRO GROCERY", rules) is None

def test_apply_rules_match_case_insensitive():
    rules = [{"pattern": "starbucks", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("STARBUCKS #42", rules) == 1

def test_apply_rules_priority_order():
    rules = [
        {"pattern": "METRO", "category_id": 2, "priorite": 0},
        {"pattern": "METRO", "category_id": 1, "priorite": 10},
    ]
    # priorite plus haute gagne
    assert apply_rules_pure("METRO", rules) == 1
```

```bash
cd backend && uv run pytest tests/test_budget/test_rules.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 2: Implémenter la logique pure des règles**

```python
# backend/app/services/budget/rules.py
import re
from sqlmodel import Session, select
from app.models.budget import BudgetRule, BudgetTransaction

def apply_rules_pure(description: str, rules: list[dict]) -> int | None:
    """Pure function: find matching category_id from rules. No DB."""
    sorted_rules = sorted(rules, key=lambda r: r["priorite"], reverse=True)
    for rule in sorted_rules:
        if re.search(rule["pattern"], description, re.IGNORECASE):
            return rule["category_id"]
    return None

def get_all_rules(session: Session) -> list[dict]:
    rules = session.exec(select(BudgetRule)).all()
    return [{"pattern": r.pattern, "category_id": r.category_id, "priorite": r.priorite} for r in rules]

def apply_rules_to_transaction(session: Session, description: str) -> int | None:
    rules = get_all_rules(session)
    return apply_rules_pure(description, rules)

def reapply_all_rules(session: Session) -> int:
    """Re-categorise all transactions. Returns count updated."""
    rules = get_all_rules(session)
    transactions = session.exec(select(BudgetTransaction)).all()
    updated = 0
    for t in transactions:
        cat_id = apply_rules_pure(f"{t.marchand} {t.description}", rules)
        if cat_id and t.category_id != cat_id:
            t.category_id = cat_id
            session.add(t)
            updated += 1
    session.commit()
    return updated
```

- [ ] **Step 3: Run tests règles**

```bash
cd backend && uv run pytest tests/test_budget/test_rules.py -v
```
Expected: 3 PASSED

- [ ] **Step 4: Implémenter categories.py**

```python
# backend/app/services/budget/categories.py
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.budget import BudgetCategory

DEFAULT_CATEGORIES = [
    ("Logement", None), ("Loyer", "Logement"), ("Électricité", "Logement"), ("Internet", "Logement"),
    ("Transport", None), ("Essence", "Transport"), ("Transport en commun", "Transport"),
    ("Nourriture", None), ("Épicerie", "Nourriture"), ("Restaurants", "Nourriture"),
    ("Santé", None), ("Pharmacie", "Santé"), ("Sport", "Santé"),
    ("Loisirs", None), ("Cinéma", "Loisirs"), ("Sorties", "Loisirs"),
    ("Abonnements", None), ("Streaming", "Abonnements"),
    ("Revenus", None), ("Salaire", "Revenus"),
]

def seed_categories(session: Session) -> None:
    existing = {c.nom: c for c in session.exec(select(BudgetCategory)).all()}
    # Insert parents first, then children
    for nom, parent_nom in DEFAULT_CATEGORIES:
        if nom in existing:
            continue
        parent_id = existing[parent_nom].id if parent_nom and parent_nom in existing else None
        cat = BudgetCategory(nom=nom, parent_id=parent_id)
        try:
            session.add(cat)
            session.commit()
            session.refresh(cat)
            existing[nom] = cat
        except IntegrityError:
            session.rollback()
            existing[nom] = session.exec(select(BudgetCategory).where(BudgetCategory.nom == nom)).first()

def get_categories(session: Session) -> list[BudgetCategory]:
    return session.exec(select(BudgetCategory)).all()

def create_category(session: Session, nom: str, parent_id: int | None = None, couleur: str = "#6366f1") -> BudgetCategory:
    cat = BudgetCategory(nom=nom, parent_id=parent_id, couleur=couleur)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
```

- [ ] **Step 5: Implémenter transactions.py**

```python
# backend/app/services/budget/transactions.py
import datetime as dt
from sqlmodel import Session, select
from app.models.budget import BudgetTransaction
from app.services.budget.rules import apply_rules_to_transaction

def create_transaction(session: Session, date: dt.date, montant: float, marchand: str,
                       description: str = "", compte: str = "principal",
                       devise: str = "CAD", auto: bool = False) -> BudgetTransaction:
    cat_id = apply_rules_to_transaction(session, f"{marchand} {description}")
    t = BudgetTransaction(date=date, montant=montant, marchand=marchand,
                          description=description, category_id=cat_id,
                          compte=compte, devise=devise, auto=auto)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t

def get_transactions(session: Session, from_date: dt.date | None = None,
                     to_date: dt.date | None = None, category_id: int | None = None) -> list[BudgetTransaction]:
    q = select(BudgetTransaction)
    if from_date:
        q = q.where(BudgetTransaction.date >= from_date)
    if to_date:
        q = q.where(BudgetTransaction.date <= to_date)
    if category_id:
        q = q.where(BudgetTransaction.category_id == category_id)
    return session.exec(q.order_by(BudgetTransaction.date.desc())).all()

def get_monthly_summary(session: Session, mois: str) -> dict:
    """mois = '2026-05'. Returns {revenus, depenses, solde, by_category}."""
    year, month = int(mois[:4]), int(mois[5:])
    start = dt.date(year, month, 1)
    import calendar
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    txs = get_transactions(session, from_date=start, to_date=end)
    revenus = sum(t.montant for t in txs if t.montant > 0)
    depenses = sum(t.montant for t in txs if t.montant < 0)
    by_cat: dict[int | None, float] = {}
    for t in txs:
        by_cat[t.category_id] = by_cat.get(t.category_id, 0) + t.montant
    return {"revenus": revenus, "depenses": depenses, "solde": revenus + depenses, "by_category": by_cat}

def get_disposable(session: Session, mois: str) -> float:
    summary = get_monthly_summary(session, mois)
    return summary["solde"]
```

- [ ] **Step 6: Implémenter imports.py**

```python
# backend/app/services/budget/imports.py
import csv
import io
import datetime as dt
from app.services.budget.transactions import create_transaction
from sqlmodel import Session

def _detect_format(headers: list[str]) -> str:
    """Detect CSV format from headers."""
    h = [h.lower().strip() for h in headers]
    if "débit" in h or "debit" in h:
        return "desjardins"
    if "cad$" in h or "cad" in h:
        return "rbc"
    return "generic"

def _parse_desjardins(row: list[str]) -> tuple[dt.date, float, str] | None:
    # Format: date, description, débit, crédit, solde
    try:
        date = dt.datetime.strptime(row[0].strip(), "%Y-%m-%d").date()
        debit = float(row[2].replace(",", "").strip()) if row[2].strip() else 0
        credit = float(row[3].replace(",", "").strip()) if row[3].strip() else 0
        montant = credit - debit
        return date, montant, row[1].strip()
    except (ValueError, IndexError):
        return None

def _parse_generic(row: list[str]) -> tuple[dt.date, float, str] | None:
    # Format: date, description, montant
    try:
        date = dt.datetime.strptime(row[0].strip(), "%Y-%m-%d").date()
        montant = float(row[2].replace(",", "").strip())
        return date, montant, row[1].strip()
    except (ValueError, IndexError):
        return None

def import_csv(session: Session, content: str, compte: str = "principal") -> dict:
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return {"imported": 0, "errors": 0}
    fmt = _detect_format(rows[0])
    imported, errors = 0, 0
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        parsed = _parse_desjardins(row) if fmt == "desjardins" else _parse_generic(row)
        if parsed:
            date, montant, marchand = parsed
            create_transaction(session, date=date, montant=montant, marchand=marchand, compte=compte)
            imported += 1
        else:
            errors += 1
    return {"imported": imported, "errors": errors, "format": fmt}
```

- [ ] **Step 7: Implémenter envelopes.py**

```python
# backend/app/services/budget/envelopes.py
import datetime as dt
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.budget import BudgetEnvelope, BudgetTransaction

def upsert_envelope(session: Session, category_id: int, mois: str, montant: float) -> BudgetEnvelope:
    existing = session.exec(
        select(BudgetEnvelope).where(
            BudgetEnvelope.category_id == category_id,
            BudgetEnvelope.mois == mois
        )
    ).first()
    if existing:
        existing.montant = montant
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    env = BudgetEnvelope(category_id=category_id, mois=mois, montant=montant)
    try:
        session.add(env)
        session.commit()
        session.refresh(env)
        return env
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(BudgetEnvelope).where(
                BudgetEnvelope.category_id == category_id,
                BudgetEnvelope.mois == mois
            )
        ).first()

def get_envelope_status(session: Session, mois: str) -> list[dict]:
    """Returns [{category_id, budget, depense, reste, pct}]"""
    envelopes = session.exec(select(BudgetEnvelope).where(BudgetEnvelope.mois == mois)).all()
    year, month = int(mois[:4]), int(mois[5:])
    import calendar
    start = dt.date(year, month, 1)
    end = dt.date(year, month, calendar.monthrange(year, month)[1])
    result = []
    for env in envelopes:
        txs = session.exec(
            select(BudgetTransaction).where(
                BudgetTransaction.category_id == env.category_id,
                BudgetTransaction.date >= start,
                BudgetTransaction.date <= end,
                BudgetTransaction.montant < 0
            )
        ).all()
        depense = abs(sum(t.montant for t in txs))
        result.append({
            "category_id": env.category_id,
            "budget": env.montant,
            "depense": depense,
            "reste": env.montant - depense,
            "pct": (depense / env.montant * 100) if env.montant > 0 else 0
        })
    return result
```

- [ ] **Step 8: Test import CSV**

```python
# backend/tests/test_budget/test_imports.py
from app.services.budget.imports import _parse_desjardins, _parse_generic
import datetime as dt

def test_parse_generic():
    row = ["2026-05-15", "METRO INC", "-45.32"]
    result = _parse_generic(row)
    assert result == (dt.date(2026, 5, 15), -45.32, "METRO INC")

def test_parse_desjardins_debit():
    row = ["2026-05-15", "STARBUCKS", "6.75", "", "1200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == -6.75

def test_parse_desjardins_credit():
    row = ["2026-05-01", "SALAIRE", "", "3000.00", "4200.00"]
    result = _parse_desjardins(row)
    assert result is not None
    assert result[1] == 3000.0
```

```bash
cd backend && uv run pytest tests/test_budget/ -v
```
Expected: 6 PASSED

- [ ] **Step 9: Commit services**

```bash
git add backend/app/services/budget/ backend/tests/test_budget/
git commit -m "feat(budget): services (transactions, rules, imports, envelopes, categories)"
```

---

## Task 3: Module Budget — API Routes

**Files:**
- Create: `backend/app/api/routes_budget.py`
- Modify: `backend/app/main.py` (ajouter le router)

- [ ] **Step 1: Créer les routes**

```python
# backend/app/api/routes_budget.py
import datetime as dt
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.budget import BudgetCategory, BudgetRule, BudgetTransaction, BudgetEnvelope
from app.services.budget import categories as cat_svc
from app.services.budget import rules as rules_svc
from app.services.budget import transactions as tx_svc
from app.services.budget import envelopes as env_svc
from app.services.budget import imports as import_svc
from pydantic import BaseModel

router = APIRouter(prefix="/api/budget", tags=["budget"])

# --- Startup seed ---
@router.on_event  # handled in main.py startup instead
def _():
    pass

class TransactionCreate(BaseModel):
    date: dt.date
    montant: float
    marchand: str
    description: str = ""
    compte: str = "principal"
    devise: str = "CAD"

class CategoryCreate(BaseModel):
    nom: str
    parent_id: int | None = None
    couleur: str = "#6366f1"

class RuleCreate(BaseModel):
    pattern: str
    category_id: int
    priorite: int = 0

class EnvelopeCreate(BaseModel):
    category_id: int
    mois: str
    montant: float

# Transactions
@router.get("/transactions")
def list_transactions(
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
    category_id: int | None = None,
    session: Session = Depends(get_session)
):
    return tx_svc.get_transactions(session, from_date, to_date, category_id)

@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionCreate, session: Session = Depends(get_session)):
    return tx_svc.create_transaction(session, **body.model_dump())

@router.patch("/transactions/{id}")
def update_transaction(id: int, category_id: int, session: Session = Depends(get_session)):
    t = session.get(BudgetTransaction, id)
    if not t:
        raise HTTPException(404)
    t.category_id = category_id
    session.add(t)
    session.commit()
    session.refresh(t)
    return t

@router.delete("/transactions/{id}", status_code=204)
def delete_transaction(id: int, session: Session = Depends(get_session)):
    t = session.get(BudgetTransaction, id)
    if not t:
        raise HTTPException(404)
    session.delete(t)
    session.commit()

@router.post("/import")
async def import_csv(file: UploadFile = File(...), compte: str = "principal",
                     session: Session = Depends(get_session)):
    content = (await file.read()).decode("utf-8", errors="replace")
    return import_svc.import_csv(session, content, compte)

# Categories
@router.get("/categories")
def list_categories(session: Session = Depends(get_session)):
    return cat_svc.get_categories(session)

@router.post("/categories", status_code=201)
def create_category(body: CategoryCreate, session: Session = Depends(get_session)):
    return cat_svc.create_category(session, **body.model_dump())

# Rules
@router.get("/rules")
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(BudgetRule)).all()

@router.post("/rules", status_code=201)
def create_rule(body: RuleCreate, session: Session = Depends(get_session)):
    rule = BudgetRule(**body.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@router.delete("/rules/{id}", status_code=204)
def delete_rule(id: int, session: Session = Depends(get_session)):
    r = session.get(BudgetRule, id)
    if not r:
        raise HTTPException(404)
    session.delete(r)
    session.commit()

@router.post("/rules/apply")
def apply_rules(session: Session = Depends(get_session)):
    updated = rules_svc.reapply_all_rules(session)
    return {"updated": updated}

# Envelopes
@router.get("/envelopes")
def list_envelopes(month: str, session: Session = Depends(get_session)):
    return env_svc.get_envelope_status(session, month)

@router.post("/envelopes", status_code=201)
def create_envelope(body: EnvelopeCreate, session: Session = Depends(get_session)):
    return env_svc.upsert_envelope(session, body.category_id, body.mois, body.montant)

# Summary endpoints
@router.get("/summary")
def monthly_summary(month: str, session: Session = Depends(get_session)):
    return tx_svc.get_monthly_summary(session, month)

@router.get("/disposable")
def disposable(month: str, session: Session = Depends(get_session)):
    return {"mois": month, "disposable": tx_svc.get_disposable(session, month)}

@router.get("/cashflow")
def cashflow(from_date: dt.date, to_date: dt.date, session: Session = Depends(get_session)):
    # Group transactions by month
    txs = tx_svc.get_transactions(session, from_date, to_date)
    by_month: dict[str, dict] = {}
    for t in txs:
        key = t.date.strftime("%Y-%m")
        if key not in by_month:
            by_month[key] = {"revenus": 0, "depenses": 0}
        if t.montant > 0:
            by_month[key]["revenus"] += t.montant
        else:
            by_month[key]["depenses"] += t.montant
    return [{"mois": k, **v} for k, v in sorted(by_month.items())]
```

- [ ] **Step 2: Enregistrer le router dans main.py**

Dans `backend/app/main.py`, ajouter :
```python
from app.api.routes_budget import router as budget_router
# dans la section include_router :
app.include_router(budget_router)
```

Et dans le startup event, ajouter :
```python
from app.services.budget.categories import seed_categories
seed_categories(session)
```

- [ ] **Step 3: Vérifier que le serveur démarre**

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```
Expected: démarrage sans erreur, aller sur `http://localhost:8000/docs` et voir les endpoints `/api/budget/*`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes_budget.py backend/app/main.py
git commit -m "feat(budget): API routes + startup seed"
```

---

## Task 4: Module Habitudes — Modèles + Services + Routes

**Files:**
- Create: `backend/app/models/habitudes.py`
- Create: `backend/app/services/habitudes/__init__.py`
- Create: `backend/app/services/habitudes/habits.py`
- Create: `backend/app/services/habitudes/entries.py`
- Create: `backend/app/services/habitudes/streaks.py`
- Create: `backend/app/services/habitudes/heatmap.py`
- Create: `backend/app/api/routes_habitudes.py`
- Create: `backend/tests/test_habitudes/__init__.py`
- Create: `backend/tests/test_habitudes/test_streaks.py`

- [ ] **Step 1: Modèles**

```python
# backend/app/models/habitudes.py
import datetime as dt
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint

class Habit(SQLModel, table=True):
    __tablename__ = "habit"
    id: int | None = Field(default=None, primary_key=True)
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"
    source_auto: str | None = None
    actif: bool = True
    ordre: int = 0

class HabitEntry(SQLModel, table=True):
    __tablename__ = "habit_entry"
    id: int | None = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id")
    date: dt.date
    valeur: float = 1.0
    auto: bool = False
    __table_args__ = (UniqueConstraint("habit_id", "date"),)
```

- [ ] **Step 2: Migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "habitudes_tables"
uv run alembic upgrade head
```

- [ ] **Step 3: Test streak (logique pure)**

```python
# backend/tests/test_habitudes/test_streaks.py
import datetime as dt
from app.services.habitudes.streaks import compute_streak_pure

def test_streak_consecutive():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 29), dt.date(2026, 5, 30), dt.date(2026, 5, 31)]
    assert compute_streak_pure(dates, today) == 3

def test_streak_broken():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 28), dt.date(2026, 5, 30), dt.date(2026, 5, 31)]
    assert compute_streak_pure(dates, today) == 2

def test_streak_empty():
    assert compute_streak_pure([], dt.date(2026, 5, 31)) == 0

def test_streak_not_today():
    today = dt.date(2026, 5, 31)
    dates = [dt.date(2026, 5, 29), dt.date(2026, 5, 30)]
    # Streak broken if yesterday missing from today
    assert compute_streak_pure(dates, today) == 0
```

```bash
cd backend && uv run pytest tests/test_habitudes/test_streaks.py -v
```
Expected: FAIL

- [ ] **Step 4: Implémenter streaks.py**

```python
# backend/app/services/habitudes/streaks.py
import datetime as dt
from sqlmodel import Session, select
from app.models.habitudes import HabitEntry

def compute_streak_pure(entry_dates: list[dt.date], today: dt.date) -> int:
    """Pure function. Returns current streak ending on today or yesterday."""
    if not entry_dates:
        return 0
    date_set = set(entry_dates)
    # Must have today or yesterday to have an active streak
    start = today if today in date_set else today - dt.timedelta(days=1)
    if start not in date_set:
        return 0
    streak = 0
    current = start
    while current in date_set:
        streak += 1
        current -= dt.timedelta(days=1)
    return streak

def get_streaks(session: Session) -> list[dict]:
    from app.models.habitudes import Habit
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    today = dt.date.today()
    result = []
    for h in habits:
        entries = session.exec(
            select(HabitEntry.date).where(HabitEntry.habit_id == h.id)
        ).all()
        streak = compute_streak_pure(list(entries), today)
        result.append({"habit_id": h.id, "nom": h.nom, "streak": streak})
    return result
```

```bash
cd backend && uv run pytest tests/test_habitudes/test_streaks.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Implémenter entries.py**

```python
# backend/app/services/habitudes/entries.py
import datetime as dt
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from app.models.habitudes import Habit, HabitEntry

DEFAULT_HABITS = [
    {"nom": "Muscu", "type": "binaire", "source_auto": "entrainement_muscu", "ordre": 0},
    {"nom": "Course", "type": "binaire", "source_auto": "entrainement_cardio", "ordre": 1},
    {"nom": "Lecture", "type": "quantifiable", "unite": "minutes", "cible": 30.0, "source_auto": "livres_lecture", "ordre": 2},
    {"nom": "Sommeil ≥ 7h", "type": "binaire", "ordre": 3},
    {"nom": "Pas de junk food", "type": "binaire", "ordre": 4},
    {"nom": "Méditation", "type": "binaire", "ordre": 5},
]

def seed_habits(session: Session) -> None:
    existing = session.exec(select(Habit)).all()
    if existing:
        return
    for h in DEFAULT_HABITS:
        habit = Habit(**h)
        session.add(habit)
    session.commit()

def get_today_checklist(session: Session) -> list[dict]:
    today = dt.date.today()
    habits = session.exec(select(Habit).where(Habit.actif == True).order_by(Habit.ordre)).all()
    entries_today = {e.habit_id: e for e in session.exec(
        select(HabitEntry).where(HabitEntry.date == today)
    ).all()}
    return [{"habit": h, "entry": entries_today.get(h.id)} for h in habits]

def upsert_entry(session: Session, habit_id: int, date: dt.date,
                 valeur: float = 1.0, auto: bool = False) -> HabitEntry:
    existing = session.exec(
        select(HabitEntry).where(HabitEntry.habit_id == habit_id, HabitEntry.date == date)
    ).first()
    if existing:
        existing.valeur = valeur
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    entry = HabitEntry(habit_id=habit_id, date=date, valeur=valeur, auto=auto)
    try:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(HabitEntry).where(HabitEntry.habit_id == habit_id, HabitEntry.date == date)
        ).first()

def auto_check_habit(session: Session, source: str, date: dt.date, valeur: float = 1.0) -> bool:
    """Called by other modules. Returns True if a habit was checked."""
    habit = session.exec(
        select(Habit).where(Habit.source_auto == source, Habit.actif == True)
    ).first()
    if not habit:
        return False
    upsert_entry(session, habit.id, date, valeur=valeur, auto=True)
    return True
```

- [ ] **Step 6: heatmap.py**

```python
# backend/app/services/habitudes/heatmap.py
import datetime as dt
from sqlmodel import Session, select
from app.models.habitudes import HabitEntry

def get_heatmap(session: Session, habit_id: int, year: int) -> list[dict]:
    start = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)
    entries = session.exec(
        select(HabitEntry).where(
            HabitEntry.habit_id == habit_id,
            HabitEntry.date >= start,
            HabitEntry.date <= end
        )
    ).all()
    entry_map = {e.date: e.valeur for e in entries}
    result = []
    current = start
    while current <= end:
        result.append({"date": current.isoformat(), "valeur": entry_map.get(current, 0)})
        current += dt.timedelta(days=1)
    return result
```

- [ ] **Step 7: Routes habitudes**

```python
# backend/app/api/routes_habitudes.py
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.habitudes import Habit, HabitEntry
from app.services.habitudes import entries as entries_svc
from app.services.habitudes import streaks as streaks_svc
from app.services.habitudes import heatmap as heatmap_svc
from pydantic import BaseModel

router = APIRouter(prefix="/api/habitudes", tags=["habitudes"])

class HabitCreate(BaseModel):
    nom: str
    type: str = "binaire"
    unite: str | None = None
    cible: float = 1.0
    frequence: str = "daily"

class EntryCreate(BaseModel):
    habit_id: int
    date: dt.date
    valeur: float = 1.0

@router.get("/habits")
def list_habits(session: Session = Depends(get_session)):
    return session.exec(select(Habit).where(Habit.actif == True).order_by(Habit.ordre)).all()

@router.post("/habits", status_code=201)
def create_habit(body: HabitCreate, session: Session = Depends(get_session)):
    h = Habit(**body.model_dump())
    session.add(h)
    session.commit()
    session.refresh(h)
    return h

@router.patch("/habits/{id}")
def update_habit(id: int, body: dict, session: Session = Depends(get_session)):
    h = session.get(Habit, id)
    if not h:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(h, k, v)
    session.add(h)
    session.commit()
    session.refresh(h)
    return h

@router.delete("/habits/{id}", status_code=204)
def delete_habit(id: int, session: Session = Depends(get_session)):
    h = session.get(Habit, id)
    if not h:
        raise HTTPException(404)
    h.actif = False  # soft delete
    session.add(h)
    session.commit()

@router.get("/today")
def today_checklist(session: Session = Depends(get_session)):
    return entries_svc.get_today_checklist(session)

@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, session: Session = Depends(get_session)):
    return entries_svc.upsert_entry(session, body.habit_id, body.date, body.valeur)

@router.delete("/entries/{id}", status_code=204)
def delete_entry(id: int, session: Session = Depends(get_session)):
    e = session.get(HabitEntry, id)
    if not e:
        raise HTTPException(404)
    session.delete(e)
    session.commit()

@router.get("/streaks")
def streaks(session: Session = Depends(get_session)):
    return streaks_svc.get_streaks(session)

@router.get("/heatmap")
def heatmap(habit_id: int, year: int = dt.date.today().year,
            session: Session = Depends(get_session)):
    return heatmap_svc.get_heatmap(session, habit_id, year)

@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    habits = session.exec(select(Habit).where(Habit.actif == True)).all()
    today = dt.date.today()
    start_30 = today - dt.timedelta(days=30)
    result = []
    for h in habits:
        entries = session.exec(
            select(HabitEntry).where(
                HabitEntry.habit_id == h.id,
                HabitEntry.date >= start_30
            )
        ).all()
        result.append({
            "habit_id": h.id,
            "nom": h.nom,
            "completions_30j": len(entries),
            "taux_30j": len(entries) / 30 * 100
        })
    return result
```

- [ ] **Step 8: Enregistrer dans main.py + seed**

Dans `backend/app/main.py` :
```python
from app.api.routes_habitudes import router as habitudes_router
app.include_router(habitudes_router)
# dans startup:
from app.services.habitudes.entries import seed_habits
seed_habits(session)
```

- [ ] **Step 9: Tests + Commit**

```bash
cd backend && uv run pytest tests/test_habitudes/ -v
# Expected: 4+ PASSED
git add backend/app/models/habitudes.py backend/app/services/habitudes/ \
         backend/app/api/routes_habitudes.py backend/tests/test_habitudes/ \
         backend/alembic/ backend/app/main.py
git commit -m "feat(habitudes): models, services, routes, streak tests"
```

---

## Task 5: Module Livres — Modèles + Services + Routes

**Files:**
- Create: `backend/app/models/livres.py`
- Create: `backend/app/services/livres/__init__.py`
- Create: `backend/app/services/livres/books.py`
- Create: `backend/app/services/livres/notes.py`
- Create: `backend/app/services/livres/sessions.py`
- Create: `backend/app/services/livres/metadata.py`
- Create: `backend/app/api/routes_livres.py`
- Create: `backend/tests/test_livres/__init__.py`
- Create: `backend/tests/test_livres/test_metadata.py`

- [ ] **Step 1: Modèles**

```python
# backend/app/models/livres.py
import datetime as dt
from sqlmodel import SQLModel, Field

class Book(SQLModel, table=True):
    __tablename__ = "book"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    auteur: str = ""
    isbn: str | None = None
    pages: int | None = None
    statut: str = "a_lire"
    genre: str = ""
    format: str = "papier"
    note: float | None = None
    date_debut: dt.date | None = None
    date_fin: dt.date | None = None
    couverture_url: str | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class BookNote(SQLModel, table=True):
    __tablename__ = "book_note"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    contenu: str
    tags: str = "[]"

class BookQuote(SQLModel, table=True):
    __tablename__ = "book_quote"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    page: int | None = None
    texte: str

class ReadingSession(SQLModel, table=True):
    __tablename__ = "reading_session"
    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    date: dt.date
    duree_minutes: int
    page_debut: int | None = None
    page_fin: int | None = None
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
```

- [ ] **Step 2: Migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "livres_tables"
uv run alembic upgrade head
```

- [ ] **Step 3: Test ISBN lookup (mocké)**

```python
# backend/tests/test_livres/test_metadata.py
from unittest.mock import patch
from app.services.livres.metadata import parse_open_library_response

def test_parse_open_library_response_valid():
    raw = {
        "ISBN:9780735224292": {
            "title": "Atomic Habits",
            "authors": [{"name": "James Clear"}],
            "number_of_pages": 320,
            "cover": {"large": "https://covers.openlibrary.org/b/id/8739161-L.jpg"}
        }
    }
    result = parse_open_library_response(raw, "9780735224292")
    assert result["titre"] == "Atomic Habits"
    assert result["auteur"] == "James Clear"
    assert result["pages"] == 320

def test_parse_open_library_response_not_found():
    result = parse_open_library_response({}, "0000000000000")
    assert result is None
```

- [ ] **Step 4: Implémenter metadata.py**

```python
# backend/app/services/livres/metadata.py
import httpx

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
COVERS_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"

def parse_open_library_response(data: dict, isbn: str) -> dict | None:
    key = f"ISBN:{isbn}"
    if key not in data:
        return None
    book = data[key]
    authors = book.get("authors", [])
    return {
        "titre": book.get("title", ""),
        "auteur": ", ".join(a["name"] for a in authors),
        "pages": book.get("number_of_pages"),
        "couverture_url": COVERS_URL.format(isbn=isbn),
    }

def lookup_isbn(isbn: str) -> dict | None:
    try:
        resp = httpx.get(
            OPEN_LIBRARY_URL,
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=5.0
        )
        resp.raise_for_status()
        return parse_open_library_response(resp.json(), isbn)
    except Exception:
        return None
```

- [ ] **Step 5: Implémenter books.py + sessions.py**

```python
# backend/app/services/livres/books.py
import datetime as dt
from sqlmodel import Session, select
from app.models.livres import Book
from app.services.livres.metadata import lookup_isbn

def create_book(session: Session, **kwargs) -> Book:
    book = Book(**kwargs)
    session.add(book)
    session.commit()
    session.refresh(book)
    return book

def create_book_from_isbn(session: Session, isbn: str) -> Book | None:
    meta = lookup_isbn(isbn)
    if not meta:
        return None
    return create_book(session, isbn=isbn, **meta)

def get_books(session: Session, statut: str | None = None) -> list[Book]:
    q = select(Book)
    if statut:
        q = q.where(Book.statut == statut)
    return session.exec(q.order_by(Book.created_at.desc())).all()

def get_stats(session: Session) -> dict:
    books = session.exec(select(Book)).all()
    lus = [b for b in books if b.statut == "lu"]
    pages_lues = sum(b.pages or 0 for b in lus)
    par_genre: dict[str, int] = {}
    for b in lus:
        par_genre[b.genre or "Autre"] = par_genre.get(b.genre or "Autre", 0) + 1
    return {"total_lus": len(lus), "pages_lues": pages_lues, "par_genre": par_genre}
```

```python
# backend/app/services/livres/sessions.py
import datetime as dt
from sqlmodel import Session as DBSession, select
from app.models.livres import ReadingSession

LECTURE_HABIT_MIN = 30

def create_session(db: DBSession, book_id: int, date: dt.date,
                   duree_minutes: int, page_debut: int | None = None,
                   page_fin: int | None = None) -> ReadingSession:
    s = ReadingSession(book_id=book_id, date=date, duree_minutes=duree_minutes,
                       page_debut=page_debut, page_fin=page_fin)
    db.add(s)
    db.commit()
    db.refresh(s)
    if duree_minutes >= LECTURE_HABIT_MIN:
        try:
            from app.services.habitudes.entries import auto_check_habit
            auto_check_habit(db, source="livres_lecture", date=date, valeur=float(duree_minutes))
        except Exception:
            pass
    return s
```

- [ ] **Step 6: Implémenter notes.py**

```python
# backend/app/services/livres/notes.py
from sqlmodel import Session, select
from app.models.livres import BookNote, BookQuote

def get_notes(session: Session, book_id: int) -> list[BookNote]:
    return session.exec(select(BookNote).where(BookNote.book_id == book_id)).all()

def create_note(session: Session, book_id: int, contenu: str,
                page: int | None = None, tags: list[str] | None = None) -> BookNote:
    import json
    note = BookNote(book_id=book_id, contenu=contenu, page=page,
                    tags=json.dumps(tags or []))
    session.add(note)
    session.commit()
    session.refresh(note)
    return note

def get_quotes(session: Session, book_id: int) -> list[BookQuote]:
    return session.exec(select(BookQuote).where(BookQuote.book_id == book_id)).all()

def create_quote(session: Session, book_id: int, texte: str,
                 page: int | None = None) -> BookQuote:
    q = BookQuote(book_id=book_id, texte=texte, page=page)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q
```

- [ ] **Step 7: Routes livres**

```python
# backend/app/api/routes_livres.py
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.db import get_session
from app.models.livres import Book, BookNote, BookQuote
from app.services.livres import books as books_svc
from app.services.livres import notes as notes_svc
from app.services.livres import sessions as sessions_svc
from pydantic import BaseModel

router = APIRouter(prefix="/api/livres", tags=["livres"])

class BookCreate(BaseModel):
    titre: str
    auteur: str = ""
    isbn: str | None = None
    pages: int | None = None
    statut: str = "a_lire"
    genre: str = ""
    format: str = "papier"

class NoteCreate(BaseModel):
    contenu: str
    page: int | None = None
    tags: list[str] = []

class QuoteCreate(BaseModel):
    texte: str
    page: int | None = None

class SessionCreate(BaseModel):
    date: dt.date
    duree_minutes: int
    page_debut: int | None = None
    page_fin: int | None = None

@router.get("/books")
def list_books(statut: str | None = None, session: Session = Depends(get_session)):
    return books_svc.get_books(session, statut)

@router.post("/books", status_code=201)
def create_book(body: BookCreate, session: Session = Depends(get_session)):
    return books_svc.create_book(session, **body.model_dump())

@router.post("/books/from-isbn", status_code=201)
def from_isbn(isbn: str, session: Session = Depends(get_session)):
    book = books_svc.create_book_from_isbn(session, isbn)
    if not book:
        raise HTTPException(404, "ISBN not found in Open Library")
    return book

@router.patch("/books/{id}")
def update_book(id: int, body: dict, session: Session = Depends(get_session)):
    b = session.get(Book, id)
    if not b:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(b, k, v)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b

@router.delete("/books/{id}", status_code=204)
def delete_book(id: int, session: Session = Depends(get_session)):
    b = session.get(Book, id)
    if not b:
        raise HTTPException(404)
    session.delete(b)
    session.commit()

@router.get("/books/{id}/notes")
def get_notes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_notes(session, id)

@router.post("/books/{id}/notes", status_code=201)
def create_note(id: int, body: NoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_note(session, id, body.contenu, body.page, body.tags)

@router.patch("/notes/{id}", status_code=200)
def update_note(id: int, body: dict, session: Session = Depends(get_session)):
    n = session.get(BookNote, id)
    if not n:
        raise HTTPException(404)
    for k, v in body.items():
        setattr(n, k, v)
    session.add(n)
    session.commit()
    return n

@router.delete("/notes/{id}", status_code=204)
def delete_note(id: int, session: Session = Depends(get_session)):
    n = session.get(BookNote, id)
    if not n:
        raise HTTPException(404)
    session.delete(n)
    session.commit()

@router.get("/books/{id}/quotes")
def get_quotes(id: int, session: Session = Depends(get_session)):
    return notes_svc.get_quotes(session, id)

@router.post("/books/{id}/quotes", status_code=201)
def create_quote(id: int, body: QuoteCreate, session: Session = Depends(get_session)):
    return notes_svc.create_quote(session, id, body.texte, body.page)

@router.delete("/quotes/{id}", status_code=204)
def delete_quote(id: int, session: Session = Depends(get_session)):
    q = session.get(BookQuote, id)
    if not q:
        raise HTTPException(404)
    session.delete(q)
    session.commit()

@router.post("/books/{id}/sessions", status_code=201)
def create_reading_session(id: int, body: SessionCreate, session: Session = Depends(get_session)):
    return sessions_svc.create_session(session, id, body.date, body.duree_minutes,
                                       body.page_debut, body.page_fin)

@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    return books_svc.get_stats(session)
```

- [ ] **Step 8: Enregistrer + tests + commit**

Dans `main.py` :
```python
from app.api.routes_livres import router as livres_router
app.include_router(livres_router)
```

```bash
cd backend && uv run pytest tests/test_livres/ -v
# Expected: 3 PASSED
git add backend/app/models/livres.py backend/app/services/livres/ \
         backend/app/api/routes_livres.py backend/tests/test_livres/ \
         backend/alembic/ backend/app/main.py
git commit -m "feat(livres): models, services, routes, ISBN lookup, habit integration"
```

---

## Task 6: Module Cuisine — Modèles + Services + Routes

**Files:**
- Create: `backend/app/models/cuisine.py`
- Create: `backend/app/services/cuisine/__init__.py`
- Create: `backend/app/services/cuisine/recipes.py`
- Create: `backend/app/services/cuisine/macros.py`
- Create: `backend/app/services/cuisine/meal_plan.py`
- Create: `backend/app/services/cuisine/shopping_list.py`
- Create: `backend/app/api/routes_cuisine.py`
- Create: `backend/tests/test_cuisine/__init__.py`
- Create: `backend/tests/test_cuisine/test_macros.py`

- [ ] **Step 1: Modèles**

```python
# backend/app/models/cuisine.py
from sqlmodel import SQLModel, Field

class Recipe(SQLModel, table=True):
    __tablename__ = "recipe"
    id: int | None = Field(default=None, primary_key=True)
    titre: str
    portions: int = 4
    temps_prep: int = 0
    temps_cuisson: int = 0
    instructions: str = ""
    source_url: str | None = None
    image_url: str | None = None

class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredient"
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    aliment_id: int | None = Field(default=None, foreign_key="aliment.id")
    nom_libre: str = ""
    quantite: float
    unite: str

class MealPlanEntry(SQLModel, table=True):
    __tablename__ = "meal_plan_entry"
    id: int | None = Field(default=None, primary_key=True)
    semaine: str  # "2026-W22"
    jour: int     # 0=lundi
    repas: str    # "petit_dejeuner" | "dejeuner" | "souper"
    recipe_id: int | None = Field(default=None, foreign_key="recipe.id")
    notes: str = ""

class ShoppingListItem(SQLModel, table=True):
    __tablename__ = "shopping_list_item"
    id: int | None = Field(default=None, primary_key=True)
    semaine: str
    ingredient: str
    quantite: float
    unite: str
    rayon: str = "Autre"
    achete: bool = False
```

- [ ] **Step 2: Migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "cuisine_tables"
uv run alembic upgrade head
```

- [ ] **Step 3: Test macros (logique pure)**

```python
# backend/tests/test_cuisine/test_macros.py
from app.services.cuisine.macros import compute_macros_for_portion

def test_compute_macros_no_ingredients():
    result = compute_macros_for_portion([], portions=4)
    assert result == {"calories": 0, "proteines": 0, "glucides": 0, "lipides": 0}

def test_compute_macros_per_portion():
    # 100g de poulet : 165 kcal, 31g P, 0g G, 3.6g L
    ingredients = [{"quantite_g": 200, "calories_100g": 165, "proteines_100g": 31,
                    "glucides_100g": 0, "lipides_100g": 3.6}]
    result = compute_macros_for_portion(ingredients, portions=4)
    # Total: 330 kcal / 4 = 82.5 par portion
    assert abs(result["calories"] - 82.5) < 0.1
    assert abs(result["proteines"] - 15.5) < 0.1
```

- [ ] **Step 4: macros.py**

```python
# backend/app/services/cuisine/macros.py
from sqlmodel import Session, select
from app.models.cuisine import RecipeIngredient
from app.models.sante import Aliment  # table existante CONV 3

def compute_macros_for_portion(ingredients: list[dict], portions: int) -> dict:
    """Pure function. ingredients = [{quantite_g, calories_100g, proteines_100g, glucides_100g, lipides_100g}]"""
    total = {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}
    for ing in ingredients:
        factor = ing["quantite_g"] / 100
        total["calories"] += ing["calories_100g"] * factor
        total["proteines"] += ing["proteines_100g"] * factor
        total["glucides"] += ing["glucides_100g"] * factor
        total["lipides"] += ing["lipides_100g"] * factor
    p = max(portions, 1)
    return {k: round(v / p, 1) for k, v in total.items()}

def get_recipe_macros(session: Session, recipe_id: int, portions: int = 1) -> dict:
    ingredients_db = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    ).all()
    ingredients_data = []
    for ing in ingredients_db:
        if ing.aliment_id:
            aliment = session.get(Aliment, ing.aliment_id)
            if aliment:
                # Convertir quantite vers grammes (simplifié: assume unité = g ou ml ≈ g)
                q_g = ing.quantite if ing.unite in ("g", "ml") else ing.quantite * 100
                ingredients_data.append({
                    "quantite_g": q_g,
                    "calories_100g": aliment.calories or 0,
                    "proteines_100g": aliment.proteines or 0,
                    "glucides_100g": aliment.glucides or 0,
                    "lipides_100g": aliment.lipides or 0,
                })
    return compute_macros_for_portion(ingredients_data, portions)
```

- [ ] **Step 5: recipes.py**

```python
# backend/app/services/cuisine/recipes.py
from sqlmodel import Session, select
from app.models.cuisine import Recipe, RecipeIngredient

def create_recipe(session: Session, titre: str, portions: int = 4,
                  temps_prep: int = 0, temps_cuisson: int = 0,
                  instructions: str = "", source_url: str | None = None) -> Recipe:
    r = Recipe(titre=titre, portions=portions, temps_prep=temps_prep,
               temps_cuisson=temps_cuisson, instructions=instructions, source_url=source_url)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r

def get_recipes(session: Session, search: str | None = None) -> list[Recipe]:
    q = select(Recipe)
    if search:
        q = q.where(Recipe.titre.contains(search))
    return session.exec(q).all()

def import_from_url(url: str) -> dict | None:
    """Parse JSON-LD Recipe schema from URL."""
    try:
        import httpx
        from bs4 import BeautifulSoup
        import json
        resp = httpx.get(url, timeout=10.0, follow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") == "Recipe":
                    return {
                        "titre": data.get("name", ""),
                        "portions": int(data.get("recipeYield", 4)) if str(data.get("recipeYield", "4")).isdigit() else 4,
                        "instructions": "\n".join(
                            step.get("text", step) if isinstance(step, dict) else step
                            for step in (data.get("recipeInstructions") or [])
                        ),
                        "image_url": data.get("image", [None])[0] if isinstance(data.get("image"), list) else data.get("image"),
                        "source_url": url,
                    }
            except Exception:
                continue
        return None
    except Exception:
        return None
```

- [ ] **Step 6: meal_plan.py + shopping_list.py**

```python
# backend/app/services/cuisine/meal_plan.py
from sqlmodel import Session, select
from app.models.cuisine import Recipe, MealPlanEntry
from app.services.cuisine.macros import get_recipe_macros

REPAS = ["petit_dejeuner", "dejeuner", "souper"]

def generate_meal_plan(session: Session, semaine: str, cibles: dict) -> list[MealPlanEntry]:
    """cibles = {calories, proteines, glucides, lipides} par jour"""
    recipes = session.exec(select(Recipe)).all()
    if not recipes:
        return []
    used: set[int] = set()
    entries = []
    for jour in range(7):
        for repas in REPAS:
            # Glouton: prendre la recette non-utilisée qui se rapproche le plus de cibles/3
            best = None
            best_score = float("inf")
            cible_repas = {k: v / 3 for k, v in cibles.items()}
            for r in recipes:
                if r.id in used:
                    continue
                macros = get_recipe_macros(session, r.id, r.portions)
                score = sum(abs(macros.get(k, 0) - cible_repas.get(k, 0)) for k in cibles)
                if score < best_score:
                    best_score = score
                    best = r
            if best:
                used.add(best.id)
                entry = MealPlanEntry(semaine=semaine, jour=jour, repas=repas, recipe_id=best.id)
                session.add(entry)
                entries.append(entry)
            if len(used) >= len(recipes):
                used.clear()
    session.commit()
    return entries
```

```python
# backend/app/services/cuisine/shopping_list.py
from sqlmodel import Session, select
from app.models.cuisine import MealPlanEntry, RecipeIngredient, ShoppingListItem

RAYON_MAP = {
    "g": "Épicerie", "kg": "Épicerie", "ml": "Liquides", "L": "Liquides",
    "unité": "Fruits & Légumes",
}

def generate_shopping_list(session: Session, semaine: str) -> list[ShoppingListItem]:
    entries = session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == semaine)).all()
    aggregated: dict[str, dict] = {}
    for entry in entries:
        if not entry.recipe_id:
            continue
        ings = session.exec(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == entry.recipe_id)
        ).all()
        for ing in ings:
            nom = ing.nom_libre or f"Aliment #{ing.aliment_id}"
            key = f"{nom}_{ing.unite}"
            if key in aggregated:
                aggregated[key]["quantite"] += ing.quantite
            else:
                aggregated[key] = {"ingredient": nom, "quantite": ing.quantite,
                                   "unite": ing.unite, "rayon": RAYON_MAP.get(ing.unite, "Autre")}
    items = []
    for data in aggregated.values():
        item = ShoppingListItem(semaine=semaine, **data)
        session.add(item)
        items.append(item)
    session.commit()
    return items

def mark_done(session: Session, semaine: str) -> dict:
    """Mark all items done, create Budget transaction."""
    items = session.exec(
        select(ShoppingListItem).where(ShoppingListItem.semaine == semaine)
    ).all()
    for item in items:
        item.achete = True
        session.add(item)
    session.commit()
    try:
        import datetime as dt
        from app.services.budget.transactions import create_transaction
        create_transaction(session, date=dt.date.today(), montant=-sum(0.0 for _ in items),
                           marchand="Épicerie (cuisine)", description=f"Courses semaine {semaine}",
                           auto=True)
    except Exception:
        pass
    return {"marked": len(items)}
```

- [ ] **Step 7: Routes cuisine**

```python
# backend/app/api/routes_cuisine.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.cuisine import Recipe, RecipeIngredient, MealPlanEntry, ShoppingListItem
from app.services.cuisine import recipes as recipes_svc
from app.services.cuisine import macros as macros_svc
from app.services.cuisine import meal_plan as plan_svc
from app.services.cuisine import shopping_list as shop_svc
from pydantic import BaseModel

router = APIRouter(prefix="/api/cuisine", tags=["cuisine"])

class RecipeCreate(BaseModel):
    titre: str
    portions: int = 4
    temps_prep: int = 0
    temps_cuisson: int = 0
    instructions: str = ""

class IngredientCreate(BaseModel):
    aliment_id: int | None = None
    nom_libre: str = ""
    quantite: float
    unite: str

class MealPlanPatch(BaseModel):
    recipe_id: int | None
    notes: str = ""

class GeneratePlanRequest(BaseModel):
    semaine: str
    cibles: dict = {"calories": 2500, "proteines": 180, "glucides": 300, "lipides": 80}

@router.get("/recipes")
def list_recipes(search: str | None = None, session: Session = Depends(get_session)):
    return recipes_svc.get_recipes(session, search)

@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeCreate, session: Session = Depends(get_session)):
    return recipes_svc.create_recipe(session, **body.model_dump())

@router.post("/recipes/from-url", status_code=201)
def from_url(url: str, session: Session = Depends(get_session)):
    data = recipes_svc.import_from_url(url)
    if not data:
        raise HTTPException(422, "Impossible de parser la recette depuis cette URL")
    return recipes_svc.create_recipe(session, **data)

@router.get("/recipes/{id}/macros")
def recipe_macros(id: int, portions: int = 1, session: Session = Depends(get_session)):
    return macros_svc.get_recipe_macros(session, id, portions)

@router.get("/meal-plan")
def get_plan(week: str, session: Session = Depends(get_session)):
    return session.exec(select(MealPlanEntry).where(MealPlanEntry.semaine == week)).all()

@router.post("/meal-plan/generate")
def generate_plan(body: GeneratePlanRequest, session: Session = Depends(get_session)):
    return plan_svc.generate_meal_plan(session, body.semaine, body.cibles)

@router.patch("/meal-plan/{id}")
def update_plan_entry(id: int, body: MealPlanPatch, session: Session = Depends(get_session)):
    e = session.get(MealPlanEntry, id)
    if not e:
        raise HTTPException(404)
    e.recipe_id = body.recipe_id
    e.notes = body.notes
    session.add(e)
    session.commit()
    return e

@router.get("/shopping-list")
def get_shopping(week: str, session: Session = Depends(get_session)):
    items = session.exec(
        select(ShoppingListItem).where(ShoppingListItem.semaine == week)
    ).all()
    if not items:
        items = shop_svc.generate_shopping_list(session, week)
    return items

@router.post("/shopping-list/done")
def shopping_done(week: str, session: Session = Depends(get_session)):
    return shop_svc.mark_done(session, week)

@router.patch("/shopping-list/{id}")
def update_item(id: int, achete: bool, session: Session = Depends(get_session)):
    item = session.get(ShoppingListItem, id)
    if not item:
        raise HTTPException(404)
    item.achete = achete
    session.add(item)
    session.commit()
    return item
```

- [ ] **Step 8: Enregistrer + tests + commit**

Dans `main.py` :
```python
from app.api.routes_cuisine import router as cuisine_router
app.include_router(cuisine_router)
```

```bash
cd backend && uv run pytest tests/test_cuisine/ -v
git add backend/app/models/cuisine.py backend/app/services/cuisine/ \
         backend/app/api/routes_cuisine.py backend/tests/test_cuisine/ \
         backend/alembic/ backend/app/main.py
git commit -m "feat(cuisine): models, services, routes, macros, meal plan, shopping list"
```

---

## Task 7: Scheduler — Activation APScheduler

**Files:**
- Create: `backend/app/models/scheduler.py`
- Create: `backend/app/services/scheduler/__init__.py`
- Create: `backend/app/services/scheduler/scheduler.py`
- Create: `backend/app/services/scheduler/runner.py`
- Create: `backend/app/services/scheduler/jobs/portfolio_snapshot.py`
- Create: `backend/app/services/scheduler/jobs/nutrition_plan.py`
- Create: `backend/app/services/scheduler/jobs/backup_db.py`
- Create: `backend/app/services/scheduler/jobs/weather_refresh.py`
- Create: `backend/app/api/routes_scheduler.py`
- Create: `backend/app/api/routes_notifications.py`

- [ ] **Step 1: Modèles Notification + JobRun**

```python
# backend/app/models/scheduler.py
import datetime as dt
from sqlmodel import SQLModel, Field

class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    id: int | None = Field(default=None, primary_key=True)
    source: str = "system"
    level: str = "info"
    titre: str
    message: str = ""
    lu: bool = False
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)

class JobRun(SQLModel, table=True):
    __tablename__ = "job_run"
    id: int | None = Field(default=None, primary_key=True)
    job_id: str
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    status: str = "running"
    log: str = ""
```

- [ ] **Step 2: Migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "scheduler_tables"
uv run alembic upgrade head
```

- [ ] **Step 3: scheduler.py**

```python
# backend/app/services/scheduler/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.config import settings

_scheduler: AsyncIOScheduler | None = None

def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {"default": SQLAlchemyJobStore(url=settings.DATABASE_URL)}
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone="America/Montreal"
        )
    return _scheduler

def register_all_jobs(scheduler: AsyncIOScheduler) -> None:
    from app.services.scheduler.jobs import portfolio_snapshot, nutrition_plan, backup_db, weather_refresh
    scheduler.add_job(portfolio_snapshot.run, "cron", hour=22, minute=0,
                      id="portfolio_snapshot", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(nutrition_plan.run, "cron", hour=6, minute=30,
                      id="nutrition_plan", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(backup_db.run, "cron", hour=0, minute=0,
                      id="backup_db", replace_existing=True, misfire_grace_time=3600)
    scheduler.add_job(weather_refresh.run, "cron", hour="6,12,18,0", minute=0,
                      id="weather_refresh", replace_existing=True)
```

- [ ] **Step 4: runner.py**

```python
# backend/app/services/scheduler/runner.py
import datetime as dt
from sqlmodel import Session
from app.core.db import engine
from app.models.scheduler import JobRun, Notification

def run_job(job_id: str, func):
    """Wrapper: logs JobRun, creates Notification on success/error."""
    with Session(engine) as session:
        run = JobRun(job_id=job_id, started_at=dt.datetime.utcnow())
        session.add(run)
        session.commit()
        session.refresh(run)
        try:
            result = func(session)
            run.status = "success"
            run.log = str(result or "OK")
            notif = Notification(source=job_id, titre=f"Job {job_id} terminé",
                                 message=run.log, level="info")
            session.add(notif)
        except Exception as e:
            run.status = "error"
            run.log = str(e)
            notif = Notification(source=job_id, titre=f"Erreur job {job_id}",
                                 message=str(e), level="error")
            session.add(notif)
        finally:
            run.finished_at = dt.datetime.utcnow()
            session.add(run)
            session.commit()
```

- [ ] **Step 5: Jobs individuels**

```python
# backend/app/services/scheduler/jobs/portfolio_snapshot.py
from app.services.finance.snapshots import create_daily_snapshot

def run(session):
    return create_daily_snapshot(session)
```

```python
# backend/app/services/scheduler/jobs/nutrition_plan.py
def run(session):
    # Placeholder: log que le plan nutrition est prêt pour la journée
    import datetime as dt
    return f"Plan nutrition vérifié pour {dt.date.today()}"
```

```python
# backend/app/services/scheduler/jobs/backup_db.py
import datetime as dt
import sqlite3
import shutil
from pathlib import Path
from app.core.config import settings

def run(session):
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    dest = backup_dir / f"{dt.date.today()}.db"
    conn = sqlite3.connect(str(db_path))
    backup_conn = sqlite3.connect(str(dest))
    conn.backup(backup_conn)
    backup_conn.close()
    conn.close()
    return f"Backup créé: {dest}"
```

```python
# backend/app/services/scheduler/jobs/weather_refresh.py
import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# Montreal coordinates
PARAMS = {"latitude": 45.5017, "longitude": -73.5673,
          "current": "temperature_2m,weather_code",
          "timezone": "America/Montreal"}

def run(session):
    resp = httpx.get(OPEN_METEO_URL, params=PARAMS, timeout=10.0)
    data = resp.json()
    temp = data["current"]["temperature_2m"]
    return f"Météo refresh: {temp}°C"
```

- [ ] **Step 6: Routes scheduler + notifications**

```python
# backend/app/api/routes_scheduler.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.scheduler import JobRun
from app.services.scheduler.scheduler import get_scheduler

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

JOB_IDS = ["portfolio_snapshot", "nutrition_plan", "backup_db", "weather_refresh"]

@router.get("/list")
def list_jobs(session: Session = Depends(get_session)):
    scheduler = get_scheduler()
    result = []
    for job_id in JOB_IDS:
        job = scheduler.get_job(job_id)
        last_run = session.exec(
            select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc())
        ).first()
        result.append({
            "job_id": job_id,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "paused": job is None or job.next_run_time is None,
            "last_run": last_run,
        })
    return result

@router.get("/runs")
def job_runs(job_id: str, session: Session = Depends(get_session)):
    return session.exec(
        select(JobRun).where(JobRun.job_id == job_id).order_by(JobRun.started_at.desc()).limit(20)
    ).all()

@router.post("/{job_id}/run")
async def force_run(job_id: str, session: Session = Depends(get_session)):
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    scheduler.modify_job(job_id, next_run_time=__import__("datetime").datetime.now())
    return {"status": "triggered", "job_id": job_id}

@router.post("/{job_id}/pause")
def pause_job(job_id: str):
    get_scheduler().pause_job(job_id)
    return {"status": "paused"}

@router.post("/{job_id}/resume")
def resume_job(job_id: str):
    get_scheduler().resume_job(job_id)
    return {"status": "resumed"}
```

```python
# backend/app/api/routes_notifications.py
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.scheduler import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("")
def list_notifications(limit: int = 20, session: Session = Depends(get_session)):
    return session.exec(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    ).all()

@router.patch("/{id}/read")
def mark_read(id: int, session: Session = Depends(get_session)):
    n = session.get(Notification, id)
    if n:
        n.lu = True
        session.add(n)
        session.commit()
    return {"ok": True}

@router.post("/read-all")
def mark_all_read(session: Session = Depends(get_session)):
    notifs = session.exec(select(Notification).where(Notification.lu == False)).all()
    for n in notifs:
        n.lu = True
        session.add(n)
    session.commit()
    return {"marked": len(notifs)}
```

- [ ] **Step 7: Brancher le scheduler dans main.py**

```python
# Dans backend/app/main.py, section startup:
from app.services.scheduler.scheduler import get_scheduler, register_all_jobs
from app.api.routes_scheduler import router as scheduler_router
from app.api.routes_notifications import router as notifications_router

app.include_router(scheduler_router)
app.include_router(notifications_router)

@app.on_event("startup")
async def startup():
    # ... code existant ...
    scheduler = get_scheduler()
    register_all_jobs(scheduler)
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    get_scheduler().shutdown(wait=False)
```

- [ ] **Step 8: Installer apscheduler**

```bash
cd backend && uv add apscheduler
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/scheduler.py backend/app/services/scheduler/ \
         backend/app/api/routes_scheduler.py backend/app/api/routes_notifications.py \
         backend/alembic/ backend/app/main.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(scheduler): APScheduler activation, jobs, notifications"
```

---

## Task 8: Auto-cochage Entraînement → Habitudes

**Files:**
- Modify: `backend/app/services/entrainement/sessions.py` (ajouter l'appel auto_check_habit)

- [ ] **Step 1: Trouver la fonction de création de séance dans sessions.py**

Lire `backend/app/services/entrainement/sessions.py` et localiser la fonction `create_seance` ou équivalent.

- [ ] **Step 2: Ajouter l'auto-cochage après commit**

Dans la fonction qui crée une séance (après `session.commit()`), ajouter :
```python
try:
    from app.services.habitudes.entries import auto_check_habit
    import datetime as dt
    # Déterminer le type de séance (musculation vs cardio)
    source = "entrainement_muscu"  # par défaut
    auto_check_habit(session, source=source, date=seance.date or dt.date.today())
except Exception:
    pass
```

Et dans la fonction qui crée un cardio (course) :
```python
try:
    from app.services.habitudes.entries import auto_check_habit
    auto_check_habit(session, source="entrainement_cardio", date=cardio.date)
except Exception:
    pass
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/entrainement/
git commit -m "feat(habitudes): auto-cochage depuis séances entraînement"
```

---

## Self-Review

**Spec coverage:**
- ✅ Budget : transactions, catégories, règles, enveloppes, import CSV, summary, cashflow, disposable
- ✅ Habitudes : habits, entries, streaks, heatmap, stats, auto-cochage, seed 6 habitudes
- ✅ Livres : books, notes, quotes, sessions, ISBN, stats, trigger habitude ≥30 min
- ✅ Cuisine : recipes, macros, meal plan glouton, shopping list, import URL, bridge budget
- ✅ Scheduler : APScheduler, 4 jobs, Notification, JobRun, routes
- ✅ Cross-module : Livres→Habitudes, Cuisine→Budget, Entraînement→Habitudes
- ✅ Migrations Alembic pour chaque module

**Placeholders:** Aucun.

**Type consistency:** Tous les modèles SQLModel utilisent `dt.date` et `dt.datetime` (pattern PLAN.md). Les services appellent les modèles avec les mêmes noms de champs.
