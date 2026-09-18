# Module Journal / Humeur (#476) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un module de suivi d'humeur quotidien (humeur, énergie, tags, note) avec tendances et corrélations déterministes (sommeil, sport, poids, dépenses), sans aucune IA.

**Architecture:** Suit le pattern module existant (model SQLModel → service → `routes_<m>.py` → front page/components/lib + entrée `modules.ts`). Le calcul statistique (Pearson, agrégations) est isolé en fonctions pures testées sans DB ; les routes câblent les sources réelles en lecture seule.

**Tech Stack:** Backend FastAPI + SQLModel + Alembic + pytest (uv). Frontend Next.js 15 + TypeScript + Vitest. Commandes backend depuis `backend/` via `uv run …`.

**Référence design :** `docs/superpowers/specs/2026-06-09-journal-humeur-design.md`.

---

## File Structure

- Create `backend/app/models/journal.py` — table `MoodEntry`.
- Create `backend/app/services/journal/__init__.py` — package vide.
- Create `backend/app/services/journal/mood.py` — CRUD + `mood_trends` (pur).
- Create `backend/app/services/journal/correlations.py` — `pearson`, `interpret`, `correlate_series` (purs) + `compute_correlations` (orchestrateur).
- Create `backend/app/api/routes_journal.py` — routes `/journal/*`.
- Modify `backend/app/models/__init__.py` — importer `MoodEntry`.
- Modify `backend/app/api/__init__.py` — enregistrer le routeur.
- Create `backend/alembic/versions/<rev>_journal.py` — migration (autogénérée).
- Create `backend/tests/test_journal/__init__.py`, `test_mood.py`, `test_correlations.py`, `test_api.py`.
- Create `frontend/lib/journal.ts` — client + types.
- Create `frontend/src/app/journal/page.tsx`, `frontend/src/app/journal/loading.tsx`.
- Create `frontend/components/journal/Journal.tsx`, `QuickEntry.tsx`, `TrendsTab.tsx`, `CorrelationsPanel.tsx`.
- Modify `frontend/lib/modules.ts` — entrée du module.

---

## Task 1: Modèle MoodEntry + migration

**Files:**
- Create: `backend/app/models/journal.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<rev>_journal.py` (autogénérée)

- [ ] **Step 1: Créer le modèle**

`backend/app/models/journal.py` :
```python
"""Module Journal / Humeur (#476) — suivi d'humeur quotidien, sans IA."""
import datetime as dt

from sqlmodel import Column, Field, JSON, SQLModel


class MoodEntry(SQLModel, table=True):
    __tablename__ = "mood_entry"
    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True, unique=True)  # une entrée par jour
    humeur: int          # 1-5
    energie: int         # 1-5
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    note: str = ""
    created_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
    updated_at: dt.datetime = Field(default_factory=dt.datetime.utcnow)
```

- [ ] **Step 2: Importer le modèle pour qu'Alembic le voie**

Dans `backend/app/models/__init__.py`, après la ligne `from app.models.habitudes import ...`, ajouter :
```python
from app.models.journal import MoodEntry  # noqa: F401
```

- [ ] **Step 3: Générer la migration**

Run (depuis `backend/`) : `uv run alembic revision --autogenerate -m "journal mood_entry"`
Expected: un fichier `alembic/versions/<rev>_journal.py` créé, contenant `op.create_table("mood_entry", ...)`.

- [ ] **Step 4: Appliquer et vérifier que les modèles == migrations**

Run : `uv run alembic upgrade head && uv run pytest tests/test_migrations.py -q`
Expected: PASS (autogenerate vide après head).

- [ ] **Step 5: Commit**

```bash
git add app/models/journal.py app/models/__init__.py alembic/versions
git commit -m "feat(journal): #476 modele MoodEntry + migration"
```

---

## Task 2: Service CRUD humeur

**Files:**
- Create: `backend/app/services/journal/__init__.py` (vide)
- Create: `backend/app/services/journal/mood.py`
- Test: `backend/tests/test_journal/__init__.py` (vide), `backend/tests/test_journal/test_mood.py`

- [ ] **Step 1: Écrire le test d'upsert (échoue)**

