# Marge de crédit — simplification (règles à seuils) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the catalog/institution-eligibility engine in the existing "Marge de crédit" module with a simpler model: the user defines their own ordered list of score-threshold rules (at score X, do action Y, worth ~$Z), and the system projects future score + total credit margin by deducing the score's growth rate from the user's real score history and applying rules as the projected score crosses their thresholds (each triggered action also dips the score by a fixed amount).

**Architecture:** Same layered structure as before (models → planner → service → API → frontend), but `catalog.py` is deleted entirely, `planner.py` is rewritten around a much simpler pure function, a new `CreditActionRule` table replaces the catalog, and `CreditProfile` drops its now-unused `revenu_annuel`/`date_arrivee_canada` fields. The frontend gains a Rules CRUD section and splits the single margin chart into two charts (credit score over time, total margin over time), each showing real history + a projected/dashed continuation.

**Tech Stack:** FastAPI, SQLModel, Alembic, pytest, Next.js (App Router), React Query, TypeScript, Tailwind CSS vars.

## Global Constraints

- No external credit-bureau/banking APIs (unchanged from v1).
- No new npm packages — charts stay inline SVG.
- Every new/changed SQLModel table/column MUST be (a) reflected in `backend/app/models/__init__.py` and (b) backed by a hand-written Alembic migration — `backend/tests/test_migrations.py` fails the build otherwise.
- Rules are entered entirely by the user — no hardcoded bank names, no eligibility heuristics based on income or time-in-Canada.
- `SCORE_IMPACT_PAR_ACTION = 10` (points lost after each triggered action, hausse or nouvelle_carte alike) — single fixed value, not configurable per action type.
- The score growth rate used for projection is deduced from the two extreme points of the user's real `CreditScoreEntry` history (first and last by date) — no multi-point regression, no user-configurable rate field.
- If fewer than 2 score entries exist, no projection is computed — only real history is returned (`projection_possible: false`).
- French UI copy and code comments, consistent with the rest of the codebase.
- No status tracking on triggered actions — `GET /finance/credit/plan` always recomputes fresh from current DB state (unchanged from v1).

---

### Task 1: Model changes — `CreditActionRule` + drop unused `CreditProfile` fields

**Files:**
- Modify: `backend/app/models/credit.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260706_0000_s706creditrules_credit_action_rule.py`

**Interfaces:**
- Produces: `CreditActionRule(id, seuil_score: int, type: str, montant_estime: float, created_at: datetime)` — `SQLModel, table=True`, importable from `app.models.credit`. `CreditProfile` loses `revenu_annuel` and `date_arrivee_canada` (fields no longer exist on the class).

- [ ] **Step 1: Update the models file**

In `backend/app/models/credit.py`, replace the `CreditProfile` class:

```python
class CreditProfile(SQLModel, table=True):
    __tablename__ = "credit_profile"
    id: int | None = Field(default=None, primary_key=True)
    date_cible: dt.date = Field(default_factory=lambda: dt.date.today())
    nom: str | None = None
    updated_at: dt.datetime = Field(default_factory=utcnow)
```

And add this new class after `CreditScoreEntry`:

```python
class CreditActionRule(SQLModel, table=True):
    """Règle définie par l'utilisateur : à partir de quel score déclencher
    quelle action (hausse de limite ou nouvelle carte), pour quel montant
    estimé. Aucune notion de banque/produit — c'est l'utilisateur qui sait
    quelle institution il visera."""
    __tablename__ = "credit_action_rule"
    id: int | None = Field(default=None, primary_key=True)
    seuil_score: int
    type: str  # "hausse" | "nouvelle_carte"
    montant_estime: float = 0.0
    created_at: dt.datetime = Field(default_factory=utcnow)
```

- [ ] **Step 2: Register the new model**

In `backend/app/models/__init__.py`, change:
```python
from app.models.credit import CreditAccount, CreditProfile, CreditScoreEntry  # noqa: F401
```
to:
```python
from app.models.credit import CreditAccount, CreditActionRule, CreditProfile, CreditScoreEntry  # noqa: F401
```

- [ ] **Step 3: Write the Alembic migration**

Create `backend/alembic/versions/20260706_0000_s706creditrules_credit_action_rule.py`:
```python
"""credit_action_rule + simplification credit_profile (#marge-credit v2)

Revision ID: s706creditrules
Revises: r705creditmargin
Create Date: 2026-07-06 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "s706creditrules"
down_revision = "r705creditmargin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_action_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seuil_score", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("montant_estime", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("credit_profile", schema=None) as batch_op:
        batch_op.drop_column("revenu_annuel")
        batch_op.drop_column("date_arrivee_canada")


def downgrade() -> None:
    with op.batch_alter_table("credit_profile", schema=None) as batch_op:
        batch_op.add_column(sa.Column("date_arrivee_canada", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("revenu_annuel", sa.Float(), nullable=True))
    op.drop_table("credit_action_rule")
```

- [ ] **Step 4: Run the migration guardrail test**

