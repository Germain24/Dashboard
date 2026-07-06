# Marge de crédit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "Marge de crédit" page that, from manually-entered credit accounts/score history/profile, generates a dated action roadmap ("ask for +X at bank Y", "open account at bank Z") plus a projected total-credit-margin curve, to maximize total credit margin across all institutions by a target date (default 2028-09-01).

**Architecture:** New backend module `backend/app/services/finance/credit/` (`catalog.py` = static rules playbook with JSON override, `planner.py` = pure simulation function, `service.py` = DB CRUD + orchestration) behind a thin FastAPI router `backend/app/api/finance/credit.py`, backed by 3 new SQLModel tables + Alembic migration. New frontend module `credit` (Next.js page + `CreditTab.tsx`) following the exact `patrimoine` module conventions (React Query, hand-rolled fetch client in `lib/finance.ts`, inline-SVG chart, no new npm deps).

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, Next.js (App Router), React Query (`@tanstack/react-query`), TypeScript, Tailwind CSS vars, lucide-react.

## Global Constraints

- No external credit-bureau/banking APIs — all data (accounts, limits, score) is manually entered by the user. Do not add any new third-party API client.
- No new npm packages — charts use the existing inline-SVG idiom (see `NetWorthChart` in `PatrimoineTab.tsx`), not a charting library.
- Every new SQLModel table MUST be (a) imported in `backend/app/models/__init__.py` and (b) backed by a hand-written Alembic migration in `backend/alembic/versions/` — `backend/tests/test_migrations.py` fails the build otherwise.
- The catalog of institutions/products is heuristic/estimated data, must be clearly labeled as such in the UI, and must be overridable via `data/imports/Finances/variables/credit_catalog.json` without a redeploy (same convention as `buffett/config.py`'s `params.json`).
- No status tracking ("done"/"rejected") on recommended actions — the plan is always recomputed fresh from the user's current actual accounts/scores on every `GET /finance/credit/plan` call.
- French UI copy and code comments, consistent with the rest of the codebase.

---

### Task 1: Backend models + Alembic migration

**Files:**
- Create: `backend/app/models/credit.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260705_0000_r705creditmargin_credit_margin_tables.py`
- Test: `backend/tests/test_migrations.py` (existing, no changes needed — just must keep passing)

**Interfaces:**
- Produces: `CreditProfile(id, revenu_annuel: float, date_arrivee_canada: date, date_cible: date, nom: str | None, updated_at: datetime)`, `CreditAccount(id, institution: str, produit: str, limite_actuelle: float, date_ouverture: date, derniere_augmentation: date | None, statut: str, notes: str | None, updated_at: datetime, created_at: datetime)`, `CreditScoreEntry(id, date: date, score: int, source: str, created_at: datetime)` — all `SQLModel, table=True`, importable from `app.models.credit`.

- [ ] **Step 1: Create the models file**

Create `backend/app/models/credit.py`:
```python
"""Modèles Crédit — comptes, historique de pointage, profil (#marge-credit).

Sert le module "Marge de crédit" : feuille de route pour maximiser la marge
de crédit totale (toutes institutions) à une date cible, à partir de données
saisies manuellement (pas d'API de bureau de crédit accessible en pratique
pour un particulier).
"""

from __future__ import annotations

import datetime as dt

from sqlmodel import Field, SQLModel

from app.core.timeutil import utcnow


class CreditProfile(SQLModel, table=True):
    __tablename__ = "credit_profile"
    id: int | None = Field(default=None, primary_key=True)
    revenu_annuel: float = 0.0
    date_arrivee_canada: dt.date = Field(default_factory=lambda: dt.date.today())
    date_cible: dt.date = Field(default_factory=lambda: dt.date.today())
    nom: str | None = None
    updated_at: dt.datetime = Field(default_factory=utcnow)


class CreditAccount(SQLModel, table=True):
    __tablename__ = "credit_account"
    id: int | None = Field(default=None, primary_key=True)
    institution: str
    produit: str
    limite_actuelle: float = 0.0
    date_ouverture: dt.date
    derniere_augmentation: dt.date | None = None
    statut: str = "actif"  # "actif" | "ferme"
    notes: str | None = None
    updated_at: dt.datetime = Field(default_factory=utcnow)
    created_at: dt.datetime = Field(default_factory=utcnow)


class CreditScoreEntry(SQLModel, table=True):
    __tablename__ = "credit_score_entry"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    score: int
    source: str = ""
    created_at: dt.datetime = Field(default_factory=utcnow)
```

- [ ] **Step 2: Register the models**

In `backend/app/models/__init__.py`, add (alongside the existing `from app.models.patrimoine import ...` line):
```python
from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry  # noqa: F401
```

- [ ] **Step 3: Write the Alembic migration**

Create `backend/alembic/versions/20260705_0000_r705creditmargin_credit_margin_tables.py`:
```python
"""credit_profile / credit_account / credit_score_entry : marge de crédit (#marge-credit)

Revision ID: r705creditmargin
Revises: 763cb2d89706
Create Date: 2026-07-05 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "r705creditmargin"
down_revision = "763cb2d89706"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revenu_annuel", sa.Float(), nullable=False, server_default="0"),
        sa.Column("date_arrivee_canada", sa.Date(), nullable=False),
        sa.Column("date_cible", sa.Date(), nullable=False),
        sa.Column("nom", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credit_account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("institution", sa.String(), nullable=False),
        sa.Column("produit", sa.String(), nullable=False),
        sa.Column("limite_actuelle", sa.Float(), nullable=False, server_default="0"),
        sa.Column("date_ouverture", sa.Date(), nullable=False),
        sa.Column("derniere_augmentation", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False, server_default="actif"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credit_score_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credit_score_entry_date", "credit_score_entry", ["date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_credit_score_entry_date", table_name="credit_score_entry")
    op.drop_table("credit_score_entry")
    op.drop_table("credit_account")
    op.drop_table("credit_profile")
```

- [ ] **Step 4: Run the migration guardrail test**

Run: `cd backend && python -m pytest tests/test_migrations.py -v`
Expected: PASS (the new tables' Alembic schema matches `SQLModel.metadata` exactly).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/credit.py backend/app/models/__init__.py backend/alembic/versions/20260705_0000_r705creditmargin_credit_margin_tables.py
git commit -m "feat(credit): add CreditProfile/CreditAccount/CreditScoreEntry models + migration"
```

---

### Task 2: Catalog (playbook of institutions/products)

**Files:**
- Create: `backend/app/services/finance/credit/__init__.py` (empty)
- Create: `backend/app/services/finance/credit/catalog.py`
- Test: `backend/tests/test_finance/test_credit_catalog.py`

**Interfaces:**
- Consumes: `app.core.config.settings.imports_dir` (existing, `Path`).
- Produces: `CreditProduct` dataclass with fields `(institution: str, produit: str, type: str, limite_min: float, limite_max: float, anciennete_min_mois: int, score_min_requis: int | None, anciennete_min_avant_1ere_hausse_mois: int, cooldown_hausse_mois: int)`; `DEFAULT_CATALOG: list[CreditProduct]`; `DEFAULT_HAUSSE_RULE: CreditProduct`; `load_catalog() -> list[CreditProduct]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_finance/test_credit_catalog.py`:
```python
"""Catalogue crédit : chargement par défaut + surcharge JSON."""

import json

from app.services.finance.credit.catalog import CreditProduct, DEFAULT_CATALOG, load_catalog


def test_default_catalog_has_no_score_requirement_for_newcomer_products():
    newcomer = [p for p in DEFAULT_CATALOG if p.type == "programme_newcomer"]
    assert newcomer
    assert all(p.score_min_requis is None for p in newcomer)


def test_load_catalog_without_override_file_returns_default(tmp_path, monkeypatch):
    import app.services.finance.credit.catalog as catalog_mod
    monkeypatch.setattr(catalog_mod, "CATALOG_OVERRIDE_FILE", str(tmp_path / "missing.json"))
    result = load_catalog()
    assert result == DEFAULT_CATALOG


def test_load_catalog_with_override_file_replaces_default(tmp_path, monkeypatch):
    import app.services.finance.credit.catalog as catalog_mod
    override_path = tmp_path / "credit_catalog.json"
    override_path.write_text(json.dumps([
        {
            "institution": "Test Bank", "produit": "Carte Test", "type": "carte_standard",
            "limite_min": 100, "limite_max": 200, "anciennete_min_mois": 0,
            "score_min_requis": None, "anciennete_min_avant_1ere_hausse_mois": 6,
            "cooldown_hausse_mois": 6,
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(catalog_mod, "CATALOG_OVERRIDE_FILE", str(override_path))
    result = load_catalog()
    assert result == [CreditProduct(
        institution="Test Bank", produit="Carte Test", type="carte_standard",
        limite_min=100, limite_max=200, anciennete_min_mois=0,
        score_min_requis=None, anciennete_min_avant_1ere_hausse_mois=6,
        cooldown_hausse_mois=6,
    )]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.finance.credit'`

- [ ] **Step 3: Write the catalog module**

Create `backend/app/services/finance/credit/__init__.py` (empty file).

Create `backend/app/services/finance/credit/catalog.py`:
```python
"""Catalogue des produits de crédit candidats (#marge-credit).

Valeurs = estimations heuristiques (limites de départ typiques, ancienneté
requise, seuils de pointage) — PAS une garantie d'approbation. Surchargeable
sans redéploiement via `data/imports/Finances/variables/credit_catalog.json`
(même convention que `params.json` du Buffett, cf. buffett/config.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class CreditProduct:
    institution: str
    produit: str
    type: str  # "carte_standard" | "carte_garantie" | "programme_newcomer" | "marge_personnelle"
    limite_min: float
    limite_max: float
    anciennete_min_mois: int                       # ancienneté au Canada minimale pour être éligible
    score_min_requis: int | None                    # None = pas d'exigence (newcomer / carte garantie)
    anciennete_min_avant_1ere_hausse_mois: int       # délai avant la 1ère demande de hausse
    cooldown_hausse_mois: int                        # délai entre deux hausses une fois la 1ère obtenue


DEFAULT_CATALOG: list[CreditProduct] = [
    CreditProduct("RBC", "Carte Visa Nouveaux arrivants", "programme_newcomer", 500, 3000, 0, None, 6, 12),
    CreditProduct("Scotiabank", "StartRight Visa", "programme_newcomer", 500, 5000, 0, None, 6, 12),
    CreditProduct("Home Trust", "Secured Visa", "carte_garantie", 500, 10000, 0, None, 6, 6),
    CreditProduct("Tangerine", "World Mastercard", "carte_standard", 1000, 5000, 6, 650, 12, 12),
    CreditProduct("Banque Nationale", "Marge personnelle", "marge_personnelle", 2000, 10000, 12, 680, 12, 12),
    CreditProduct("Desjardins", "Marge personnelle", "marge_personnelle", 1000, 8000, 12, 660, 12, 12),
    CreditProduct("CIBC", "Carte Visa standard", "carte_standard", 1000, 5000, 6, 640, 12, 12),
    CreditProduct("BMO", "Mastercard World Elite", "carte_standard", 3000, 15000, 18, 720, 12, 12),
]

# Règle par défaut appliquée à un compte existant qui ne correspond à aucune
# entrée du catalogue (ex. carte déjà détenue avant l'usage de cet outil).
DEFAULT_HAUSSE_RULE = CreditProduct("_defaut", "_defaut", "carte_standard", 0, 0, 0, None, 12, 12)

CATALOG_OVERRIDE_FILE: str = str(settings.imports_dir / "Finances" / "variables" / "credit_catalog.json")


def load_catalog() -> list[CreditProduct]:
    """Charge le catalogue : surcharge JSON si présente, sinon le défaut."""
    if not os.path.exists(CATALOG_OVERRIDE_FILE):
        return list(DEFAULT_CATALOG)
    try:
        with open(CATALOG_OVERRIDE_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        return [CreditProduct(**item) for item in raw]
    except Exception as e:
        print(f"[credit.catalog] Erreur chargement {CATALOG_OVERRIDE_FILE}: {e}")
        return list(DEFAULT_CATALOG)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_catalog.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/credit/__init__.py backend/app/services/finance/credit/catalog.py backend/tests/test_finance/test_credit_catalog.py
git commit -m "feat(credit): add institution/product catalog with JSON override"
```

---

### Task 3: Planner (core simulation engine)

**Files:**
- Create: `backend/app/services/finance/credit/planner.py`
- Test: `backend/tests/test_finance/test_credit_planner.py`

**Interfaces:**
- Consumes: `CreditProduct`, `DEFAULT_HAUSSE_RULE` from Task 2's `app.services.finance.credit.catalog`; duck-typed `accounts` (objects with `.institution`, `.produit`, `.limite_actuelle`, `.date_ouverture`, `.derniere_augmentation`, `.statut`), `score_history` (objects with `.date`, `.score`), `profile` (object with `.revenu_annuel`, `.date_arrivee_canada`, `.date_cible`) — satisfied directly by Task 1's `CreditAccount`/`CreditScoreEntry`/`CreditProfile` SQLModel instances (constructible without a DB session).
- Produces: `build_plan(accounts, score_history, profile, catalog, today: date) -> dict` with keys `marge_actuelle: float`, `marge_projetee_a_date_cible: float`, `actions: list[dict]` (each with `date`, `type`, `institution`, `produit`, `delta_limite`, `justification`), `projection: list[dict]` (each with `date`, `marge_totale`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_finance/test_credit_planner.py`:
```python
"""Planner marge de crédit : simulation de hausses/ouvertures dans le temps."""

import datetime as dt

from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry
from app.services.finance.credit.catalog import CreditProduct
from app.services.finance.credit.planner import build_plan


def _profile(date_cible):
    return CreditProfile(revenu_annuel=40000, date_arrivee_canada=dt.date(2025, 9, 1), date_cible=date_cible)


def test_existing_account_gets_increase_after_default_threshold():
    accounts = [
        CreditAccount(
            institution="Desjardins", produit="Carte Mastercard", limite_actuelle=700,
            date_ouverture=dt.date(2025, 9, 1), derniere_augmentation=None, statut="actif",
        )
    ]
    profile = _profile(dt.date(2026, 12, 1))
    plan = build_plan(accounts, [], profile, [], today=dt.date(2026, 7, 1))
    hausses = [a for a in plan["actions"] if a["type"] == "hausse" and a["institution"] == "Desjardins"]
    assert len(hausses) == 1
    assert hausses[0]["date"] == dt.date(2026, 9, 1)  # 12 mois après l'ouverture (règle par défaut)
    assert hausses[0]["delta_limite"] == 350.0  # +50% de 700


def test_new_product_opened_once_eligible():
    catalog = [CreditProduct("Newcomer Bank", "Carte Débutant", "programme_newcomer", 500, 2000, 0, None, 6, 12)]
    profile = _profile(dt.date(2026, 7, 1))
    plan = build_plan([], [], profile, catalog, today=dt.date(2026, 1, 1))
    ouvertures = [a for a in plan["actions"] if a["type"] == "ouverture"]
    assert len(ouvertures) == 1
    assert ouvertures[0]["institution"] == "Newcomer Bank"
    assert ouvertures[0]["date"] == dt.date(2026, 1, 1)  # anciennete_min_mois=0 -> éligible immédiatement


def test_score_gate_blocks_product_requiring_score():
    gated = [CreditProduct("Prime Bank", "Carte Premium", "carte_standard", 3000, 8000, 0, 700, 6, 12)]
    profile = _profile(dt.date(2026, 12, 1))

    plan_no_score = build_plan([], [], profile, gated, today=dt.date(2026, 1, 1))
    assert not [a for a in plan_no_score["actions"] if a["institution"] == "Prime Bank"]

    scores = [CreditScoreEntry(date=dt.date(2026, 1, 1), score=720, source="Test")]
    plan_with_score = build_plan([], scores, profile, gated, today=dt.date(2026, 1, 1))
    assert [a for a in plan_with_score["actions"] if a["institution"] == "Prime Bank"]


def test_anti_inquiry_cooldown_limits_new_accounts_per_window():
    catalog = [
        CreditProduct("Bank A", "Carte A", "programme_newcomer", 500, 1000, 0, None, 6, 12),
        CreditProduct("Bank B", "Carte B", "programme_newcomer", 500, 1000, 0, None, 6, 12),
    ]
    profile = _profile(dt.date(2026, 3, 1))
    plan = build_plan([], [], profile, catalog, today=dt.date(2026, 1, 1))
    ouvertures = [a for a in plan["actions"] if a["type"] == "ouverture"]
    # cooldown anti-inquiry = 4 mois -> une seule ouverture possible sur une fenêtre de 3 mois (jan-mar)
    assert len(ouvertures) == 1


def test_empty_state_still_returns_full_projection():
    profile = _profile(dt.date(2026, 9, 1))
    plan = build_plan([], [], profile, [], today=dt.date(2026, 7, 1))
    assert plan["actions"] == []
    assert len(plan["projection"]) == 3  # juillet, août, septembre 2026
    assert plan["marge_actuelle"] == 0.0
    assert plan["marge_projetee_a_date_cible"] == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_planner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.finance.credit.planner'`

- [ ] **Step 3: Write the planner module**

Create `backend/app/services/finance/credit/planner.py`:
```python
"""Simulation mois par mois de la marge de crédit totale (#marge-credit).

Fonction pure : ne touche pas la DB. `build_plan` prend l'état courant
(comptes, historique de pointage, profil) et un catalogue de produits
candidats, et simule mois par mois de `today` à `profile.date_cible` pour
produire une feuille de route d'actions recommandées + une projection de la
marge totale. Aucune extrapolation du pointage : on utilise le dernier
pointage connu à chaque mois (pas de prédiction de progression).
"""

from __future__ import annotations

import datetime as dt

from app.services.finance.credit.catalog import DEFAULT_HAUSSE_RULE, CreditProduct

ANTI_INQUIRY_COOLDOWN_MOIS = 4  # au plus 1 nouvelle demande d'ouverture tous les N mois
HAUSSE_PCT = 0.5  # heuristique : +50% de la limite courante à chaque hausse accordée


def _months_between(d1: dt.date, d2: dt.date) -> int:
    """Nombre de mois pleins entre d1 et d2 (d2 >= d1 attendu)."""
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def _month_range(start: dt.date, end: dt.date) -> list[dt.date]:
    """Premier jour de chaque mois, de start (mois inclus) à end (mois inclus)."""
    cur = dt.date(start.year, start.month, 1)
    last = dt.date(end.year, end.month, 1)
    months = []
    while cur <= last:
        months.append(cur)
        cur = dt.date(cur.year + 1, 1, 1) if cur.month == 12 else dt.date(cur.year, cur.month + 1, 1)
    return months


def _score_at(score_history: list, on_date: dt.date) -> int | None:
    """Dernier pointage connu à une date <= on_date, sinon None."""
    known = [s for s in score_history if s.date <= on_date]
    if not known:
        return None
    return max(known, key=lambda s: s.date).score


def _match_rule(catalog: list[CreditProduct], institution: str, produit: str) -> CreditProduct:
    for p in catalog:
        if p.institution.strip().lower() == institution.strip().lower() and p.produit.strip().lower() == produit.strip().lower():
            return p
    return DEFAULT_HAUSSE_RULE


def build_plan(accounts, score_history, profile, catalog: list[CreditProduct], today: dt.date) -> dict:
    sim = [
        {
            "institution": a.institution,
            "produit": a.produit,
            "limite": a.limite_actuelle,
            "date_ouverture": a.date_ouverture,
            "derniere_hausse": a.derniere_augmentation,
        }
        for a in accounts
        if a.statut == "actif"
    ]
    opened = {(a["institution"].strip().lower(), a["produit"].strip().lower()) for a in sim}
    marge_actuelle = sum(a["limite"] for a in sim)

    actions: list[dict] = []
    projection: list[dict] = []
    last_new_account_month: dt.date | None = None

    for month in _month_range(today, profile.date_cible):
        score = _score_at(score_history, month)
        anciennete_canada = _months_between(profile.date_arrivee_canada, month)

        # 1. Demandes de hausse sur les comptes existants (simulés).
        for acc in sim:
            rule = _match_rule(catalog, acc["institution"], acc["produit"])
            reference = acc["derniere_hausse"] or acc["date_ouverture"]
            months_since = _months_between(reference, month)
            seuil = rule.cooldown_hausse_mois if acc["derniere_hausse"] else rule.anciennete_min_avant_1ere_hausse_mois
            score_ok = rule.score_min_requis is None or (score is not None and score >= rule.score_min_requis)
            if months_since >= seuil and score_ok:
                delta = round(acc["limite"] * HAUSSE_PCT, 2)
                actions.append({
                    "date": month,
                    "type": "hausse",
                    "institution": acc["institution"],
                    "produit": acc["produit"],
                    "delta_limite": delta,
                    "justification": (
                        f"{months_since} mois depuis la dernière hausse (seuil {seuil}), "
                        f"score {'inconnu' if score is None else score} (minimum {rule.score_min_requis or 'aucun'})"
                    ),
                })
                acc["limite"] += delta
                acc["derniere_hausse"] = month

        # 2. Ouverture d'un nouveau produit (au plus 1 tous les ANTI_INQUIRY_COOLDOWN_MOIS).
        can_open = (
            last_new_account_month is None
            or _months_between(last_new_account_month, month) >= ANTI_INQUIRY_COOLDOWN_MOIS
        )
        if can_open:
            candidats = [
                p for p in catalog
                if (p.institution.strip().lower(), p.produit.strip().lower()) not in opened
                and anciennete_canada >= p.anciennete_min_mois
                and (p.score_min_requis is None or (score is not None and score >= p.score_min_requis))
            ]
            if candidats:
                meilleur = max(candidats, key=lambda p: (p.limite_min + p.limite_max) / 2)
                limite_depart = min(meilleur.limite_max, max(meilleur.limite_min, profile.revenu_annuel * 0.1))
                actions.append({
                    "date": month,
                    "type": "ouverture",
                    "institution": meilleur.institution,
                    "produit": meilleur.produit,
                    "delta_limite": round(limite_depart, 2),
                    "justification": (
                        f"éligible : {anciennete_canada} mois au Canada, "
                        f"score {'inconnu' if score is None else score} (minimum {meilleur.score_min_requis or 'aucun'})"
                    ),
                })
                sim.append({
                    "institution": meilleur.institution,
                    "produit": meilleur.produit,
                    "limite": limite_depart,
                    "date_ouverture": month,
                    "derniere_hausse": None,
                })
                opened.add((meilleur.institution.strip().lower(), meilleur.produit.strip().lower()))
                last_new_account_month = month

        projection.append({"date": month, "marge_totale": round(sum(a["limite"] for a in sim), 2)})

    return {
        "marge_actuelle": round(marge_actuelle, 2),
        "marge_projetee_a_date_cible": projection[-1]["marge_totale"] if projection else round(marge_actuelle, 2),
        "actions": actions,
        "projection": projection,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_planner.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/credit/planner.py backend/tests/test_finance/test_credit_planner.py
git commit -m "feat(credit): add month-by-month planner (increases + new-account rules)"
```

---

### Task 4: Service layer (CRUD + compute_plan)

**Files:**
- Create: `backend/app/services/finance/credit/service.py`
- Test: `backend/tests/test_finance/test_credit_service.py`

**Interfaces:**
- Consumes: `CreditProfile`, `CreditAccount`, `CreditScoreEntry` (Task 1); `load_catalog` (Task 2); `build_plan` (Task 3); `app.core.db.get_session`-compatible `Session`; `app.core.timeutil.utcnow`.
- Produces: `get_or_create_profile(session) -> CreditProfile`, `update_profile(session, patch: dict) -> CreditProfile`, `list_accounts(session) -> list[CreditAccount]`, `create_account(session, **kwargs) -> CreditAccount`, `update_account(session, account_id: int, patch: dict) -> CreditAccount | None`, `delete_account(session, account_id: int) -> bool`, `list_score_entries(session) -> list[CreditScoreEntry]`, `create_score_entry(session, **kwargs) -> CreditScoreEntry`, `delete_score_entry(session, entry_id: int) -> bool`, `compute_plan(session) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_finance/test_credit_service.py` (uses the `mem_session` fixture from `backend/tests/conftest.py`):
```python
"""Service CRUD + compute_plan pour le module Marge de crédit."""

import datetime as dt

from app.services.finance.credit import service as svc


def test_get_or_create_profile_creates_default_on_first_call(mem_session):
    profile = svc.get_or_create_profile(mem_session)
    assert profile.id is not None
    assert profile.revenu_annuel == 0.0
    # même profil renvoyé au 2e appel (pas de doublon)
    again = svc.get_or_create_profile(mem_session)
    assert again.id == profile.id


def test_update_profile_patches_fields(mem_session):
    svc.get_or_create_profile(mem_session)
    updated = svc.update_profile(mem_session, {"revenu_annuel": 40000.0})
    assert updated.revenu_annuel == 40000.0


def test_account_crud_roundtrip(mem_session):
    account = svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    assert account.id is not None
    assert svc.list_accounts(mem_session) == [account]

    updated = svc.update_account(mem_session, account.id, {"limite_actuelle": 1200})
    assert updated.limite_actuelle == 1200

    assert svc.update_account(mem_session, 9999, {"limite_actuelle": 1}) is None
    assert svc.delete_account(mem_session, account.id) is True
    assert svc.delete_account(mem_session, account.id) is False
    assert svc.list_accounts(mem_session) == []


def test_score_entry_crud_roundtrip(mem_session):
    entry = svc.create_score_entry(mem_session, date=dt.date(2026, 1, 1), score=650, source="Credit Karma")
    assert entry.id is not None
    assert svc.list_score_entries(mem_session) == [entry]
    assert svc.delete_score_entry(mem_session, entry.id) is True
    assert svc.delete_score_entry(mem_session, entry.id) is False


def test_compute_plan_uses_current_db_state(mem_session):
    svc.update_profile(mem_session, {
        "revenu_annuel": 40000.0,
        "date_arrivee_canada": dt.date(2025, 9, 1),
        "date_cible": dt.date(2025, 12, 1),
    })
    svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    plan = svc.compute_plan(mem_session)
    assert plan["marge_actuelle"] == 700.0
    assert "projection" in plan and "actions" in plan
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.finance.credit.service'`

- [ ] **Step 3: Write the service module**

Create `backend/app/services/finance/credit/service.py`:
```python
"""Service CRUD + calcul du plan pour le module Marge de crédit (#marge-credit)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry
from app.services.finance.credit.catalog import load_catalog
from app.services.finance.credit.planner import build_plan

DEFAULT_DATE_CIBLE_ANNEES = 3  # par défaut, 3 ans après l'arrivée au Canada


def get_or_create_profile(session: Session) -> CreditProfile:
    profile = session.exec(select(CreditProfile)).first()
    if profile:
        return profile
    today = dt.date.today()
    profile = CreditProfile(
        revenu_annuel=0.0,
        date_arrivee_canada=today,
        date_cible=today.replace(year=today.year + DEFAULT_DATE_CIBLE_ANNEES),
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def update_profile(session: Session, patch: dict) -> CreditProfile:
    profile = get_or_create_profile(session)
    for k, v in patch.items():
        if hasattr(profile, k):
            setattr(profile, k, v)
    profile.updated_at = utcnow()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def list_accounts(session: Session) -> list[CreditAccount]:
    return list(session.exec(select(CreditAccount).order_by(CreditAccount.date_ouverture)).all())


def create_account(session: Session, **kwargs) -> CreditAccount:
    account = CreditAccount(**kwargs)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def update_account(session: Session, account_id: int, patch: dict) -> CreditAccount | None:
    account = session.get(CreditAccount, account_id)
    if not account:
        return None
    for k, v in patch.items():
        if hasattr(account, k):
            setattr(account, k, v)
    account.updated_at = utcnow()
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def delete_account(session: Session, account_id: int) -> bool:
    account = session.get(CreditAccount, account_id)
    if not account:
        return False
    session.delete(account)
    session.commit()
    return True


def list_score_entries(session: Session) -> list[CreditScoreEntry]:
    return list(session.exec(select(CreditScoreEntry).order_by(CreditScoreEntry.date)).all())


def create_score_entry(session: Session, **kwargs) -> CreditScoreEntry:
    entry = CreditScoreEntry(**kwargs)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def delete_score_entry(session: Session, entry_id: int) -> bool:
    entry = session.get(CreditScoreEntry, entry_id)
    if not entry:
        return False
    session.delete(entry)
    session.commit()
    return True


def compute_plan(session: Session) -> dict:
    profile = get_or_create_profile(session)
    accounts = list_accounts(session)
    scores = list_score_entries(session)
    catalog = load_catalog()
    return build_plan(accounts, scores, profile, catalog, today=dt.date.today())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/credit/service.py backend/tests/test_finance/test_credit_service.py
git commit -m "feat(credit): add CRUD service + compute_plan orchestration"
```

---

### Task 5: API routes + router registration

**Files:**
- Create: `backend/app/api/finance/credit.py`
- Modify: `backend/app/api/finance/__init__.py`
- Test: `backend/tests/test_finance/test_credit_api.py`

**Interfaces:**
- Consumes: `app.services.finance.credit.service` (Task 4); `app.core.db.get_session`; FastAPI `APIRouter`.
- Produces: HTTP endpoints `GET/PATCH /finance/credit/profile`, `GET/POST /finance/credit/accounts`, `PATCH/DELETE /finance/credit/accounts/{id}`, `GET/POST /finance/credit/scores`, `DELETE /finance/credit/scores/{id}`, `GET /finance/credit/plan`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_finance/test_credit_api.py` (follows the `TestClient` + dependency-override pattern from `backend/tests/test_finance/test_state_api.py`):
```python
"""Intégration API : CRUD marge de crédit + calcul du plan."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


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


def test_profile_get_and_patch(client):
    r = client.get("/finance/credit/profile")
    assert r.status_code == 200
    assert r.json()["revenu_annuel"] == 0.0

    r = client.patch("/finance/credit/profile", json={"revenu_annuel": 40000})
    assert r.status_code == 200
    assert r.json()["revenu_annuel"] == 40000.0


def test_account_crud(client):
    r = client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    assert r.status_code == 201
    account_id = r.json()["id"]

    r = client.get("/finance/credit/accounts")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = client.patch(f"/finance/credit/accounts/{account_id}", json={"limite_actuelle": 1200})
    assert r.status_code == 200
    assert r.json()["limite_actuelle"] == 1200.0

    r = client.delete(f"/finance/credit/accounts/{account_id}")
    assert r.status_code == 204
    r = client.delete(f"/finance/credit/accounts/{account_id}")
    assert r.status_code == 404


def test_score_crud(client):
    r = client.post("/finance/credit/scores", json={"date": "2026-01-01", "score": 650, "source": "Credit Karma"})
    assert r.status_code == 201
    entry_id = r.json()["id"]
    assert client.get("/finance/credit/scores").json()[0]["score"] == 650
    assert client.delete(f"/finance/credit/scores/{entry_id}").status_code == 204


def test_plan_endpoint_returns_projection(client):
    client.patch("/finance/credit/profile", json={
        "revenu_annuel": 40000, "date_arrivee_canada": "2025-09-01", "date_cible": "2025-12-01",
    })
    client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["marge_actuelle"] == 700.0
    assert "actions" in body and "projection" in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_api.py -v`
Expected: FAIL with 404s (route `/finance/credit/*` doesn't exist yet)

- [ ] **Step 3: Write the API route module**

Create `backend/app/api/finance/credit.py`:
```python
"""Marge de crédit : profil, comptes, historique de pointage, feuille de route."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance.credit import service as svc

router = APIRouter()


class CreditProfilePatch(BaseModel):
    revenu_annuel: float | None = None
    date_arrivee_canada: dt.date | None = None
    date_cible: dt.date | None = None
    nom: str | None = None


class CreditAccountIn(BaseModel):
    institution: str
    produit: str
    limite_actuelle: float
    date_ouverture: dt.date
    derniere_augmentation: dt.date | None = None
    statut: str = "actif"
    notes: str | None = None


class CreditAccountPatch(BaseModel):
    institution: str | None = None
    produit: str | None = None
    limite_actuelle: float | None = None
    date_ouverture: dt.date | None = None
    derniere_augmentation: dt.date | None = None
    statut: str | None = None
    notes: str | None = None


class CreditScoreEntryIn(BaseModel):
    date: dt.date
    score: int
    source: str = ""


@router.get("/credit/profile")
def get_credit_profile(session: Session = Depends(get_session)):
    return svc.get_or_create_profile(session).model_dump()


@router.patch("/credit/profile")
def patch_credit_profile(body: CreditProfilePatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return svc.update_profile(session, patch).model_dump()


@router.get("/credit/accounts")
def get_credit_accounts(session: Session = Depends(get_session)):
    return [a.model_dump() for a in svc.list_accounts(session)]


@router.post("/credit/accounts", status_code=201)
def create_credit_account(body: CreditAccountIn, session: Session = Depends(get_session)):
    return svc.create_account(session, **body.model_dump()).model_dump()


@router.patch("/credit/accounts/{account_id}")
def patch_credit_account(account_id: int, body: CreditAccountPatch, session: Session = Depends(get_session)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    account = svc.update_account(session, account_id, patch)
    if not account:
        raise HTTPException(404)
    return account.model_dump()


@router.delete("/credit/accounts/{account_id}", status_code=204)
def delete_credit_account(account_id: int, session: Session = Depends(get_session)):
    if not svc.delete_account(session, account_id):
        raise HTTPException(404)


@router.get("/credit/scores")
def get_credit_scores(session: Session = Depends(get_session)):
    return [s.model_dump() for s in svc.list_score_entries(session)]


@router.post("/credit/scores", status_code=201)
def create_credit_score(body: CreditScoreEntryIn, session: Session = Depends(get_session)):
    return svc.create_score_entry(session, **body.model_dump()).model_dump()


@router.delete("/credit/scores/{entry_id}", status_code=204)
def delete_credit_score(entry_id: int, session: Session = Depends(get_session)):
    if not svc.delete_score_entry(session, entry_id):
        raise HTTPException(404)


@router.get("/credit/plan")
def get_credit_plan(session: Session = Depends(get_session)):
    return svc.compute_plan(session)
```

- [ ] **Step 4: Register the router**

In `backend/app/api/finance/__init__.py`, change:
```python
from . import buffett, objectif, patrimoine, portfolio, rebalancing, risk, transactions
```
to:
```python
from . import buffett, credit, objectif, patrimoine, portfolio, rebalancing, risk, transactions
```
and add, alongside the other `include_router` calls:
```python
router.include_router(credit.router)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS, no regressions (in particular `tests/test_migrations.py` still passes)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/finance/credit.py backend/app/api/finance/__init__.py backend/tests/test_finance/test_credit_api.py
git commit -m "feat(credit): add /finance/credit API routes"
```

---

### Task 6: Frontend API client (types + fetch wrappers)

**Files:**
- Modify: `frontend/lib/finance.ts`

**Interfaces:**
- Consumes: existing `get`, `post`, `put`, `patch`, `del` helpers already defined in `frontend/lib/finance.ts` (Section 6 of the codebase research — do not redefine them).
- Produces (appended to the `financeApi` export and new top-level types in the same file): `CreditProfile`, `CreditProfilePatch`, `CreditAccount`, `CreditAccountCreate`, `CreditScoreEntry`, `CreditScoreEntryCreate`, `CreditPlanAction`, `CreditPlanPoint`, `CreditPlan` interfaces; `financeApi.creditProfile()`, `financeApi.creditProfileUpdate(data)`, `financeApi.creditAccounts()`, `financeApi.creditAccountCreate(data)`, `financeApi.creditAccountUpdate(id, data)`, `financeApi.creditAccountDelete(id)`, `financeApi.creditScores()`, `financeApi.creditScoreCreate(data)`, `financeApi.creditScoreDelete(id)`, `financeApi.creditPlan()`.

- [ ] **Step 1: Add the TypeScript interfaces**

In `frontend/lib/finance.ts`, add near the other domain interfaces (e.g. right before the `PatrimoineItem` interfaces):
```ts
export interface CreditProfile {
  id: number;
  revenu_annuel: number;
  date_arrivee_canada: string;
  date_cible: string;
  nom: string | null;
}
export interface CreditProfilePatch {
  revenu_annuel?: number;
  date_arrivee_canada?: string;
  date_cible?: string;
  nom?: string | null;
}
export interface CreditAccount {
  id: number;
  institution: string;
  produit: string;
  limite_actuelle: number;
  date_ouverture: string;
  derniere_augmentation: string | null;
  statut: "actif" | "ferme";
  notes: string | null;
}
export interface CreditAccountCreate {
  institution: string;
  produit: string;
  limite_actuelle: number;
  date_ouverture: string;
  derniere_augmentation?: string | null;
  statut?: "actif" | "ferme";
  notes?: string | null;
}
export interface CreditScoreEntry {
  id: number;
  date: string;
  score: number;
  source: string;
}
export interface CreditScoreEntryCreate {
  date: string;
  score: number;
  source?: string;
}
export interface CreditPlanAction {
  date: string;
  type: "hausse" | "ouverture";
  institution: string;
  produit: string;
  delta_limite: number;
  justification: string;
}
export interface CreditPlanPoint {
  date: string;
  marge_totale: number;
}
export interface CreditPlan {
  marge_actuelle: number;
  marge_projetee_a_date_cible: number;
  actions: CreditPlanAction[];
  projection: CreditPlanPoint[];
}
```

- [ ] **Step 2: Append the endpoint functions**

In `frontend/lib/finance.ts`, inside the `financeApi` object (right after the `patrimoine*` entries), add:
```ts
  // Marge de crédit
  creditProfile: () => get<CreditProfile>("/credit/profile"),
  creditProfileUpdate: (data: CreditProfilePatch) => patch<CreditProfile>("/credit/profile", data),
  creditAccounts: () => get<CreditAccount[]>("/credit/accounts"),
  creditAccountCreate: (data: CreditAccountCreate) => post<CreditAccount>("/credit/accounts", data),
  creditAccountUpdate: (id: number, data: Partial<CreditAccountCreate>) =>
    patch<CreditAccount>(`/credit/accounts/${id}`, data),
  creditAccountDelete: (id: number) => del(`/credit/accounts/${id}`),
  creditScores: () => get<CreditScoreEntry[]>("/credit/scores"),
  creditScoreCreate: (data: CreditScoreEntryCreate) => post<CreditScoreEntry>("/credit/scores", data),
  creditScoreDelete: (id: number) => del(`/credit/scores/${id}`),
  creditPlan: () => get<CreditPlan>("/credit/plan"),
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors related to `finance.ts`

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/finance.ts
git commit -m "feat(credit): add frontend types + API client for credit margin"
```

---

### Task 7: Frontend module registration + route scaffold

**Files:**
- Modify: `frontend/lib/modules.ts`
- Create: `frontend/src/app/credit/page.tsx`
- Create: `frontend/src/app/credit/loading.tsx`

**Interfaces:**
- Consumes: `CreditTab` from `@/components/finance/CreditTab` (created in Task 8 — this task creates the page that imports it, so Task 8 must land before this route is functional; import will type-error until Task 8 exists, which is fine since both are committed together in this plan's execution order).
- Produces: route `/credit` registered in nav (`ModuleGroup = "Finances & Ingénierie"`).

- [ ] **Step 1: Register the module**

In `frontend/lib/modules.ts`, add `CreditCard` to the `lucide-react` import list (alphabetical, between `Calendar` and `Database`... actually insert alphabetically: the import list is alphabetized, so add `CreditCard` right after `Calendar`):
```ts
import {
  BookOpen,
  Briefcase,
  Calendar,
  ChefHat,
  CreditCard,
  Database,
  Dumbbell,
  ...
```
Then add a new entry inside the `"Finances & Ingénierie"` group of `MODULES` (after the `patrimoine` entry):
```ts
  {
    slug: "credit",
    label: "Marge de crédit",
    description: "Feuille de route pour maximiser la marge de crédit totale.",
    icon: CreditCard,
    group: "Finances & Ingénierie",
    ready: true,
  },
```

- [ ] **Step 2: Create the page**

Create `frontend/src/app/credit/page.tsx`:
```tsx
import { CreditTab } from "@/components/finance/CreditTab";
import { ModuleHeader } from "@/components/layout";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = { title: "Marge de crédit — Mission Control" };

export default function CreditPage() {
  return (
    <div>
      <ModuleHeader title="Marge de crédit" subtitle="Feuille de route pour maximiser ta marge de crédit totale" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Marge de crédit">
          <CreditTab />
        </ErrorBoundary>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create the loading skeleton**

Create `frontend/src/app/credit/loading.tsx`:
```tsx
import { SkeletonHeader, SkeletonStatRow, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="animate-fade-in">
      <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
        <div className="mb-4">
          <SkeletonHeader />
        </div>
      </div>

      <div className="p-6 space-y-6 animate-fade-in-up">
        <SkeletonStatRow count={2} />
        <Skeleton className="h-24 w-full rounded-[var(--radius-lg)]" /> {/* projection */}
        <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" /> {/* comptes */}
        <Skeleton className="h-40 w-full rounded-[var(--radius-lg)]" /> {/* feuille de route */}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/modules.ts frontend/src/app/credit/page.tsx frontend/src/app/credit/loading.tsx
git commit -m "feat(credit): register credit module in nav + scaffold route"
```

(Note: this commit will not yet build cleanly on its own since `CreditTab` doesn't exist until Task 8 — that's expected for this plan's task ordering; if running under `executing-plans`/`subagent-driven-development` with a build-check gate per task, run Tasks 7 and 8 as one combined review checkpoint.)

---

### Task 8: `CreditTab` component (profile, accounts, scores, roadmap, chart)

**Files:**
- Create: `frontend/components/finance/CreditTab.tsx`

**Interfaces:**
- Consumes: `financeApi.creditProfile/creditProfileUpdate/creditAccounts/creditAccountCreate/creditAccountUpdate/creditAccountDelete/creditScores/creditScoreCreate/creditScoreDelete/creditPlan` and types `CreditProfile`, `CreditAccount`, `CreditAccountCreate`, `CreditScoreEntry`, `CreditPlan` (Task 6); `CreditPage` (Task 7) imports `CreditTab` from this file.
- Produces: `export function CreditTab(): JSX.Element`.

- [ ] **Step 1: Write the component**

Create `frontend/components/finance/CreditTab.tsx`:
```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import {
  financeApi,
  type CreditAccount,
  type CreditAccountCreate,
  type CreditProfile,
  type CreditScoreEntry,
} from "@/lib/finance";

const cad = (n: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(n);

const fmtMonthYear = (iso: string) =>
  new Date(iso + "T12:00:00").toLocaleDateString("fr-CA", { month: "short", year: "numeric" });

const KEY = ["finance", "credit"] as const;

export function CreditTab() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const plan = useQuery({ queryKey: [...KEY, "plan"], queryFn: financeApi.creditPlan });
  const profile = useQuery({ queryKey: [...KEY, "profile"], queryFn: financeApi.creditProfile });
  const accounts = useQuery({ queryKey: [...KEY, "accounts"], queryFn: financeApi.creditAccounts });
  const scores = useQuery({ queryKey: [...KEY, "scores"], queryFn: financeApi.creditScores });

  const updateProfile = useMutation({ mutationFn: financeApi.creditProfileUpdate, onSuccess: invalidate });
  const createAccount = useMutation({ mutationFn: financeApi.creditAccountCreate, onSuccess: invalidate });
  const updateAccount = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<CreditAccountCreate> }) =>
      financeApi.creditAccountUpdate(id, patch),
    onSuccess: invalidate,
  });
  const deleteAccount = useMutation({ mutationFn: financeApi.creditAccountDelete, onSuccess: invalidate });
  const createScore = useMutation({ mutationFn: financeApi.creditScoreCreate, onSuccess: invalidate });
  const deleteScore = useMutation({ mutationFn: financeApi.creditScoreDelete, onSuccess: invalidate });

  const anyError = plan.isError || profile.isError || accounts.isError || scores.isError;
  const anyLoading =
    plan.isLoading || profile.isLoading || accounts.isLoading || scores.isLoading ||
    !plan.data || !profile.data || !accounts.data || !scores.data;

  if (anyError)
    return (
      <div className="text-sm text-[var(--warning-foreground)]">
        Impossible de charger la marge de crédit.{" "}
        <button
          onClick={() => { void plan.refetch(); void profile.refetch(); void accounts.refetch(); void scores.refetch(); }}
          className="underline hover:text-[var(--foreground)]"
        >
          Réessayer
        </button>
      </div>
    );
  if (anyLoading) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Marge totale actuelle" value={cad(plan.data!.marge_actuelle)} strong />
        <Stat
          label={`Marge projetée au ${fmtMonthYear(profile.data!.date_cible)}`}
          value={cad(plan.data!.marge_projetee_a_date_cible)}
          strong
        />
      </div>

      <ProjectionChart points={plan.data!.projection} />

      <ProfileForm profile={profile.data!} onSave={(patch) => updateProfile.mutate(patch)} />

      <AccountsSection
        accounts={accounts.data!}
        onCreate={(body) => createAccount.mutate(body)}
        onUpdate={(id, patch) => updateAccount.mutate({ id, patch })}
        onDelete={(id) => deleteAccount.mutate(id)}
      />

      <ScoresSection
        scores={scores.data!}
        onCreate={(body) => createScore.mutate(body)}
        onDelete={(id) => deleteScore.mutate(id)}
      />

      <RoadmapSection actions={plan.data!.actions} />
    </div>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`tabular-nums text-[var(--foreground)] ${strong ? "text-xl font-semibold" : "text-base"}`}>{value}</div>
    </div>
  );
}

function ProjectionChart({ points }: { points: { date: string; marge_totale: number }[] }) {
  if (points.length < 2) return null;
  const values = points.map((p) => p.marge_totale);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100, H = 32;
  const coords = values
    .map((v, i) => `${((i / (values.length - 1)) * W).toFixed(2)},${(H - ((v - min) / span) * H).toFixed(2)}`)
    .join(" ");

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale projetée</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Projection de la marge de crédit totale">
        <polyline points={coords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(points[0].date)} · {cad(min)}</span>
        <span>{fmtMonthYear(points[points.length - 1].date)} · {cad(max)}</span>
      </div>
    </div>
  );
}

function ProfileForm({
  profile,
  onSave,
}: {
  profile: CreditProfile;
  onSave: (patch: { revenu_annuel?: number; date_arrivee_canada?: string; date_cible?: string }) => void;
}) {
  const [revenu, setRevenu] = useState(String(profile.revenu_annuel));
  const [arrivee, setArrivee] = useState(profile.date_arrivee_canada);
  const [cible, setCible] = useState(profile.date_cible);

  const commitRevenu = () => {
    const n = Number(revenu);
    if (!Number.isNaN(n) && n !== profile.revenu_annuel) onSave({ revenu_annuel: n });
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Profil</p>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-1.5">
          Revenu annuel
          <input
            value={revenu}
            onChange={(e) => setRevenu(e.target.value)}
            onBlur={commitRevenu}
            type="number"
            className="w-24 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-right tabular-nums"
          />
        </label>
        <label className="flex items-center gap-1.5">
          Arrivée au Canada
          <input
            value={arrivee}
            onChange={(e) => setArrivee(e.target.value)}
            onBlur={() => arrivee !== profile.date_arrivee_canada && onSave({ date_arrivee_canada: arrivee })}
            type="date"
            className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1"
          />
        </label>
        <label className="flex items-center gap-1.5">
          Date cible
          <input
            value={cible}
            onChange={(e) => setCible(e.target.value)}
            onBlur={() => cible !== profile.date_cible && onSave({ date_cible: cible })}
            type="date"
            className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1"
          />
        </label>
      </div>
    </div>
  );
}

function AccountsSection({
  accounts,
  onCreate,
  onUpdate,
  onDelete,
}: {
  accounts: CreditAccount[];
  onCreate: (body: CreditAccountCreate) => void;
  onUpdate: (id: number, patch: Partial<CreditAccountCreate>) => void;
  onDelete: (id: number) => void;
}) {
  const [institution, setInstitution] = useState("");
  const [produit, setProduit] = useState("");
  const [limite, setLimite] = useState("");
  const [dateOuverture, setDateOuverture] = useState("");

  const submit = () => {
    if (!institution.trim() || !produit.trim() || !limite || !dateOuverture) return;
    onCreate({ institution: institution.trim(), produit: produit.trim(), limite_actuelle: Number(limite), date_ouverture: dateOuverture });
    setInstitution(""); setProduit(""); setLimite(""); setDateOuverture("");
  };

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Mes comptes de crédit</p>
      {accounts.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucun compte enregistré.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {accounts.map((a) => (
            <AccountRow key={`${a.id}:${a.limite_actuelle}:${a.statut}`} account={a} onUpdate={onUpdate} onDelete={onDelete} />
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={institution} onChange={(e) => setInstitution(e.target.value)} placeholder="Institution" className="w-32 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={produit} onChange={(e) => setProduit(e.target.value)} placeholder="Produit (ex. Carte Mastercard)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={limite} onChange={(e) => setLimite(e.target.value)} type="number" placeholder="Limite" className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <input value={dateOuverture} onChange={(e) => setDateOuverture(e.target.value)} type="date" className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function AccountRow({
  account,
  onUpdate,
  onDelete,
}: {
  account: CreditAccount;
  onUpdate: (id: number, patch: Partial<CreditAccountCreate>) => void;
  onDelete: (id: number) => void;
}) {
  const [limite, setLimite] = useState(String(account.limite_actuelle));
  const commit = () => {
    const n = Number(limite);
    if (!Number.isNaN(n) && n !== account.limite_actuelle) onUpdate(account.id, { limite_actuelle: n });
  };
  return (
    <li className="flex items-center gap-2 px-3 py-2 text-sm">
      <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">
        {account.institution} <span className="text-xs text-[var(--muted-foreground)]">· {account.produit}</span>
      </span>
      <span className="text-xs text-[var(--muted-foreground)]">depuis {fmtMonthYear(account.date_ouverture)}</span>
      <input
        value={limite}
        onChange={(e) => setLimite(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
        className="w-24 rounded border border-transparent bg-transparent px-1 py-0.5 text-right tabular-nums hover:border-[var(--border)] focus:border-[var(--ring)] focus:outline-none"
      />
      <button onClick={() => onDelete(account.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
        <Trash2 size={14} />
      </button>
    </li>
  );
}

function ScoresSection({
  scores,
  onCreate,
  onDelete,
}: {
  scores: CreditScoreEntry[];
  onCreate: (body: { date: string; score: number; source?: string }) => void;
  onDelete: (id: number) => void;
}) {
  const [date, setDate] = useState("");
  const [score, setScore] = useState("");
  const [source, setSource] = useState("");

  const submit = () => {
    if (!date || !score) return;
    onCreate({ date, score: Number(score), source: source.trim() });
    setDate(""); setScore(""); setSource("");
  };

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Historique de pointage</p>
      {scores.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucun pointage enregistré.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {scores.map((s) => (
            <li key={s.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="text-xs text-[var(--muted-foreground)]">{fmtMonthYear(s.date)}</span>
              <span className="flex-1 font-medium tabular-nums text-[var(--foreground)]">{s.score}</span>
              <span className="text-xs text-[var(--muted-foreground)]">{s.source}</span>
              <button onClick={() => onDelete(s.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={date} onChange={(e) => setDate(e.target.value)} type="date" className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <input value={score} onChange={(e) => setScore(e.target.value)} type="number" placeholder="Score" className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source (ex. Credit Karma)" className="min-w-40 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function RoadmapSection({
  actions,
}: {
  actions: { date: string; type: "hausse" | "ouverture"; institution: string; produit: string; delta_limite: number; justification: string }[];
}) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Feuille de route recommandée</p>
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">
        Estimations heuristiques — ajuste le catalogue si tu connais les vraies politiques d'une banque.
      </p>
      {actions.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune action recommandée pour l'instant.</p>
      ) : (
        <ol className="space-y-2">
          {actions.map((a, i) => (
            <li key={i} className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-[var(--foreground)]">
                  {fmtMonthYear(a.date)} · {a.type === "hausse" ? "Demander une augmentation" : "Ouvrir un compte"} — {a.institution} ({a.produit})
                </span>
                <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(a.delta_limite)}</span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted-foreground)]">{a.justification}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no errors in `CreditTab.tsx` or the files touched in Task 7

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds, `/credit` route present in the output

- [ ] **Step 5: Manual smoke test**

Run: `cd frontend && npm run dev` (and `cd backend && uvicorn app.main:app --reload` if not already running), then open `http://localhost:3000/credit` in a browser. Confirm: page loads without console errors, "Marge de crédit" appears in the sidebar under "Finances & Ingénierie", adding a credit account and a score entry works and updates the stat tiles/roadmap/chart after a refetch.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/finance/CreditTab.tsx
git commit -m "feat(credit): add CreditTab UI (profile, accounts, scores, roadmap, chart)"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1 → data model section; Task 2 → catalogue section; Task 3 → moteur section; Task 4+5 → API section; Task 6+7+8 → frontend section. Hors-scope items (bureau de crédit, Monte-Carlo, statut fait/rejeté) are explicitly not implemented anywhere in this plan.
- **Type consistency checked:** `CreditAccountCreate`/`CreditAccountIn` field names match `CreditAccount` model fields exactly across Tasks 1, 5, 6, 8. `CreditPlan`/`CreditPlanAction`/`CreditPlanPoint` (Task 6) match the dict shape returned by `build_plan` (Task 3) and re-emitted verbatim by `GET /credit/plan` (Task 5).
- **Naming collision avoided:** the generic `patch<T>()` fetch helper in `lib/finance.ts` and the `CreditProfilePatch`/mutation `patch` object are never both in scope with the same identifier — mutation functions use parameter name `data`, not `patch`, precisely to avoid shadowing the helper.