`backend/tests/test_journal/test_mood.py` :
```python
import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.journal import mood as svc


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_upsert_creates_then_updates_same_day(session):
    d = dt.date(2026, 6, 1)
    e1 = svc.upsert_entry(session, d, humeur=3, energie=4, tags=["calme"], note="ok")
    assert e1.id is not None and e1.humeur == 3
    e2 = svc.upsert_entry(session, d, humeur=5, energie=2, tags=["motivé"], note="mieux")
    assert e2.id == e1.id          # même jour -> update, pas de doublon
    assert e2.humeur == 5 and e2.tags == ["motivé"]
    assert len(svc.list_entries(session, d, d)) == 1


def test_upsert_rejects_out_of_range(session):
    with pytest.raises(ValueError):
        svc.upsert_entry(session, dt.date(2026, 6, 1), humeur=6, energie=3, tags=[], note="")
```

- [ ] **Step 2: Lancer le test (échoue)**

Run : `uv run pytest tests/test_journal/test_mood.py -q`
Expected: FAIL (`ModuleNotFoundError: app.services.journal`).

- [ ] **Step 3: Implémenter le service**

Créer `backend/app/services/journal/__init__.py` (vide).
Créer `backend/app/services/journal/mood.py` :
```python
"""CRUD humeur (1 entrée/jour) + agrégations pures (#476)."""
from __future__ import annotations

import datetime as dt

from sqlmodel import Session, select

from app.models.journal import MoodEntry


def _validate(humeur: int, energie: int) -> None:
    for name, v in (("humeur", humeur), ("energie", energie)):
        if not (1 <= int(v) <= 5):
            raise ValueError(f"{name} doit être entre 1 et 5")


def upsert_entry(session: Session, date: dt.date, humeur: int, energie: int,
                 tags: list[str], note: str = "") -> MoodEntry:
    _validate(humeur, energie)
    entry = session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()
    if entry is None:
        entry = MoodEntry(date=date, humeur=humeur, energie=energie, tags=list(tags), note=note)
    else:
        entry.humeur = humeur
        entry.energie = energie
        entry.tags = list(tags)
        entry.note = note
        entry.updated_at = dt.datetime.utcnow()
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_entry(session: Session, date: dt.date) -> MoodEntry | None:
    return session.exec(select(MoodEntry).where(MoodEntry.date == date)).first()


def list_entries(session: Session, debut: dt.date, fin: dt.date) -> list[MoodEntry]:
    return list(session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
        .order_by(MoodEntry.date)  # type: ignore[arg-type]
    ).all())


def delete_entry(session: Session, date: dt.date) -> bool:
    entry = get_entry(session, date)
    if entry is None:
        return False
    session.delete(entry)
    session.commit()
    return True
```

- [ ] **Step 4: Lancer le test (passe)**

Run : `uv run pytest tests/test_journal/test_mood.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/journal/__init__.py app/services/journal/mood.py tests/test_journal
git commit -m "feat(journal): #476 service CRUD humeur (upsert 1/jour)"
```

---

## Task 3: Agrégations de tendances (pures)

**Files:**
- Modify: `backend/app/services/journal/mood.py`
- Test: `backend/tests/test_journal/test_mood.py`

- [ ] **Step 1: Ajouter le test (échoue)**

Ajouter à `backend/tests/test_journal/test_mood.py` :
```python
from app.services.journal.mood import mood_trends


def test_mood_trends_aggregates():
    entries = [
        {"date": "2026-06-01", "humeur": 2, "energie": 3, "tags": ["calme"]},
        {"date": "2026-06-02", "humeur": 4, "energie": 5, "tags": ["calme", "motivé"]},
    ]
    t = mood_trends(entries)
    assert t["n"] == 2
    assert t["moyenne_humeur"] == 3.0
    assert t["distribution_humeur"]["2"] == 1 and t["distribution_humeur"]["4"] == 1
    assert t["tags_freq"][0] == {"tag": "calme", "count": 2}


def test_mood_trends_empty():
    t = mood_trends([])
    assert t["n"] == 0 and t["tags_freq"] == []
```

- [ ] **Step 2: Lancer le test (échoue)**

Run : `uv run pytest tests/test_journal/test_mood.py::test_mood_trends_aggregates -q`
Expected: FAIL (`ImportError: cannot import name 'mood_trends'`).

- [ ] **Step 3: Implémenter `mood_trends`**