Run: `cd backend && python -m pytest tests/test_migrations.py -v`
Expected: PASS (schema matches models exactly)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/credit.py backend/app/models/__init__.py backend/alembic/versions/20260706_0000_s706creditrules_credit_action_rule.py
git commit -m "feat(credit): add CreditActionRule model, drop unused CreditProfile fields"
```

---

### Task 2: Planner rewrite — score-threshold simulation

**Files:**
- Modify: `backend/app/services/finance/credit/planner.py` (full rewrite)
- Modify: `backend/tests/test_finance/test_credit_planner.py` (full rewrite)
- Delete: `backend/app/services/finance/credit/catalog.py`
- Delete: `backend/tests/test_finance/test_credit_catalog.py`

**Interfaces:**
- Consumes: `CreditAccount` (`.limite_actuelle`, `.statut`), `CreditScoreEntry` (`.date`, `.score`), `CreditActionRule` (`.seuil_score`, `.type`, `.montant_estime`) — all from `app.models.credit` (Task 1).
- Produces: `build_plan(accounts, score_history, rules, date_cible: date, today: date) -> dict` with keys `marge_actuelle: float`, `historique_score: list[dict]` (`date`, `score`), `historique_marge: list[dict]` (`date`, `marge_totale`), `projection_score: list[dict]` (`date`, `score`), `projection_marge: list[dict]` (`date`, `marge_totale`), `actions: list[dict]` (`date`, `type`, `seuil_score`, `montant_estime`), `projection_possible: bool`.

- [ ] **Step 1: Delete the old catalog module and its test**

```bash
git rm backend/app/services/finance/credit/catalog.py backend/tests/test_finance/test_credit_catalog.py
```

- [ ] **Step 2: Write the failing tests**

Replace the full content of `backend/tests/test_finance/test_credit_planner.py`:
```python
"""Planner marge de crédit v2 : simulation par seuils de score."""

import datetime as dt

from app.models.credit import CreditAccount, CreditActionRule, CreditScoreEntry
from app.services.finance.credit.planner import build_plan


def _account(limite=700, statut="actif"):
    return CreditAccount(
        institution="Desjardins", produit="Carte Mastercard", limite_actuelle=limite,
        date_ouverture=dt.date(2025, 9, 1), statut=statut,
    )


def test_less_than_two_score_points_returns_no_projection():
    plan = build_plan([_account()], [], [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["projection_possible"] is False
    assert plan["projection_score"] == []
    assert plan["projection_marge"] == []
    assert plan["actions"] == []
    assert plan["historique_marge"] == [{"date": dt.date(2026, 7, 1), "marge_totale": 700.0}]

    one_score = [CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x")]
    plan2 = build_plan([_account()], one_score, [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan2["projection_possible"] is False


def test_closed_accounts_excluded_from_marge_actuelle():
    accounts = [_account(limite=700, statut="actif"), _account(limite=5000, statut="ferme")]
    plan = build_plan(accounts, [], [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["marge_actuelle"] == 700.0


def test_no_rules_defined_still_projects_score_and_margin():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x"),
        CreditScoreEntry(date=dt.date(2026, 7, 1), score=680, source="y"),
    ]
    plan = build_plan([_account()], scores, [], date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))
    assert plan["actions"] == []
    assert plan["projection_possible"] is True
    assert len(plan["projection_score"]) == 3  # juillet, août, septembre 2026
    assert plan["projection_marge"][-1]["marge_totale"] == 700.0  # jamais modifiée sans règle


def test_single_rule_triggers_at_correct_month_and_updates_margin_and_score():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=650, source="x"),
        CreditScoreEntry(date=dt.date(2026, 7, 1), score=680, source="y"),
    ]
    # pente = (680-650)/6 = 5 pts/mois. Juillet: 685 (pas de trigger). Août: 690 (trigger).
    rules = [CreditActionRule(seuil_score=690, type="hausse", montant_estime=1000)]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 9, 1), today=dt.date(2026, 7, 1))

    assert plan["actions"] == [
        {"date": dt.date(2026, 8, 1), "type": "hausse", "seuil_score": 690, "montant_estime": 1000.0},
    ]
    aout = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 8, 1))
    assert aout["marge_totale"] == 1700.0  # 700 + 1000
    aout_score = next(p for p in plan["projection_score"] if p["date"] == dt.date(2026, 8, 1))
    assert aout_score["score"] == 680.0  # 690 - 10 (impact de l'action)
    sept = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 9, 1))
    assert sept["marge_totale"] == 1700.0  # règle déjà consommée, ne se redéclenche pas


def test_multiple_rules_can_trigger_same_month_when_score_jumps_fast():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=600, source="x"),
        CreditScoreEntry(date=dt.date(2026, 3, 1), score=700, source="y"),
    ]
    # pente = (700-600)/2 = 50 pts/mois. Mars: 700+50=750 -> franchit 720 ET 740 le même mois.
    rules = [
        CreditActionRule(seuil_score=720, type="hausse", montant_estime=500),
        CreditActionRule(seuil_score=740, type="nouvelle_carte", montant_estime=1000),
    ]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 4, 1), today=dt.date(2026, 3, 1))

    assert [a["seuil_score"] for a in plan["actions"]] == [720, 740]
    assert all(a["date"] == dt.date(2026, 3, 1) for a in plan["actions"])
    mars = next(p for p in plan["projection_marge"] if p["date"] == dt.date(2026, 3, 1))
    assert mars["marge_totale"] == 2200.0  # 700 + 500 + 1000


def test_rules_consumed_in_ascending_threshold_order_regardless_of_input_order():
    scores = [
        CreditScoreEntry(date=dt.date(2026, 1, 1), score=600, source="x"),
        CreditScoreEntry(date=dt.date(2026, 3, 1), score=700, source="y"),
    ]
    rules = [
        CreditActionRule(seuil_score=740, type="nouvelle_carte", montant_estime=1000),
        CreditActionRule(seuil_score=720, type="hausse", montant_estime=500),
    ]
    plan = build_plan([_account()], scores, rules, date_cible=dt.date(2026, 4, 1), today=dt.date(2026, 3, 1))
    assert [a["seuil_score"] for a in plan["actions"]] == [720, 740]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_planner.py -v`
Expected: FAIL (old `build_plan` signature doesn't match; `catalog` module already deleted so old planner.py would also fail to import)

- [ ] **Step 4: Rewrite the planner module**

Replace the full content of `backend/app/services/finance/credit/planner.py`:
```python
"""Simulation mois par mois du score de crédit et de la marge totale (#marge-credit v2).

Fonction pure : ne touche pas la DB. `build_plan` prend l'état courant
(comptes actifs, historique réel de score, règles de seuils définies par
l'utilisateur) et simule mois par mois de `today` à `date_cible` : le score
projeté avance selon la pente déduite des 2 points extrêmes de l'historique
réel, et dès qu'il franchit un seuil non consommé (dans l'ordre croissant),
l'action correspondante s'applique (marge += montant_estime, score -=
SCORE_IMPACT_PAR_ACTION). Aucune notion de banque : les règles ne portent
que sur un seuil de score, un type d'action et un montant estimé.
"""

from __future__ import annotations

import datetime as dt

SCORE_IMPACT_PAR_ACTION = 10  # points perdus après chaque action déclenchée (hausse ou nouvelle carte)


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