Ajouter à la fin de `backend/app/services/journal/mood.py` :
```python
def _moving_average(values: list[float], window: int = 7) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def mood_trends(entries: list[dict]) -> dict:
    """Agrégations déterministes : moyennes, moyenne mobile 7j, distribution, tags."""
    rows = sorted(entries, key=lambda e: e["date"])
    n = len(rows)
    if n == 0:
        return {"n": 0, "moyenne_humeur": 0.0, "moyenne_energie": 0.0,
                "humeur_ma7": [], "energie_ma7": [],
                "distribution_humeur": {str(i): 0 for i in range(1, 6)}, "tags_freq": []}

    humeurs = [float(r["humeur"]) for r in rows]
    energies = [float(r["energie"]) for r in rows]
    dates = [str(r["date"]) for r in rows]
    ma_h = _moving_average(humeurs)
    ma_e = _moving_average(energies)

    distribution = {str(i): 0 for i in range(1, 6)}
    for h in humeurs:
        distribution[str(int(h))] += 1

    counts: dict[str, int] = {}
    for r in rows:
        for tag in r.get("tags", []):
            counts[tag] = counts.get(tag, 0) + 1
    tags_freq = [{"tag": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    return {
        "n": n,
        "moyenne_humeur": round(sum(humeurs) / n, 2),
        "moyenne_energie": round(sum(energies) / n, 2),
        "humeur_ma7": [{"date": d, "value": v} for d, v in zip(dates, ma_h)],
        "energie_ma7": [{"date": d, "value": v} for d, v in zip(dates, ma_e)],
        "distribution_humeur": distribution,
        "tags_freq": tags_freq,
    }
```

- [ ] **Step 4: Lancer les tests (passent)**

Run : `uv run pytest tests/test_journal/test_mood.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/journal/mood.py tests/test_journal/test_mood.py
git commit -m "feat(journal): #476 mood_trends (moyennes, MA7, distribution, tags)"
```

---

## Task 4: Pearson + interprétation (purs)

**Files:**
- Create: `backend/app/services/journal/correlations.py`
- Test: `backend/tests/test_journal/test_correlations.py`

- [ ] **Step 1: Écrire le test (échoue)**

`backend/tests/test_journal/test_correlations.py` :
```python
from app.services.journal.correlations import interpret, pearson


def test_pearson_perfect_positive():
    assert pearson([1, 2, 3], [2, 4, 6]) == 1.0


def test_pearson_perfect_negative():
    assert pearson([1, 2, 3], [6, 4, 2]) == -1.0


def test_pearson_zero_variance_is_none():
    assert pearson([1, 2, 3], [5, 5, 5]) is None


def test_pearson_too_few_points_is_none():
    assert pearson([1], [1]) is None


def test_interpret_strength_and_sign():
    assert interpret(0.75) == {"force": "forte", "signe": "positif"}
    assert interpret(-0.5) == {"force": "modérée", "signe": "négatif"}
    assert interpret(0.1) == {"force": "négligeable", "signe": "positif"}
```

- [ ] **Step 2: Lancer le test (échoue)**

Run : `uv run pytest tests/test_journal/test_correlations.py -q`
Expected: FAIL (`ModuleNotFoundError` correlations).

- [ ] **Step 3: Implémenter**

`backend/app/services/journal/correlations.py` :
```python
"""Corrélations déterministes humeur ↔ autres modules (#476). Aucune IA."""
from __future__ import annotations

import math


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de Pearson, ou None si < 2 paires ou variance nulle."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return round(cov / math.sqrt(vx * vy), 3)


def interpret(r: float) -> dict:
    a = abs(r)
    force = "forte" if a >= 0.6 else "modérée" if a >= 0.4 else "faible" if a >= 0.2 else "négligeable"
    return {"force": force, "signe": "positif" if r >= 0 else "négatif"}
```

- [ ] **Step 4: Lancer le test (passe)**

Run : `uv run pytest tests/test_journal/test_correlations.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/journal/correlations.py tests/test_journal/test_correlations.py
git commit -m "feat(journal): #476 pearson + interpret (purs, testes)"
```

---

## Task 5: Alignement de séries + `correlate_series`

**Files:**
- Modify: `backend/app/services/journal/correlations.py`
- Test: `backend/tests/test_journal/test_correlations.py`

- [ ] **Step 1: Ajouter le test (échoue)**

Ajouter à `backend/tests/test_journal/test_correlations.py` :
```python
from app.services.journal.correlations import correlate_series


def test_correlate_series_intersects_dates():
    mood = {"2026-06-01": 2.0, "2026-06-02": 4.0, "2026-06-03": 3.0}
    target = {"2026-06-01": 4.0, "2026-06-02": 8.0}  # 06-03 absent -> ignoré
    res = correlate_series(mood, target)
    assert res["n"] == 2
    assert res["r"] == 1.0
    assert res["force"] == "forte" and res["signe"] == "positif"


def test_correlate_series_insufficient():
    res = correlate_series({"2026-06-01": 2.0}, {"2026-06-01": 4.0})
    assert res["n"] == 1 and res["r"] is None and res["force"] == "indéterminée"
```