def build_plan(accounts, score_history, rules, date_cible: dt.date, today: dt.date) -> dict:
    marge_actuelle = round(sum(a.limite_actuelle for a in accounts if a.statut == "actif"), 2)
    historique_score = [{"date": s.date, "score": s.score} for s in sorted(score_history, key=lambda s: s.date)]
    historique_marge = [{"date": today, "marge_totale": marge_actuelle}]

    if len(historique_score) < 2:
        return {
            "marge_actuelle": marge_actuelle,
            "historique_score": historique_score,
            "historique_marge": historique_marge,
            "projection_score": [],
            "projection_marge": [],
            "actions": [],
            "projection_possible": False,
        }

    premier, dernier = historique_score[0], historique_score[-1]
    mois_ecoules = _months_between(premier["date"], dernier["date"])
    pente = (dernier["score"] - premier["score"]) / mois_ecoules if mois_ecoules > 0 else 0.0

    rules_triees = sorted(rules, key=lambda r: r.seuil_score)
    consumed = [False] * len(rules_triees)

    score = float(dernier["score"])
    marge = marge_actuelle
    actions: list[dict] = []
    projection_score: list[dict] = []
    projection_marge: list[dict] = []

    for month in _month_range(today, date_cible):
        score += pente
        while True:
            next_idx = next(
                (i for i, r in enumerate(rules_triees) if not consumed[i] and score >= r.seuil_score),
                None,
            )
            if next_idx is None:
                break
            rule = rules_triees[next_idx]
            marge += rule.montant_estime
            score -= SCORE_IMPACT_PAR_ACTION
            consumed[next_idx] = True
            actions.append({
                "date": month,
                "type": rule.type,
                "seuil_score": rule.seuil_score,
                "montant_estime": rule.montant_estime,
            })
        projection_score.append({"date": month, "score": round(score, 1)})
        projection_marge.append({"date": month, "marge_totale": round(marge, 2)})

    return {
        "marge_actuelle": marge_actuelle,
        "historique_score": historique_score,
        "historique_marge": historique_marge,
        "projection_score": projection_score,
        "projection_marge": projection_marge,
        "actions": actions,
        "projection_possible": True,
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_planner.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/finance/credit/planner.py backend/tests/test_finance/test_credit_planner.py
git rm backend/app/services/finance/credit/catalog.py backend/tests/test_finance/test_credit_catalog.py
git commit -m "feat(credit): rewrite planner around user-defined score-threshold rules"
```

---

### Task 3: Service layer — rule CRUD + simplified profile/compute_plan

**Files:**
- Modify: `backend/app/services/finance/credit/service.py`
- Modify: `backend/tests/test_finance/test_credit_service.py`

**Interfaces:**
- Consumes: `CreditAccount`, `CreditActionRule`, `CreditProfile`, `CreditScoreEntry` (Task 1); `build_plan` (Task 2, new signature).
- Produces (new/changed vs. v1): `get_or_create_profile(session) -> CreditProfile` (no longer sets `revenu_annuel`/`date_arrivee_canada`), `list_rules(session) -> list[CreditActionRule]`, `create_rule(session, **kwargs) -> CreditActionRule`, `delete_rule(session, rule_id: int) -> bool`, `compute_plan(session) -> dict` (calls `build_plan(accounts, scores, rules, date_cible=profile.date_cible, today=dt.date.today())`). All account/score CRUD functions are unchanged from v1.

- [ ] **Step 1: Write the failing tests**

Replace the full content of `backend/tests/test_finance/test_credit_service.py`:
```python
"""Service CRUD + compute_plan pour le module Marge de crédit (v2, règles à seuils)."""

import datetime as dt

from app.services.finance.credit import service as svc


def _add_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    return dt.date(year, month + 1, 1)


def test_get_or_create_profile_creates_default_on_first_call(mem_session):
    profile = svc.get_or_create_profile(mem_session)
    assert profile.id is not None
    again = svc.get_or_create_profile(mem_session)
    assert again.id == profile.id


def test_update_profile_patches_date_cible(mem_session):
    svc.get_or_create_profile(mem_session)
    updated = svc.update_profile(mem_session, {"date_cible": dt.date(2028, 9, 1)})
    assert updated.date_cible == dt.date(2028, 9, 1)


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


def test_rule_crud_roundtrip(mem_session):
    svc.create_rule(mem_session, seuil_score=720, type="hausse", montant_estime=1000)
    rule_bas = svc.create_rule(mem_session, seuil_score=700, type="hausse", montant_estime=500)
    rules = svc.list_rules(mem_session)
    assert [r.seuil_score for r in rules] == [700, 720]  # triées par seuil croissant

    assert svc.delete_rule(mem_session, rule_bas.id) is True
    assert svc.delete_rule(mem_session, rule_bas.id) is False
    assert [r.seuil_score for r in svc.list_rules(mem_session)] == [720]


def test_compute_plan_produces_roadmap_and_growing_projection(mem_session):
    today = dt.date.today()
    six_months_ago = _add_months(today, -6)
    date_cible = _add_months(today, 12)

    svc.update_profile(mem_session, {"date_cible": date_cible})
    svc.create_account(
        mem_session, institution="Desjardins", produit="Carte Mastercard",
        limite_actuelle=700, date_ouverture=dt.date(2025, 9, 1),
    )
    svc.create_score_entry(mem_session, date=six_months_ago, score=650, source="Credit Karma")
    svc.create_score_entry(mem_session, date=today, score=680, source="Credit Karma")
    svc.create_rule(mem_session, seuil_score=685, type="hausse", montant_estime=1000)

    plan = svc.compute_plan(mem_session)
    assert plan["projection_possible"] is True
    assert len(plan["projection_score"]) > 1
    assert len(plan["actions"]) >= 1
    assert plan["actions"][0]["type"] == "hausse"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_service.py -v`
Expected: FAIL (`svc.create_rule`/`list_rules`/`delete_rule` don't exist yet; `get_or_create_profile` still references removed fields)

- [ ] **Step 3: Rewrite the service module**

Replace the full content of `backend/app/services/finance/credit/service.py`:
```python
"""Service CRUD + calcul du plan pour le module Marge de crédit (#marge-credit)."""

from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.core.timeutil import utcnow
from app.models.credit import CreditAccount, CreditActionRule, CreditProfile, CreditScoreEntry
from app.services.finance.credit.planner import build_plan

DEFAULT_DATE_CIBLE_ANNEES = 3


def get_or_create_profile(session: Session) -> CreditProfile:
    profile = session.exec(select(CreditProfile)).first()
    if profile:
        return profile
    today = dt.date.today()
    profile = CreditProfile(date_cible=today.replace(year=today.year + DEFAULT_DATE_CIBLE_ANNEES))
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


def list_rules(session: Session) -> list[CreditActionRule]:
    return list(session.exec(select(CreditActionRule).order_by(CreditActionRule.seuil_score)).all())


def create_rule(session: Session, **kwargs) -> CreditActionRule:
    rule = CreditActionRule(**kwargs)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: int) -> bool:
    rule = session.get(CreditActionRule, rule_id)
    if not rule:
        return False
    session.delete(rule)
    session.commit()
    return True


def compute_plan(session: Session) -> dict:
    profile = get_or_create_profile(session)
    accounts = list_accounts(session)
    scores = list_score_entries(session)
    rules = list_rules(session)
    return build_plan(accounts, scores, rules, date_cible=profile.date_cible, today=dt.date.today())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_service.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/finance/credit/service.py backend/tests/test_finance/test_credit_service.py
git commit -m "feat(credit): add rule CRUD to service layer, simplify profile defaults"
```

---

### Task 4: API routes — rules CRUD + simplified profile patch

**Files:**
- Modify: `backend/app/api/finance/credit.py`
- Modify: `backend/tests/test_finance/test_credit_api.py`

**Interfaces:**
- Consumes: `app.services.finance.credit.service` (Task 3, including `list_rules`/`create_rule`/`delete_rule`).
- Produces: `GET/POST /finance/credit/rules`, `DELETE /finance/credit/rules/{rule_id}` (new); `CreditProfilePatch` now only has `date_cible`/`nom` fields; all other routes unchanged in shape (only their underlying data changed via Tasks 1-3).

- [ ] **Step 1: Write the failing tests**

Replace the full content of `backend/tests/test_finance/test_credit_api.py`:
```python
"""Intégration API : CRUD marge de crédit + calcul du plan (v2, règles à seuils)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app


def _add_months(d: dt.date, months: int) -> dt.date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    return dt.date(year, month + 1, 1)


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
    assert "date_cible" in r.json()

    r = client.patch("/finance/credit/profile", json={"date_cible": "2028-09-01"})
    assert r.status_code == 200
    assert r.json()["date_cible"] == "2028-09-01"


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


def test_rule_crud(client):
    r = client.post("/finance/credit/rules", json={"seuil_score": 720, "type": "hausse", "montant_estime": 1000})
    assert r.status_code == 201
    rule_id = r.json()["id"]
    assert client.get("/finance/credit/rules").json()[0]["seuil_score"] == 720
    assert client.delete(f"/finance/credit/rules/{rule_id}").status_code == 204
    assert client.delete(f"/finance/credit/rules/{rule_id}").status_code == 404


def test_plan_endpoint_produces_roadmap_and_growing_margin(client):
    today = dt.date.today()
    six_months_ago = _add_months(today, -6)
    date_cible = _add_months(today, 12)

    client.patch("/finance/credit/profile", json={"date_cible": date_cible.isoformat()})
    client.post("/finance/credit/accounts", json={
        "institution": "Desjardins", "produit": "Carte Mastercard",
        "limite_actuelle": 700, "date_ouverture": "2025-09-01",
    })
    client.post("/finance/credit/scores", json={"date": six_months_ago.isoformat(), "score": 650, "source": "Credit Karma"})
    client.post("/finance/credit/scores", json={"date": today.isoformat(), "score": 680, "source": "Credit Karma"})
    client.post("/finance/credit/rules", json={"seuil_score": 685, "type": "hausse", "montant_estime": 1000})

    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["projection_possible"] is True
    assert body["marge_actuelle"] == 700.0
    assert len(body["projection_score"]) > 1
    margins = [p["marge_totale"] for p in body["projection_marge"]]
    assert margins == sorted(margins)
    assert len(body["actions"]) >= 1
    assert body["actions"][0]["type"] == "hausse"


def test_plan_endpoint_without_enough_score_history_has_no_projection(client):
    r = client.get("/finance/credit/plan")
    assert r.status_code == 200
    body = r.json()
    assert body["projection_possible"] is False
    assert body["projection_score"] == []
    assert body["actions"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_api.py -v`
Expected: FAIL (`/finance/credit/rules` routes don't exist; `CreditProfilePatch` still has old fields)

- [ ] **Step 3: Rewrite the API route module**

Replace the full content of `backend/app/api/finance/credit.py`:
```python
"""Marge de crédit : profil, comptes, historique de pointage, règles de seuils, feuille de route."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.finance.credit import service as svc

router = APIRouter()


class CreditProfilePatch(BaseModel):
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


class CreditActionRuleIn(BaseModel):
    seuil_score: int
    type: str
    montant_estime: float = 0.0


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
        raise HTTPException(404, f"Compte {account_id} introuvable")
    return account.model_dump()


@router.delete("/credit/accounts/{account_id}", status_code=204)
def delete_credit_account(account_id: int, session: Session = Depends(get_session)):
    if not svc.delete_account(session, account_id):
        raise HTTPException(404, f"Compte {account_id} introuvable")


@router.get("/credit/scores")
def get_credit_scores(session: Session = Depends(get_session)):
    return [s.model_dump() for s in svc.list_score_entries(session)]


@router.post("/credit/scores", status_code=201)
def create_credit_score(body: CreditScoreEntryIn, session: Session = Depends(get_session)):
    return svc.create_score_entry(session, **body.model_dump()).model_dump()


@router.delete("/credit/scores/{entry_id}", status_code=204)
def delete_credit_score(entry_id: int, session: Session = Depends(get_session)):
    if not svc.delete_score_entry(session, entry_id):
        raise HTTPException(404, f"Pointage {entry_id} introuvable")


@router.get("/credit/rules")
def get_credit_rules(session: Session = Depends(get_session)):
    return [r.model_dump() for r in svc.list_rules(session)]


@router.post("/credit/rules", status_code=201)
def create_credit_rule(body: CreditActionRuleIn, session: Session = Depends(get_session)):
    return svc.create_rule(session, **body.model_dump()).model_dump()


@router.delete("/credit/rules/{rule_id}", status_code=204)
def delete_credit_rule(rule_id: int, session: Session = Depends(get_session)):
    if not svc.delete_rule(session, rule_id):
        raise HTTPException(404, f"Règle {rule_id} introuvable")


@router.get("/credit/plan")
def get_credit_plan(session: Session = Depends(get_session)):
    return svc.compute_plan(session)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_finance/test_credit_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS, no regressions (in particular `tests/test_migrations.py` still passes, and no leftover references to `catalog.py` anywhere)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/finance/credit.py backend/tests/test_finance/test_credit_api.py