- [ ] **Step 2: Lancer le test (échoue)**

Run : `uv run pytest tests/test_journal/test_correlations.py::test_correlate_series_intersects_dates -q`
Expected: FAIL (`cannot import name 'correlate_series'`).

- [ ] **Step 3: Implémenter**

Ajouter à `backend/app/services/journal/correlations.py` :
```python
def correlate_series(source_by_date: dict[str, float], target_by_date: dict[str, float]) -> dict:
    """Corrèle deux séries datées sur l'intersection de leurs dates."""
    dates = sorted(set(source_by_date) & set(target_by_date))
    xs = [source_by_date[d] for d in dates]
    ys = [target_by_date[d] for d in dates]
    r = pearson(xs, ys)
    if r is None:
        return {"r": None, "force": "indéterminée", "signe": "", "n": len(dates)}
    return {"r": r, "n": len(dates), **interpret(r)}
```

- [ ] **Step 4: Lancer le test (passe)**

Run : `uv run pytest tests/test_journal/test_correlations.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/journal/correlations.py tests/test_journal/test_correlations.py
git commit -m "feat(journal): #476 correlate_series (intersection par date)"
```

---

## Task 6: `compute_correlations` + routes `/journal`

**Files:**
- Modify: `backend/app/services/journal/correlations.py`
- Create: `backend/app/api/routes_journal.py`
- Modify: `backend/app/api/__init__.py`
- Test: `backend/tests/test_journal/test_api.py`

- [ ] **Step 1: Écrire le test d'API (échoue)**

`backend/tests/test_journal/test_api.py` :
```python
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api import api_router  # noqa: F401  (assure l'enregistrement)
from app.core.db import get_session
from app.main import create_app


def _client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = override
    return TestClient(app)


def test_put_then_get_entry():
    client = _client()
    r = client.put("/journal/entries/2026-06-01", json={"humeur": 4, "energie": 3, "tags": ["calme"], "note": "ok"})
    assert r.status_code == 200
    assert r.json()["humeur"] == 4
    g = client.get("/journal/entries/2026-06-01")
    assert g.status_code == 200 and g.json()["tags"] == ["calme"]


def test_get_missing_entry_404():
    client = _client()
    assert client.get("/journal/entries/2030-01-01").status_code == 404


def test_trends_and_correlations_empty_ok():
    client = _client()
    assert client.get("/journal/trends?days=30").status_code == 200
    c = client.get("/journal/correlations?days=90")
    assert c.status_code == 200 and "caveat" in c.json()
```

- [ ] **Step 2: Lancer le test (échoue)**

Run : `uv run pytest tests/test_journal/test_api.py -q`
Expected: FAIL (404 sur `/journal/...`, routeur non enregistré).

- [ ] **Step 3: Implémenter `compute_correlations`**

Ajouter à `backend/app/services/journal/correlations.py` :
```python
import datetime as dt

from sqlmodel import Session, select


def compute_correlations(session: Session, jours: int = 90) -> dict:
    """Corrèle humeur & énergie avec sommeil, sport, poids, dépenses (lecture seule)."""
    from app.models.journal import MoodEntry
    from app.models.sante import MesureSante
    from app.models.entrainement import Seance
    from app.models.budget import BudgetTransaction

    fin = dt.date.today()
    debut = fin - dt.timedelta(days=jours)

    moods = session.exec(
        select(MoodEntry).where(MoodEntry.date >= debut).where(MoodEntry.date <= fin)
    ).all()
    humeur_by = {str(m.date): float(m.humeur) for m in moods}
    energie_by = {str(m.date): float(m.energie) for m in moods}
    mood_dates = list(humeur_by.keys())

    mesures = session.exec(
        select(MesureSante).where(MesureSante.date >= debut).where(MesureSante.date <= fin)
    ).all()
    sommeil_by = {str(m.date): float((m.extra or {})["sommeil_h"])
                  for m in mesures if (m.extra or {}).get("sommeil_h") is not None}
    poids_by = {str(m.date): float(m.poids) for m in mesures if m.poids is not None}

    seances = session.exec(select(Seance)).all()
    seance_days = {s.date.date().isoformat() for s in seances if debut <= s.date.date() <= fin}
    # Sport = 0/1 sur TOUS les jours d'humeur (variance nécessaire au calcul).
    sport_by = {d: (1.0 if d in seance_days else 0.0) for d in mood_dates}

    txns = session.exec(
        select(BudgetTransaction).where(BudgetTransaction.date >= debut).where(BudgetTransaction.date <= fin)
    ).all()
    depenses_by: dict[str, float] = {}
    for t in txns:
        depenses_by[str(t.date)] = depenses_by.get(str(t.date), 0.0) + float(t.montant)

    targets = {"sommeil": sommeil_by, "sport": sport_by, "poids": poids_by, "depenses": depenses_by}
    correlations = []
    for source_name, source in (("humeur", humeur_by), ("energie", energie_by)):
        for cible, target in targets.items():
            res = correlate_series(source, target)
            correlations.append({"source": source_name, "cible": cible, **res})

    return {"caveat": "corrélation ≠ causalité", "jours": jours, "correlations": correlations}
```