git commit -m "feat(credit): add /finance/credit/rules routes, simplify profile patch"
```

---

### Task 5: Frontend API client — updated types + rules endpoints

**Files:**
- Modify: `frontend/lib/finance.ts:65-125` (interfaces block)
- Modify: `frontend/lib/finance.ts:475-486` (financeApi credit entries)

**Interfaces:**
- Consumes: existing `get`, `post`, `patch`, `del` helpers already defined earlier in `frontend/lib/finance.ts` (unchanged, do not redefine).
- Produces: `CreditProfile` (now just `id`, `date_cible`, `nom`), `CreditProfilePatch` (now just `date_cible?`, `nom?`), `CreditAccount`/`CreditAccountCreate`/`CreditScoreEntry`/`CreditScoreEntryCreate` (unchanged), new `CreditActionRule`, `CreditActionRuleCreate`, new `CreditScorePoint`, `CreditMarginPoint`, new-shape `CreditPlanAction`, new-shape `CreditPlan`; `financeApi.creditRules()`, `financeApi.creditRuleCreate(data)`, `financeApi.creditRuleDelete(id)` added; `financeApi.creditPlan()` return type updated.

- [ ] **Step 1: Replace the interfaces block**

In `frontend/lib/finance.ts`, replace lines 65-125 (from `export interface CreditProfile {` through the closing `}` of `export interface CreditPlan {`) with:
```ts
export interface CreditProfile {
  id: number;
  date_cible: string;
  nom: string | null;
}
export interface CreditProfilePatch {
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
export interface CreditActionRule {
  id: number;
  seuil_score: number;
  type: "hausse" | "nouvelle_carte";
  montant_estime: number;
}
export interface CreditActionRuleCreate {
  seuil_score: number;
  type: "hausse" | "nouvelle_carte";
  montant_estime?: number;
}
export interface CreditScorePoint {
  date: string;
  score: number;
}
export interface CreditMarginPoint {
  date: string;
  marge_totale: number;
}
export interface CreditPlanAction {
  date: string;
  type: "hausse" | "nouvelle_carte";
  seuil_score: number;
  montant_estime: number;
}
export interface CreditPlan {
  marge_actuelle: number;
  historique_score: CreditScorePoint[];
  historique_marge: CreditMarginPoint[];
  projection_score: CreditScorePoint[];
  projection_marge: CreditMarginPoint[];
  actions: CreditPlanAction[];
  projection_possible: boolean;
}
```

- [ ] **Step 2: Replace the financeApi credit entries**

In `frontend/lib/finance.ts`, replace lines 475-486 (from `// Marge de crédit` through `creditPlan: () => get<CreditPlan>("/credit/plan"),`) with:
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
  creditRules: () => get<CreditActionRule[]>("/credit/rules"),
  creditRuleCreate: (data: CreditActionRuleCreate) => post<CreditActionRule>("/credit/rules", data),
  creditRuleDelete: (id: number) => del(`/credit/rules/${id}`),
  creditPlan: () => get<CreditPlan>("/credit/plan"),
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors ONLY in `frontend/components/finance/CreditTab.tsx` (it still references the old `CreditPlan` shape — that's fixed in Task 6). No errors anywhere else.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/finance.ts
git commit -m "feat(credit): update frontend types + API client for score-threshold rules"
```

---

### Task 6: `CreditTab` rewrite — two charts, rules section, simplified profile form

**Files:**
- Modify: `frontend/components/finance/CreditTab.tsx` (full rewrite)

**Interfaces:**
- Consumes: `financeApi.creditProfile/creditProfileUpdate/creditAccounts/creditAccountCreate/creditAccountUpdate/creditAccountDelete/creditScores/creditScoreCreate/creditScoreDelete/creditRules/creditRuleCreate/creditRuleDelete/creditPlan` and types `CreditProfile`, `CreditAccount`, `CreditAccountCreate`, `CreditScoreEntry`, `CreditActionRule`, `CreditActionRuleCreate`, `CreditPlanAction`, `CreditScorePoint`, `CreditMarginPoint` (Task 5).
- Produces: `export function CreditTab(): JSX.Element` (same export name, consumed by `frontend/src/app/credit/page.tsx`, unchanged from v1 — no changes needed there).

- [ ] **Step 1: Replace the full file**

Replace the full content of `frontend/components/finance/CreditTab.tsx`:
```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Plus } from "lucide-react";
import {
  financeApi,
  type CreditAccount,
  type CreditAccountCreate,
  type CreditActionRule,
  type CreditActionRuleCreate,
  type CreditMarginPoint,
  type CreditPlanAction,
  type CreditProfile,
  type CreditScoreEntry,
  type CreditScorePoint,
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
  const rules = useQuery({ queryKey: [...KEY, "rules"], queryFn: financeApi.creditRules });

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
  const createRule = useMutation({ mutationFn: financeApi.creditRuleCreate, onSuccess: invalidate });
  const deleteRule = useMutation({ mutationFn: financeApi.creditRuleDelete, onSuccess: invalidate });

  const anyError = plan.isError || profile.isError || accounts.isError || scores.isError || rules.isError;
  const anyLoading =
    plan.isLoading || profile.isLoading || accounts.isLoading || scores.isLoading || rules.isLoading ||
    !plan.data || !profile.data || !accounts.data || !scores.data || !rules.data;

  if (anyError)
    return (
      <div className="text-sm text-[var(--warning-foreground)]">
        Impossible de charger la marge de crédit.{" "}
        <button
          onClick={() => {
            void plan.refetch(); void profile.refetch(); void accounts.refetch();
            void scores.refetch(); void rules.refetch();
          }}
          className="underline hover:text-[var(--foreground)]"
        >
          Réessayer
        </button>
      </div>
    );
  if (anyLoading) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  const dernierScore = plan.data.historique_score.length
    ? plan.data.historique_score[plan.data.historique_score.length - 1].score
    : null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Marge totale actuelle" value={cad(plan.data.marge_actuelle)} strong />
        <Stat label="Score le plus récent" value={dernierScore === null ? "—" : String(dernierScore)} strong />
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        La portion projetée (pointillée) est une estimation basée sur tes règles de seuils et la progression
        passée de ton score — pas une garantie bancaire.
      </p>

      <ScoreChart real={plan.data.historique_score} projected={plan.data.projection_score} />
      <MarginChart real={plan.data.historique_marge} projected={plan.data.projection_marge} />

      <ProfileForm profile={profile.data} onSave={(patch) => updateProfile.mutate(patch)} />

      <AccountsSection
        accounts={accounts.data}
        onCreate={(body) => createAccount.mutate(body)}
        onUpdate={(id, patch) => updateAccount.mutate({ id, patch })}
        onDelete={(id) => deleteAccount.mutate(id)}
      />

      <ScoresSection
        scores={scores.data}
        onCreate={(body) => createScore.mutate(body)}
        onDelete={(id) => deleteScore.mutate(id)}
      />

      <RulesSection
        rules={rules.data}
        onCreate={(body) => createRule.mutate(body)}
        onDelete={(id) => deleteRule.mutate(id)}
      />

      <RoadmapSection actions={plan.data.actions} projectionPossible={plan.data.projection_possible} />
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

/** Construit une polyline pour la portion "réelle" et une pour la portion
 *  "projetée" (reliée au dernier point réel), sur un même axe X d'indices
 *  0..total-1 partagé entre les deux séries. */
function buildDualSeries<T>(real: T[], projected: T[], getValue: (p: T) => number, W: number, H: number) {
  const all = [...real, ...projected];
  if (all.length < 2) return null;
  const values = all.map(getValue);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const total = all.length;
  const x = (i: number) => (i / (total - 1)) * W;
  const y = (v: number) => H - ((v - min) / span) * H;

  const realCoords = real.map((p, i) => `${x(i).toFixed(2)},${y(getValue(p)).toFixed(2)}`).join(" ");
  const projCoords = projected.length
    ? [
        `${x(Math.max(real.length - 1, 0)).toFixed(2)},${y(real.length ? getValue(real[real.length - 1]) : getValue(projected[0])).toFixed(2)}`,
        ...projected.map((p, i) => `${x(real.length + i).toFixed(2)},${y(getValue(p)).toFixed(2)}`),
      ].join(" ")
    : "";

  return { all, min, max, realCoords, projCoords };
}

function ScoreChart({ real, projected }: { real: CreditScorePoint[]; projected: CreditScorePoint[] }) {
  const W = 100, H = 32;
  const built = buildDualSeries(real, projected, (p) => p.score, W, H);
  if (!built)
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Cote de crédit dans le temps</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">Ajoute au moins 2 points de score pour voir la courbe.</p>
      </div>
    );
  const { all, min, max, realCoords, projCoords } = built;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Cote de crédit dans le temps</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Cote de credit dans le temps">
        {realCoords && <polyline points={realCoords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />}
        {projCoords && (
          <polyline points={projCoords} fill="none" stroke="var(--muted-foreground)" strokeWidth={0.8} strokeDasharray="2,1.5" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(all[0].date)} · {min}</span>
        <span>{fmtMonthYear(all[all.length - 1].date)} · {max}</span>
      </div>
    </div>
  );
}

function MarginChart({ real, projected }: { real: CreditMarginPoint[]; projected: CreditMarginPoint[] }) {
  const W = 100, H = 32;
  const built = buildDualSeries(real, projected, (p) => p.marge_totale, W, H);
  if (!built)
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
        <p className="text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale dans le temps</p>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          Ajoute au moins 2 points de score (dans la section pointage) pour voir la projection de marge.
        </p>
      </div>
    );
  const { all, min, max, realCoords, projCoords } = built;
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Marge de crédit totale dans le temps</p>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-24 w-full" role="img" aria-label="Marge de credit totale dans le temps">
        {realCoords && <polyline points={realCoords} fill="none" stroke="var(--ring)" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />}
        {projCoords && (
          <polyline points={projCoords} fill="none" stroke="var(--muted-foreground)" strokeWidth={0.8} strokeDasharray="2,1.5" vectorEffect="non-scaling-stroke" />
        )}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtMonthYear(all[0].date)} · {cad(min)}</span>
        <span>{fmtMonthYear(all[all.length - 1].date)} · {cad(max)}</span>
      </div>
    </div>
  );
}

function ProfileForm({ profile, onSave }: { profile: CreditProfile; onSave: (patch: { date_cible?: string }) => void }) {
  const [cible, setCible] = useState(profile.date_cible);
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--muted-foreground)]">Profil</p>
      <label className="flex items-center gap-1.5 text-sm">
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
      <select
        value={account.statut}
        onChange={(e) => onUpdate(account.id, { statut: e.target.value as "actif" | "ferme" })}
        className="rounded bg-transparent text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        <option value="actif">Actif</option>
        <option value="ferme">Fermé</option>
      </select>
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

function RulesSection({
  rules,
  onCreate,
  onDelete,
}: {
  rules: CreditActionRule[];
  onCreate: (body: CreditActionRuleCreate) => void;
  onDelete: (id: number) => void;
}) {
  const [seuil, setSeuil] = useState("");
  const [type, setType] = useState<"hausse" | "nouvelle_carte">("hausse");
  const [montant, setMontant] = useState("");

  const submit = () => {
    if (!seuil || !montant) return;
    onCreate({ seuil_score: Number(seuil), type, montant_estime: Number(montant) });
    setSeuil(""); setMontant("");
  };

  const sorted = [...rules].sort((a, b) => a.seuil_score - b.seuil_score);

  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Règles de seuils</p>
      <p className="mb-2 text-xs text-[var(--muted-foreground)]">
        À partir de quel score demander une augmentation ou ouvrir une nouvelle carte, et pour combien.
      </p>
      {sorted.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune règle définie.</p>
      ) : (
        <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
          {sorted.map((r) => (
            <li key={r.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="w-20 shrink-0 tabular-nums text-[var(--foreground)]">Score {r.seuil_score}</span>
              <span className="flex-1 text-[var(--muted-foreground)]">
                {r.type === "hausse" ? "Demander une augmentation" : "Ouvrir une nouvelle carte"}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(r.montant_estime)}</span>
              <button onClick={() => onDelete(r.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input value={seuil} onChange={(e) => setSeuil(e.target.value)} type="number" placeholder="Score seuil" className="w-28 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <select value={type} onChange={(e) => setType(e.target.value as "hausse" | "nouvelle_carte")} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
            <option value="hausse">Demander une augmentation</option>
            <option value="nouvelle_carte">Ouvrir une nouvelle carte</option>
          </select>
          <input value={montant} onChange={(e) => setMontant(e.target.value)} type="number" placeholder="Montant estimé" className="w-32 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
          <button onClick={submit} className="flex items-center gap-1.5 rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white">
            <Plus size={14} /> Ajouter
          </button>
        </div>
      </div>
    </div>
  );
}

function RoadmapSection({ actions, projectionPossible }: { actions: CreditPlanAction[]; projectionPossible: boolean }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold text-[var(--muted-foreground)]">Prochaines actions prévues</p>
      {!projectionPossible ? (
        <p className="text-xs text-[var(--muted-foreground)]">Ajoute au moins 2 points de score pour voir les actions prévues.</p>
      ) : actions.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune action prévue avant la date cible avec les règles actuelles.</p>
      ) : (
        <ol className="space-y-2">
          {actions.map((a, i) => (
            <li key={i} className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-[var(--foreground)]">
                  {fmtMonthYear(a.date)} · {a.type === "hausse" ? "Demander une augmentation" : "Ouvrir une nouvelle carte"} (score {a.seuil_score})
                </span>
                <span className="shrink-0 tabular-nums text-[var(--success-foreground)]">+{cad(a.montant_estime)}</span>
              </div>
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
Expected: no errors in `CreditTab.tsx`

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds, `/credit` route present in the output

- [ ] **Step 5: Manual smoke test**

Run: `cd frontend && npm run dev` (and `cd backend && uvicorn app.main:app --reload` if not already running), then open `http://localhost:3000/credit`. Confirm: page loads with no console errors; adding a score entry (need 2+ to see a projection), an account, and a rule all work; the two charts render; the roadmap list updates after adding a rule whose threshold the projected score will cross.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/finance/CreditTab.tsx
git commit -m "feat(credit): rewrite CreditTab with score/margin charts + rules section"
```

---

## Self-Review Notes

- **Spec coverage:** Task 1 → data model section (CreditActionRule + dropped profile fields); Task 2 → moteur section + catalog deletion; Task 3 → service layer section; Task 4 → API section; Task 5+6 → frontend section (two charts, rules CRUD, simplified profile form, compact roadmap). Hors-scope items (real credit-bureau API, multi-point regression, per-account increase caps) are not implemented anywhere in this plan, matching the spec.
- **Type consistency checked:** `CreditActionRuleIn`/`CreditActionRuleCreate` field names (`seuil_score`, `type`, `montant_estime`) match across Tasks 1, 3, 4, 5, 6. `CreditPlan`'s new shape (`historique_score`, `historique_marge`, `projection_score`, `projection_marge`, `actions`, `projection_possible`, `marge_actuelle`) matches the dict returned by `build_plan` (Task 2) verbatim through `compute_plan` (Task 3) and the `/credit/plan` route (Task 4) to the frontend type (Task 5) and its consumers in `CreditTab.tsx` (Task 6).
- **Migration safety:** Task 1's migration drops two NOT NULL columns without a `server_default`, which is safe here because `upgrade()` only removes columns (no data needs backfilling) — this differs from the v1 pattern (which only ever added columns) but follows the same `batch_alter_table` idiom already used elsewhere in this repo for SQLite compatibility.