- [ ] **Step 4: Implémenter les routes**

`backend/app/api/routes_journal.py` :
```python
"""Routes module Journal / Humeur (#476)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.db import get_session
from app.services.journal import mood as mood_svc
from app.services.journal.correlations import compute_correlations

router = APIRouter()


class MoodEntryIn(BaseModel):
    humeur: int
    energie: int
    tags: list[str] = []
    note: str = ""


def _serialize(e) -> dict:
    return {"id": e.id, "date": str(e.date), "humeur": e.humeur,
            "energie": e.energie, "tags": e.tags, "note": e.note}


@router.get("/entries")
def list_entries(session: Session = Depends(get_session),
                 from_: dt.date | None = None, to: dt.date | None = None):
    fin = to or dt.date.today()
    debut = from_ or (fin - dt.timedelta(days=30))
    return [_serialize(e) for e in mood_svc.list_entries(session, debut, fin)]


@router.get("/entries/{date}")
def get_entry(date: dt.date, session: Session = Depends(get_session)):
    e = mood_svc.get_entry(session, date)
    if e is None:
        raise HTTPException(404, "Aucune entrée pour ce jour")
    return _serialize(e)


@router.put("/entries/{date}")
def put_entry(date: dt.date, body: MoodEntryIn, session: Session = Depends(get_session)):
    try:
        e = mood_svc.upsert_entry(session, date, body.humeur, body.energie, body.tags, body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return _serialize(e)


@router.delete("/entries/{date}", status_code=204)
def delete_entry(date: dt.date, session: Session = Depends(get_session)):
    mood_svc.delete_entry(session, date)


@router.get("/trends")
def trends(days: int = 30, session: Session = Depends(get_session)):
    fin = dt.date.today()
    debut = fin - dt.timedelta(days=days)
    entries = [_serialize(e) for e in mood_svc.list_entries(session, debut, fin)]
    return mood_svc.mood_trends(entries)


@router.get("/correlations")
def correlations(days: int = 90, session: Session = Depends(get_session)):
    return compute_correlations(session, days)
```

Dans `backend/app/api/__init__.py` : ajouter `routes_journal,` à la liste d'imports (ordre alphabétique, après `routes_habitudes,`) et la ligne d'enregistrement après celle de habitudes :
```python
api_router.include_router(routes_journal.router, prefix="/journal", tags=["journal"])
```

- [ ] **Step 5: Lancer les tests (passent)**

Run : `uv run pytest tests/test_journal/ -q`
Expected: PASS (tous les tests journal).

- [ ] **Step 6: Commit**

```bash
git add app/services/journal/correlations.py app/api/routes_journal.py app/api/__init__.py tests/test_journal/test_api.py
git commit -m "feat(journal): #476 compute_correlations + routes /journal"
```

---

## Task 7: Client & types frontend

**Files:**
- Create: `frontend/lib/journal.ts`

- [ ] **Step 1: Implémenter le client**

`frontend/lib/journal.ts` :
```typescript
import { api } from "./api";

export interface MoodEntry {
  id?: number; date: string; humeur: number; energie: number; tags: string[]; note: string;
}
export interface MoodTrends {
  n: number; moyenne_humeur: number; moyenne_energie: number;
  humeur_ma7: { date: string; value: number }[];
  energie_ma7: { date: string; value: number }[];
  distribution_humeur: Record<string, number>;
  tags_freq: { tag: string; count: number }[];
}
export interface Correlation {
  source: string; cible: string; r: number | null; force: string; signe: string; n: number;
}
export interface CorrelationsOut { caveat: string; jours: number; correlations: Correlation[]; }

export const TAGS_EMOTIONS = [
  "calme", "heureux", "motivé", "fatigué", "anxieux",
  "irrité", "triste", "serein", "stressé", "reconnaissant",
];

export const journalApi = {
  entries: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    return api<MoodEntry[]>(`/journal/entries?${q}`);
  },
  getEntry: (date: string) => api<MoodEntry>(`/journal/entries/${date}`),
  putEntry: (date: string, body: Omit<MoodEntry, "id" | "date">) =>
    api<MoodEntry>(`/journal/entries/${date}`, { method: "PUT", body: JSON.stringify(body) }),
  trends: (days = 30) => api<MoodTrends>(`/journal/trends?days=${days}`),
  correlations: (days = 90) => api<CorrelationsOut>(`/journal/correlations?days=${days}`),
};
```

- [ ] **Step 2: Vérifier la compilation**

Run (depuis `frontend/`) : `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add lib/journal.ts
git commit -m "feat(journal): #476 client + types frontend"
```

---

## Task 8: QuickEntry (saisie du jour)

**Files:**
- Create: `frontend/components/journal/QuickEntry.tsx`

- [ ] **Step 1: Implémenter**

`frontend/components/journal/QuickEntry.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { journalApi, TAGS_EMOTIONS, type MoodEntry } from "@/lib/journal";

const todayISO = () => new Date().toISOString().slice(0, 10);

function Scale({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 text-sm text-[var(--muted-foreground)]">{label}</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} onClick={() => onChange(n)}
          className={`h-8 w-8 rounded-full border text-sm ${value === n
            ? "bg-[var(--ring)] text-white border-[var(--ring)]"
            : "border-[var(--border)] hover:border-[var(--ring)]"}`}>{n}</button>
      ))}
    </div>
  );
}

export function QuickEntry({ onSaved }: { onSaved?: () => void }) {
  const date = todayISO();
  const [humeur, setHumeur] = useState(3);
  const [energie, setEnergie] = useState(3);
  const [tags, setTags] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    journalApi.getEntry(date).then((e: MoodEntry) => {
      setHumeur(e.humeur); setEnergie(e.energie); setTags(e.tags); setNote(e.note);
    }).catch(() => {});
  }, [date]);

  const toggleTag = (t: string) =>
    setTags((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  const save = async () => {
    setSaving(true);
    try {
      await journalApi.putEntry(date, { humeur, energie, tags, note });
      onSaved?.();
    } finally { setSaving(false); }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <h2 className="text-base font-semibold">Aujourd&apos;hui</h2>
      <Scale label="Humeur" value={humeur} onChange={setHumeur} />
      <Scale label="Énergie" value={energie} onChange={setEnergie} />
      <div className="flex flex-wrap gap-1.5">
        {TAGS_EMOTIONS.map((t) => (
          <button key={t} onClick={() => toggleTag(t)}
            className={`text-xs px-2.5 py-1 rounded-full border ${tags.includes(t)
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--ring)]"}`}>{t}</button>
        ))}
      </div>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note du jour (optionnel)"
        className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] p-2 text-sm" rows={2} />
      <button onClick={() => void save()} disabled={saving}
        className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50">
        {saving ? "…" : "Enregistrer"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier la compilation**

Run : `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add components/journal/QuickEntry.tsx
git commit -m "feat(journal): #476 QuickEntry (saisie humeur/energie/tags/note)"
```

---

## Task 9: TrendsTab (tendances)

**Files:**
- Create: `frontend/components/journal/TrendsTab.tsx`

- [ ] **Step 1: Implémenter**

`frontend/components/journal/TrendsTab.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { journalApi, type MoodTrends } from "@/lib/journal";

export function TrendsTab() {
  const [t, setT] = useState<MoodTrends | null>(null);
  useEffect(() => { journalApi.trends(30).then(setT).catch(() => {}); }, []);
  if (!t) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  if (t.n === 0) return <p className="text-sm text-[var(--muted-foreground)]">Aucune entrée sur 30 jours.</p>;

  const maxTag = t.tags_freq[0]?.count || 1;
  // Sparkline 1-5 : convertit une série MA7 en polyline SVG (viewBox 100x40).
  const line = (pts: { value: number }[]) => {
    if (pts.length < 2) return "";
    return pts.map((p, i) => {
      const x = (i / (pts.length - 1)) * 100;
      const y = 40 - ((p.value - 1) / 4) * 40; // humeur 1..5 -> y 40..0
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  };
  return (
    <div className="space-y-5">
      <div className="flex gap-6 text-sm">
        <span>Humeur moyenne : <strong>{t.moyenne_humeur}</strong>/5</span>
        <span>Énergie moyenne : <strong>{t.moyenne_energie}</strong>/5</span>
        <span className="text-[var(--muted-foreground)]">{t.n} jours</span>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Humeur (—) &amp; énergie (·) — moyenne mobile 7 j</h3>
        <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="w-full h-24 rounded border border-[var(--border)]">
          <polyline points={line(t.humeur_ma7)} fill="none" stroke="var(--ring)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          <polyline points={line(t.energie_ma7)} fill="none" stroke="var(--muted-foreground)" strokeWidth="1" strokeDasharray="3 2" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Distribution de l&apos;humeur</h3>
        <div className="flex items-end gap-2 h-24">
          {[1, 2, 3, 4, 5].map((n) => {
            const c = t.distribution_humeur[String(n)] || 0;
            const max = Math.max(...Object.values(t.distribution_humeur), 1);
            return (
              <div key={n} className="flex flex-col items-center gap-1">
                <div className="w-8 rounded-t bg-[var(--ring)]" style={{ height: `${(c / max) * 100}%` }} />
                <span className="text-xs text-[var(--muted-foreground)]">{n}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Émotions fréquentes</h3>
        <div className="space-y-1">
          {t.tags_freq.map((f) => (
            <div key={f.tag} className="flex items-center gap-2 text-xs">
              <span className="w-24">{f.tag}</span>
              <div className="h-2 rounded-full bg-[var(--ring)]" style={{ width: `${(f.count / maxTag) * 160}px` }} />
              <span className="text-[var(--muted-foreground)]">{f.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Vérifier la compilation**

Run : `npx tsc --noEmit`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add components/journal/TrendsTab.tsx
git commit -m "feat(journal): #476 TrendsTab (moyennes, distribution, tags)"
```

---

## Task 10: CorrelationsPanel + page + module

**Files:**
- Create: `frontend/components/journal/CorrelationsPanel.tsx`
- Create: `frontend/components/journal/Journal.tsx`
- Create: `frontend/src/app/journal/page.tsx`, `frontend/src/app/journal/loading.tsx`
- Modify: `frontend/lib/modules.ts`

- [ ] **Step 1: CorrelationsPanel**

`frontend/components/journal/CorrelationsPanel.tsx` :
```tsx
"use client";

import { useEffect, useState } from "react";
import { journalApi, type CorrelationsOut } from "@/lib/journal";

const LABEL: Record<string, string> = {
  sommeil: "Sommeil", sport: "Sport", poids: "Poids", depenses: "Dépenses",
};

export function CorrelationsPanel() {
  const [data, setData] = useState<CorrelationsOut | null>(null);
  useEffect(() => { journalApi.correlations(90).then(setData).catch(() => {}); }, []);
  if (!data) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  const humeur = data.correlations.filter((c) => c.source === "humeur");

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--muted-foreground)]">
        Humeur vs… (90 j) · {data.caveat}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {humeur.map((c) => (
          <div key={c.cible} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <div className="text-sm font-medium">{LABEL[c.cible] ?? c.cible}</div>
            {c.r == null ? (
              <div className="text-xs text-[var(--muted-foreground)]">Pas assez de données ({c.n} j)</div>
            ) : (
              <div className="text-xs">
                <span className="font-mono">r = {c.r}</span> · corrélation {c.force} {c.signe} · {c.n} j
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Journal (assemblage onglets)**

`frontend/components/journal/Journal.tsx` :
```tsx
"use client";

import { useState } from "react";
import { QuickEntry } from "./QuickEntry";
import { TrendsTab } from "./TrendsTab";
import { CorrelationsPanel } from "./CorrelationsPanel";

export default function Journal() {
  const [refresh, setRefresh] = useState(0);
  return (
    <div className="space-y-6 p-4 max-w-3xl mx-auto">
      <h1 className="text-xl font-semibold">Journal · Humeur</h1>
      <QuickEntry onSaved={() => setRefresh((r) => r + 1)} />
      <section key={refresh} className="space-y-6">
        <TrendsTab />
        <CorrelationsPanel />
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Page + loading**

`frontend/src/app/journal/page.tsx` :
```tsx
import Journal from "@/components/journal/Journal";

export const metadata = { title: "Journal — Mission Control" };

export default function JournalPage() {
  return <Journal />;
}
```

`frontend/src/app/journal/loading.tsx` :
```tsx
import { PageSkeleton } from "@/components/PageSkeleton";

export default function Loading() {
  return <PageSkeleton />;
}
```

- [ ] **Step 4: Entrée dans la sidebar**

Dans `frontend/lib/modules.ts` : ajouter `Smile,` à l'import lucide en tête, puis ajouter l'objet module **dans le tableau `MODULES`, juste après l'entrée `sante`** (groupe `"Santé & Sport"`, déjà déclaré dans `ModuleGroup`/`GROUP_ORDER` ; `MODULE_GROUPS` est dérivé automatiquement, rien d'autre à modifier) :
```tsx
  {
    slug: "journal",
    label: "Journal",
    description: "Suivi d'humeur & tendances.",
    icon: Smile,
    group: "Santé & Sport",
    ready: true,
  },
```

- [ ] **Step 5: Vérifier compilation + lint du dossier**

Run : `npx tsc --noEmit && npx eslint components/journal lib/journal.ts`
Expected: tsc exit 0 ; eslint sans nouvelle erreur sur ces fichiers.

- [ ] **Step 6: Commit**

```bash
git add components/journal/CorrelationsPanel.tsx components/journal/Journal.tsx \
  src/app/journal lib/modules.ts
git commit -m "feat(journal): #476 page Journal (corrélations, assemblage, sidebar)"
```

---

## Task 11: Types OpenAPI + vérification finale + suivi

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/openapi.json` (régénérés)
- Modify: `orchestration/AMELIORATIONS_200.txt`

- [ ] **Step 1: Régénérer les types**

Run (depuis la racine) : `make gen-types`
Expected: `frontend/lib/types.ts` régénéré incluant les schémas `/journal`.

- [ ] **Step 2: Suite de tests backend journal + santé/budget non cassés**

Run (depuis `backend/`) : `uv run pytest tests/test_journal tests/test_health.py tests/test_openapi_contract.py -q`
Expected: PASS.

- [ ] **Step 3: Vérification front**

Run (depuis `frontend/`) : `rm -rf .next && npx tsc --noEmit && npm test`
Expected: tsc exit 0 ; vitest PASS.

- [ ] **Step 4: Marquer l'item FINIS (daté)**

Dans `orchestration/AMELIORATIONS_200.txt`, remplacer la ligne 476 par :
```
476. [L](***) Module « Journaling » : prompts statiques (banque de questions) + saisie d'humeur manuelle + tendances déterministes (sans IA).   ← FINIS ✓ (2026-06-09) module Journal/Humeur : MoodEntry (1/jour) + tendances (moyennes/MA7/distribution/tags) + corrélations Pearson humeur/énergie vs sommeil/sport/poids/dépenses ; page /journal (QuickEntry, TrendsTab, CorrelationsPanel) ; sans IA. Tests TDD.
```

- [ ] **Step 5: Commit final**

```bash
git add frontend/lib/types.ts frontend/openapi.json orchestration/AMELIORATIONS_200.txt
git commit -m "feat(journal): #476 types OpenAPI + item marque FINIS"
```

---

## Notes de mise en œuvre

- **Sport en 0/1** : la série sport couvre tous les jours d'humeur (1 si séance, 0 sinon) pour garantir de la variance ; sinon Pearson renverrait `None`.
- **Dépenses** : somme des `montant` du jour (indicateur de flux ; pas de filtrage type car le modèle `BudgetTransaction` n'a pas de champ type).
- **Sommeil/Poids** : lus depuis `MesureSante` (`extra["sommeil_h"]`, `poids`), uniquement les jours renseignés.
- **Pas d'IA** : toutes les analyses sont des calculs statistiques déterministes.
- **Heatmap calendrier** : le spec la mentionnait ; reportée (YAGNI v1). TrendsTab livre la courbe MA7 (humeur+énergie) + distribution + fréquence des tags, ce qui couvre le besoin « tendances ». La heatmap pourra être ajoutée dans une itération ultérieure.
- **ChartFrame** : non utilisé ici (sparkline SVG inline suffit et évite de coupler au composant) ; cohérent avec le reste si on veut migrer plus tard.
