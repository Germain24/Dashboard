# Garde-robe « Objectif » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un onglet « Objectif » à la Garde-robe qui montre, pour chacun des 55 types de vêtements, des emplacements (251 au total) avec une barre 0→100 positionnant la marque possédée sur l'échelle Qualité/Prix → Qualité Max, les emplacements vides, et les pièces en excédent (rouge).

**Architecture :** `data/imports/Vetements.xlsx` est la **source de vérité** (master). Un endpoint `POST /garderobe/objectif/sync` lit l'Excel (openpyxl) et remplit une table cache `objectif_type`. L'onglet lit `GET /garderobe/objectif`, qui croise le cache avec les vêtements possédés reliés via une nouvelle colonne `Vetement.type_objectif`. Toute la logique de positionnement/remplissage est dans des fonctions pures testables.

**Tech Stack :** Backend FastAPI + SQLModel + Alembic + openpyxl ; Frontend Next.js + TanStack Query + Vitest. Aucune nouvelle dépendance (openpyxl 3.1.5 déjà installé).

## Global Constraints

- Backend : Python exécuté via `uv run` depuis `backend/`. Tests : `uv run pytest`.
- Frontend : tests via `npx vitest run` depuis `frontend/`.
- UI en français (labels, sous-titres).
- **Excel = master** : l'app ne fait que lire/synchroniser. Aucun écran d'édition d'échelle/quantité dans l'app. Le re-sync **écrase** la table cache.
- Chemin du master : `settings.imports_dir / "Vetements.xlsx"` (= `data/imports/Vetements.xlsx`).
- Structure du fichier : feuille 0, ligne 0 = en-tête (`[None, "Quantité objectif", "Qualité/Prix", "Qualité 1"…]`), lignes 1+ = `[nom_type, quantité, marque_QP, marque_1, …]`, colonnes marque vides = `None`. 55 types, somme des quantités = 251, 119 marques distinctes.
- Hors scope (projets séparés ultérieurs) : logos de marques, conseils d'achat combinatoires, enrichissement BonneGueule de l'Excel.

---

## File Structure

**Backend (créer) :**
- `backend/app/services/garderobe/objectif.py` — fonctions pures (`build_echelle`, `brand_position`, `fill_slots`).
- `backend/app/services/garderobe/objectif_import.py` — `parse_objectif_xlsx`, `sync_objectif`.
- `backend/app/api/garderobe/objectif.py` — routeur `GET /objectif`, `POST /objectif/sync`.
- `backend/alembic/versions/20260630_1200_v610_objectif_garderobe.py` — migration.
- `backend/tests/test_garderobe/test_objectif.py` — tests fonctions pures.
- `backend/tests/test_garderobe/test_objectif_import.py` — tests parser/sync.
- `backend/tests/test_garderobe/test_objectif_api.py` — tests API.

**Backend (modifier) :**
- `backend/app/models/garderobe.py` — nouvelle table `ObjectifType` + colonne `Vetement.type_objectif`.
- `backend/app/models/__init__.py` — enregistrer `ObjectifType`.
- `backend/app/api/garderobe/__init__.py` — monter le routeur `objectif`.
- `backend/app/api/garderobe/schemas.py` — schémas `Emplacement`, `ObjectifTypeOut`, `ObjectifResponse` + champ `type_objectif`.
- `backend/app/api/garderobe/common.py` — propager `type_objectif`.

**Frontend (modifier/créer) :**
- `frontend/lib/garderobe.ts` — types `Emplacement`/`ObjectifTypeOut`/`ObjectifResponse`, champ `type_objectif`, méthodes `getObjectif`/`syncObjectif`.
- `frontend/lib/queries/garderobe.ts` — hooks `useObjectif`, `useSyncObjectif`.
- `frontend/components/garderobe/ObjectifTab.tsx` — onglet (créer).
- `frontend/components/garderobe/ObjectifBar.tsx` — barre 0→100 (créer).
- `frontend/components/garderobe/Garderobe.tsx` — onglet branché.
- `frontend/__tests__/queries/garderobe.test.tsx` — étendre le mock + un test.

---

## Task 1: Fonctions pures de positionnement

**Files:**
- Create: `backend/app/services/garderobe/objectif.py`
- Test: `backend/tests/test_garderobe/test_objectif.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `build_echelle(brands: list) -> list[str]` — dédup (casefold) en conservant l'ordre, strip, drop vides.
  - `brand_position(echelle: list[str], marque: str | None) -> float | None` — `None` si marque absente/None ; `0.0` si échelle de longueur ≤ 1 ; sinon `round(idx/(len-1)*100, 1)`.
  - `fill_slots(echelle: list[str], quantite: int, owned: list[dict]) -> dict` — `owned` = `[{"id","nom","marque"}]`. Retourne `{"emplacements": list[dict], "excedent": list[dict], "rempli": int}`. Chaque dict d'emplacement rempli/excédent : `{"statut": "rempli", "vetement_id", "vetement_nom", "marque", "position": float|None, "hors_echelle": bool}` ; vide : `{"statut":"vide","vetement_id":None,"vetement_nom":None,"marque":None,"position":None,"hors_echelle":False}`. `len(emplacements) == quantite`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_objectif.py
"""Fonctions pures de l'onglet Objectif (échelle Q/P → Max)."""
from __future__ import annotations

from app.services.garderobe.objectif import (
    brand_position,
    build_echelle,
    fill_slots,
)


def test_build_echelle_dedup_strip_order():
    assert build_echelle(["Uniqlo U", "Beams Plus", None, " Beams Plus ", "Auralee", ""]) == [
        "Uniqlo U",
        "Beams Plus",
        "Auralee",
    ]


def test_brand_position_extremes_and_middle():
    ech = ["Uniqlo U", "Beams Plus", "Graphpaper", "Auralee", "Visvim"]  # 5 marques
    assert brand_position(ech, "Uniqlo U") == 0.0
    assert brand_position(ech, "Visvim") == 100.0
    assert brand_position(ech, "Graphpaper") == 50.0


def test_brand_position_absent_or_none():
    ech = ["Uniqlo U", "Visvim"]
    assert brand_position(ech, "Lacoste") is None
    assert brand_position(ech, None) is None


def test_brand_position_case_insensitive_and_single():
    assert brand_position(["Uniqlo U", "Visvim"], "visvim") == 100.0
    assert brand_position(["Auralee"], "Auralee") == 0.0  # échelle de longueur 1


def test_fill_slots_partial_fills_then_empty():
    ech = ["Uniqlo U", "Beams Plus", "Visvim"]
    owned = [{"id": "v1", "nom": "Tee gris", "marque": "Visvim"}]
    res = fill_slots(ech, 3, owned)
    assert res["rempli"] == 1
    assert len(res["emplacements"]) == 3
    assert res["emplacements"][0]["statut"] == "rempli"
    assert res["emplacements"][0]["position"] == 100.0
    assert res["emplacements"][1]["statut"] == "vide"
    assert res["excedent"] == []


def test_fill_slots_excess_goes_red():
    ech = ["Uniqlo U", "Visvim"]
    owned = [
        {"id": "a", "nom": "A", "marque": "Visvim"},
        {"id": "b", "nom": "B", "marque": "Uniqlo U"},
        {"id": "c", "nom": "C", "marque": "Visvim"},
    ]
    res = fill_slots(ech, 1, owned)  # objectif 1, possédés 3
    assert res["rempli"] == 1
    assert len(res["emplacements"]) == 1
    assert len(res["excedent"]) == 2
    # meilleure qualité conservée dans l'emplacement
    assert res["emplacements"][0]["position"] == 100.0


def test_fill_slots_unknown_brand_is_off_scale_and_last():
    ech = ["Uniqlo U", "Visvim"]
    owned = [
        {"id": "a", "nom": "A", "marque": "Lacoste"},   # hors échelle
        {"id": "b", "nom": "B", "marque": "Visvim"},
    ]
    res = fill_slots(ech, 1, owned)
    assert res["emplacements"][0]["marque"] == "Visvim"  # positionné d'abord
    assert res["excedent"][0]["marque"] == "Lacoste"
    assert res["excedent"][0]["hors_echelle"] is True
    assert res["excedent"][0]["position"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_objectif.py -v` (depuis `backend/`)
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.garderobe.objectif'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/garderobe/objectif.py
"""Fonctions pures de l'onglet « Objectif » de la garde-robe.

L'échelle d'un type va de Qualité/Prix (index 0 → position 0) à Qualité Max
(dernier index → position 100). La position d'une marque possédée sur cette
échelle pilote la barre 0→100 de l'onglet.
"""
from __future__ import annotations


def build_echelle(brands: list) -> list[str]:
    """Liste de marques ordonnée, dédupliquée (insensible à la casse), sans vides."""
    out: list[str] = []
    seen: set[str] = set()
    for b in brands:
        if not b:
            continue
        name = str(b).strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def brand_position(echelle: list[str], marque: str | None) -> float | None:
    """Position 0..100 de `marque` dans `echelle`, ou None si absente/None."""
    if not marque:
        return None
    key = str(marque).strip().casefold()
    idx = next((i for i, b in enumerate(echelle) if b.casefold() == key), None)
    if idx is None:
        return None
    n = len(echelle)
    if n <= 1:
        return 0.0
    return round(idx / (n - 1) * 100.0, 1)


def _empty_slot() -> dict:
    return {
        "statut": "vide",
        "vetement_id": None,
        "vetement_nom": None,
        "marque": None,
        "position": None,
        "hors_echelle": False,
    }


def fill_slots(echelle: list[str], quantite: int, owned: list[dict]) -> dict:
    """Répartit les pièces possédées sur `quantite` emplacements.

    Tri par qualité décroissante (meilleure marque d'abord) ; les pièces dont la
    marque n'est pas dans l'échelle (position None) passent en dernier. Les
    `quantite` premières remplissent les emplacements ; le reste = excédent.
    """
    enriched: list[dict] = []
    for o in owned:
        pos = brand_position(echelle, o.get("marque"))
        enriched.append(
            {
                "statut": "rempli",
                "vetement_id": o.get("id"),
                "vetement_nom": o.get("nom"),
                "marque": o.get("marque"),
                "position": pos,
                "hors_echelle": pos is None,
            }
        )
    enriched.sort(
        key=lambda e: (e["position"] is not None, e["position"] or 0.0),
        reverse=True,
    )
    filled = enriched[:quantite]
    excedent = enriched[quantite:]
    emplacements = list(filled) + [_empty_slot() for _ in range(quantite - len(filled))]
    return {"emplacements": emplacements, "excedent": excedent, "rempli": len(filled)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_objectif.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/garderobe/objectif.py backend/tests/test_garderobe/test_objectif.py
git commit -m "feat(garderobe): fonctions pures objectif (échelle Q/P→Max, remplissage emplacements)"
```

---

## Task 2: Modèle ObjectifType + colonne type_objectif + migration

**Files:**
- Modify: `backend/app/models/garderobe.py`
- Modify: `backend/app/models/__init__.py:31` (ligne d'import garderobe)
- Create: `backend/alembic/versions/20260630_1200_v610_objectif_garderobe.py`
- Test: `backend/tests/test_garderobe/test_objectif_import.py` (créé ici, étoffé en Task 3)

**Interfaces:**
- Consumes: rien.
- Produces:
  - `ObjectifType(nom: str [pk], ordre: int, quantite_objectif: int, echelle: list)`.
  - `Vetement.type_objectif: Optional[str]` (nullable).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_objectif_import.py
"""Modèle ObjectifType + colonne Vetement.type_objectif."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 — enregistre toutes les tables
from app.models.garderobe import ObjectifType, Vetement


def _mem_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_objectif_type_roundtrip():
    with _mem_session() as s:
        s.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=15,
                            echelle=["Uniqlo U", "Visvim"]))
        s.commit()
        got = s.get(ObjectifType, "T-shirts")
        assert got is not None
        assert got.quantite_objectif == 15
        assert got.echelle == ["Uniqlo U", "Visvim"]


def test_vetement_has_type_objectif():
    with _mem_session() as s:
        s.add(Vetement(id="v1", nom="Tee", categorie="Haut", type_objectif="T-shirts"))
        s.commit()
        assert s.get(Vetement, "v1").type_objectif == "T-shirts"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_objectif_import.py -v`
Expected: FAIL with `ImportError: cannot import name 'ObjectifType'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/models/garderobe.py`, add the `type_objectif` field to `Vetement` (after `couleur`):

```python
    couleur: Optional[str] = None
    type_objectif: Optional[str] = None  # relie la pièce à un ObjectifType.nom
```

And append the new table at the end of the file:

```python
class ObjectifType(SQLModel, table=True):
    """Cache de l'objectif garde-robe (master = data/imports/Vetements.xlsx).

    Écrasé à chaque POST /garderobe/objectif/sync.
    """

    __tablename__ = "objectif_type"

    nom: str = Field(primary_key=True)
    ordre: int = 0
    quantite_objectif: int = 0
    echelle: list = Field(default_factory=list, sa_column=Column(JSON))
```

In `backend/app/models/__init__.py`, update the garderobe import line:

```python
from app.models.garderobe import ObjectifType, TenueHistory, Vetement  # noqa: F401
```

Create the migration `backend/alembic/versions/20260630_1200_v610_objectif_garderobe.py`:

```python
"""objectif_type + vetement.type_objectif (#garderobe-objectif)

Revision ID: v610objectifgarderobe
Revises: m601musicquality
Create Date: 2026-06-30 12:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "v610objectifgarderobe"
down_revision = "m601musicquality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "objectif_type",
        sa.Column("nom", sa.String(), primary_key=True),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantite_objectif", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("echelle", sa.JSON(), nullable=True),
    )
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.add_column(sa.Column("type_objectif", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.drop_column("type_objectif")
    op.drop_table("objectif_type")
```

- [ ] **Step 4: Run test + migration check**

Run: `uv run pytest tests/test_garderobe/test_objectif_import.py -v`
Expected: PASS (2 passed)

Run: `uv run alembic upgrade head`
Expected: applies `v610objectifgarderobe` with no error (head advances).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/garderobe.py backend/app/models/__init__.py backend/alembic/versions/20260630_1200_v610_objectif_garderobe.py backend/tests/test_garderobe/test_objectif_import.py
git commit -m "feat(garderobe): table objectif_type + colonne vetement.type_objectif + migration"
```

---

## Task 3: Parser Excel + sync vers le cache

**Files:**
- Create: `backend/app/services/garderobe/objectif_import.py`
- Modify: `backend/tests/test_garderobe/test_objectif_import.py` (ajouts)

**Interfaces:**
- Consumes: `build_echelle` (Task 1), `ObjectifType` (Task 2).
- Produces:
  - `parse_objectif_xlsx(path) -> list[dict]` — chaque dict = `{"nom","ordre","quantite_objectif","echelle"}`.
  - `sync_objectif(session, path) -> int` — efface le cache, insère les lignes parsées, commit, retourne le nombre de types.

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
# Append to backend/tests/test_garderobe/test_objectif_import.py

import openpyxl  # noqa: E402
from app.services.garderobe.objectif_import import parse_objectif_xlsx, sync_objectif  # noqa: E402


def _make_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, "Quantité objectif", "Qualité/Prix", "Qualité 1", "Qualité 2"])
    ws.append(["T-shirts", 2, "Uniqlo U", "Beams Plus", "Visvim"])
    ws.append(["Polos", 1, "Uniqlo", "Uniqlo", None])  # doublon → dédup
    ws.append([None, None, None, None, None])           # ligne vide → ignorée
    wb.save(path)


def test_parse_objectif_xlsx(tmp_path):
    p = tmp_path / "Vetements.xlsx"
    _make_xlsx(p)
    rows = parse_objectif_xlsx(p)
    assert len(rows) == 2
    assert rows[0] == {
        "nom": "T-shirts", "ordre": 0, "quantite_objectif": 2,
        "echelle": ["Uniqlo U", "Beams Plus", "Visvim"],
    }
    assert rows[1]["echelle"] == ["Uniqlo"]  # dédupliqué


def test_sync_objectif_wipes_and_refills(tmp_path):
    p = tmp_path / "Vetements.xlsx"
    _make_xlsx(p)
    with _mem_session() as s:
        s.add(ObjectifType(nom="Obsolète", ordre=0, quantite_objectif=9, echelle=["X"]))
        s.commit()
        n = sync_objectif(s, p)
        assert n == 2
        from sqlmodel import select
        noms = {t.nom for t in s.exec(select(ObjectifType)).all()}
        assert noms == {"T-shirts", "Polos"}  # ancien effacé
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_objectif_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.garderobe.objectif_import'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/garderobe/objectif_import.py
"""Import / sync de l'objectif garde-robe depuis Vetements.xlsx (master)."""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.garderobe import ObjectifType
from app.services.garderobe.objectif import build_echelle


def parse_objectif_xlsx(path: Path) -> list[dict]:
    """Lit la feuille 0 : ligne 0 = en-tête, lignes 1+ = types.

    Colonne A = nom du type, B = quantité objectif, C+ = marches Q/P → Max.
    Les lignes sans nom sont ignorées.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    out: list[dict] = []
    ordre = 0
    for row in rows[1:]:  # saute l'en-tête
        nom = row[0] if row else None
        if not nom or not str(nom).strip():
            continue
        quantite = int(row[1] or 0)
        echelle = build_echelle(list(row[2:]))
        out.append(
            {
                "nom": str(nom).strip(),
                "ordre": ordre,
                "quantite_objectif": quantite,
                "echelle": echelle,
            }
        )
        ordre += 1
    return out


def sync_objectif(session: Session, path: Path) -> int:
    """Écrase la table cache `objectif_type` avec le contenu de l'Excel."""
    rows = parse_objectif_xlsx(path)
    for old in session.exec(select(ObjectifType)).all():
        session.delete(old)
    for r in rows:
        session.add(ObjectifType(**r))
    session.commit()
    return len(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_objectif_import.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/garderobe/objectif_import.py backend/tests/test_garderobe/test_objectif_import.py
git commit -m "feat(garderobe): parser Vetements.xlsx + sync vers table cache objectif_type"
```

---

## Task 4: API — GET /objectif, POST /objectif/sync, PATCH type_objectif

**Files:**
- Create: `backend/app/api/garderobe/objectif.py`
- Modify: `backend/app/api/garderobe/__init__.py:9,14` (import + include)
- Modify: `backend/app/api/garderobe/schemas.py` (schémas + champ `type_objectif`)
- Modify: `backend/app/api/garderobe/common.py:21-39,42-55` (propager `type_objectif`)
- Test: `backend/tests/test_garderobe/test_objectif_api.py`

**Interfaces:**
- Consumes: `fill_slots` (Task 1), `ObjectifType`/`Vetement` (Task 2), `sync_objectif` (Task 3).
- Produces (response shapes):
  - `GET /garderobe/objectif` → `ObjectifResponse{ total_emplacements:int, total_remplis:int, types: ObjectifTypeOut[] }`.
  - `ObjectifTypeOut{ nom, ordre, quantite_objectif, echelle:str[], rempli:int, emplacements: Emplacement[], excedent: Emplacement[] }`.
  - `Emplacement{ statut:str, vetement_id:str|None, vetement_nom:str|None, marque:str|None, position:float|None, hors_echelle:bool }`.
  - `POST /garderobe/objectif/sync` → `{ "types": int }`.
  - `PATCH /garderobe/vetements/{id}` accepte désormais `{"type_objectif": str|null}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_objectif_api.py
"""API onglet Objectif (#garderobe-objectif)."""
from __future__ import annotations

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.api.garderobe import objectif as objectif_mod
from app.core.db import get_session
from app.main import create_app
from app.models.garderobe import ObjectifType, Vetement


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_get_objectif_positions_and_empty(client, session):
    session.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=2,
                             echelle=["Uniqlo U", "Beams Plus", "Visvim"]))
    session.add(Vetement(id="v1", nom="Tee", categorie="Haut",
                         marque="Visvim", type_objectif="T-shirts"))
    session.commit()

    r = client.get("/garderobe/objectif")
    assert r.status_code == 200
    data = r.json()
    assert data["total_emplacements"] == 2
    assert data["total_remplis"] == 1
    t = data["types"][0]
    assert t["nom"] == "T-shirts"
    assert t["emplacements"][0]["position"] == 100.0
    assert t["emplacements"][1]["statut"] == "vide"


def test_get_objectif_excess_red(client, session):
    session.add(ObjectifType(nom="Polos", ordre=0, quantite_objectif=1,
                             echelle=["Uniqlo", "Auralee"]))
    session.add(Vetement(id="p1", nom="Polo A", categorie="Haut",
                         marque="Auralee", type_objectif="Polos"))
    session.add(Vetement(id="p2", nom="Polo B", categorie="Haut",
                         marque="Uniqlo", type_objectif="Polos"))
    session.commit()

    t = client.get("/garderobe/objectif").json()["types"][0]
    assert len(t["emplacements"]) == 1
    assert len(t["excedent"]) == 1


def test_patch_vetement_type_objectif(client, session):
    session.add(Vetement(id="v9", nom="Tee", categorie="Haut"))
    session.commit()
    r = client.patch("/garderobe/vetements/v9", json={"type_objectif": "T-shirts"})
    assert r.status_code == 200
    assert r.json()["type_objectif"] == "T-shirts"


def test_post_sync(client, session, tmp_path, monkeypatch):
    p = tmp_path / "Vetements.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([None, "Quantité objectif", "Qualité/Prix"])
    ws.append(["T-shirts", 3, "Uniqlo U"])
    wb.save(p)
    monkeypatch.setattr(objectif_mod, "_objectif_xlsx_path", lambda: p)

    r = client.post("/garderobe/objectif/sync")
    assert r.status_code == 200
    assert r.json() == {"types": 1}
    assert session.get(ObjectifType, "T-shirts").quantite_objectif == 3


def test_post_sync_missing_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(objectif_mod, "_objectif_xlsx_path", lambda: tmp_path / "absent.xlsx")
    r = client.post("/garderobe/objectif/sync")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_objectif_api.py -v`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` for `app.api.garderobe.objectif`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/garderobe/schemas.py`, add `type_objectif` to the three Vetement schemas:
- `VetementBase` (after `couleur`): `type_objectif: Optional[str] = None`
- `VetementUpdate` (after `couleur`): `type_objectif: Optional[str] = None`

(`VetementRead`/`VetementCreate` inherit from `VetementBase`, so they get it automatically.)

Then append the Objectif schemas at the end of `schemas.py`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Objectif garde-robe
# ─────────────────────────────────────────────────────────────────────────────

class Emplacement(BaseModel):
    statut: str  # "rempli" | "vide"
    vetement_id: Optional[str] = None
    vetement_nom: Optional[str] = None
    marque: Optional[str] = None
    position: Optional[float] = None  # 0..100, None si vide ou hors échelle
    hors_echelle: bool = False


class ObjectifTypeOut(BaseModel):
    nom: str
    ordre: int
    quantite_objectif: int
    echelle: list[str]
    rempli: int
    emplacements: list[Emplacement]
    excedent: list[Emplacement]


class ObjectifResponse(BaseModel):
    total_emplacements: int
    total_remplis: int
    types: list[ObjectifTypeOut]
```

In `backend/app/api/garderobe/common.py`, add `type_objectif` to the dict in `vetement_to_dict` (after `"couleur": v.couleur,`):

```python
        "couleur": v.couleur,
        "type_objectif": v.type_objectif,
```

(`vetement_to_read` spreads `**d`, so it propagates automatically.)

Create `backend/app/api/garderobe/objectif.py`:

```python
"""Sous-routeur Garde-robe : onglet « Objectif » (#garderobe-objectif).

Master = data/imports/Vetements.xlsx. POST /objectif/sync l'importe dans la table
cache `objectif_type` ; GET /objectif la croise avec les vêtements possédés.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.garderobe.schemas import Emplacement, ObjectifResponse, ObjectifTypeOut
from app.core.config import settings
from app.core.db import get_session
from app.models.garderobe import ObjectifType, Vetement
from app.services.garderobe.objectif import fill_slots
from app.services.garderobe.objectif_import import sync_objectif

router = APIRouter()


def _objectif_xlsx_path() -> Path:
    return settings.imports_dir / "Vetements.xlsx"


@router.get("/objectif", response_model=ObjectifResponse)
def get_objectif(session: Session = Depends(get_session)) -> ObjectifResponse:
    types = session.exec(select(ObjectifType).order_by(ObjectifType.ordre)).all()
    vets = session.exec(
        select(Vetement).where(Vetement.type_objectif.is_not(None))
    ).all()

    owned_by_type: dict[str, list[dict]] = {}
    for v in vets:
        owned_by_type.setdefault(v.type_objectif, []).append(
            {"id": v.id, "nom": v.nom, "marque": v.marque}
        )

    out_types: list[ObjectifTypeOut] = []
    total_emp = 0
    total_remplis = 0
    for t in types:
        res = fill_slots(t.echelle or [], t.quantite_objectif, owned_by_type.get(t.nom, []))
        total_emp += t.quantite_objectif
        total_remplis += res["rempli"]
        out_types.append(
            ObjectifTypeOut(
                nom=t.nom,
                ordre=t.ordre,
                quantite_objectif=t.quantite_objectif,
                echelle=t.echelle or [],
                rempli=res["rempli"],
                emplacements=[Emplacement(**e) for e in res["emplacements"]],
                excedent=[Emplacement(**e) for e in res["excedent"]],
            )
        )

    return ObjectifResponse(
        total_emplacements=total_emp,
        total_remplis=total_remplis,
        types=out_types,
    )


@router.post("/objectif/sync")
def post_objectif_sync(session: Session = Depends(get_session)) -> dict:
    path = _objectif_xlsx_path()
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Fichier introuvable : {path}")
    n = sync_objectif(session, path)
    return {"types": n}
```

Wire it in `backend/app/api/garderobe/__init__.py`:

```python
from . import insights, objectif, planner, tenues, vetements

router = APIRouter(tags=["garderobe"])
router.include_router(vetements.router)
router.include_router(tenues.router)
router.include_router(insights.router)
router.include_router(planner.router)
router.include_router(objectif.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_objectif_api.py -v`
Expected: PASS (5 passed)

Run (regression): `uv run pytest tests/test_garderobe -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/garderobe/objectif.py backend/app/api/garderobe/__init__.py backend/app/api/garderobe/schemas.py backend/app/api/garderobe/common.py backend/tests/test_garderobe/test_objectif_api.py
git commit -m "feat(garderobe): API GET /objectif + POST /objectif/sync + PATCH type_objectif"
```

---

## Task 5: Frontend — types, client API, hooks

**Files:**
- Modify: `frontend/lib/garderobe.ts` (types + champ + méthodes)
- Modify: `frontend/lib/queries/garderobe.ts` (hooks)
- Modify: `frontend/__tests__/queries/garderobe.test.tsx` (mock + test)

**Interfaces:**
- Consumes: API de Task 4.
- Produces:
  - Types `Emplacement`, `ObjectifTypeOut`, `ObjectifResponse` ; champ `type_objectif: string | null` sur `Vetement`.
  - `garderobeApi.getObjectif(): Promise<ObjectifResponse>` ; `garderobeApi.syncObjectif(): Promise<{ types: number }>`.
  - Hooks `useObjectif()`, `useSyncObjectif()` ; clé `garderobeKeys.objectif()`.

- [ ] **Step 1: Write the failing test (extend existing query test)**

In `frontend/__tests__/queries/garderobe.test.tsx`, add to the `garderobeApi` mock object:

```typescript
    getObjectif: vi.fn().mockResolvedValue({
      total_emplacements: 2,
      total_remplis: 1,
      types: [{ nom: "T-shirts", ordre: 0, quantite_objectif: 2, echelle: [], rempli: 1, emplacements: [], excedent: [] }],
    }),
    syncObjectif: vi.fn().mockResolvedValue({ types: 55 }),
```

Update the import line to include `useObjectif`:

```typescript
import { garderobeKeys, useObjectif, useVetements, useValiderTenue } from "@/lib/queries/garderobe";
```

Add a test inside the `describe`:

```typescript
  it("useObjectif charge l'objectif", async () => {
    const { result } = renderHook(() => useObjectif(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total_emplacements).toBe(2);
    expect(garderobeKeys.objectif()).toEqual(["garderobe", "objectif"]);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/queries/garderobe.test.tsx`
Expected: FAIL — `useObjectif` is not exported / `garderobeKeys.objectif` is undefined.

- [ ] **Step 3: Write minimal implementation**

In `frontend/lib/garderobe.ts`, add `type_objectif` to the `Vetement` type (after `couleur`):

```typescript
  couleur: string | null;
  type_objectif: string | null;
```

Add the Objectif types (near the other type exports, e.g. before `// Endpoints`):

```typescript
export type Emplacement = {
  statut: "rempli" | "vide";
  vetement_id: string | null;
  vetement_nom: string | null;
  marque: string | null;
  position: number | null; // 0..100, null si vide ou hors échelle
  hors_echelle: boolean;
};

export type ObjectifTypeOut = {
  nom: string;
  ordre: number;
  quantite_objectif: number;
  echelle: string[];
  rempli: number;
  emplacements: Emplacement[];
  excedent: Emplacement[];
};

export type ObjectifResponse = {
  total_emplacements: number;
  total_remplis: number;
  types: ObjectifTypeOut[];
};
```

Add the two methods inside the `garderobeApi` object (e.g. after `recommendations`):

```typescript
  getObjectif: () => api<ObjectifResponse>(`/garderobe/objectif`),

  syncObjectif: () =>
    api<{ types: number }>(`/garderobe/objectif/sync`, { method: "POST" }),
```

In `frontend/lib/queries/garderobe.ts`, add the cache key (inside `garderobeKeys`):

```typescript
  objectif: () => [...garderobeKeys.all, "objectif"] as const,
```

Add the hooks (e.g. after `useGarderobeRecommendations`):

```typescript
export function useObjectif() {
  return useQuery({ queryKey: garderobeKeys.objectif(), queryFn: garderobeApi.getObjectif });
}
export function useSyncObjectif() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: garderobeApi.syncObjectif, onSuccess: invalidate });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/queries/garderobe.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/garderobe.ts frontend/lib/queries/garderobe.ts frontend/__tests__/queries/garderobe.test.tsx
git commit -m "feat(garderobe): client API + hooks objectif (front)"
```

---

## Task 6: Frontend — onglet Objectif + barre 0→100

**Files:**
- Create: `frontend/components/garderobe/ObjectifBar.tsx`
- Create: `frontend/components/garderobe/ObjectifTab.tsx`
- Modify: `frontend/components/garderobe/Garderobe.tsx:4,30,32-38,57-75,257-266` (tab type, TABS, hook, rendu)

**Interfaces:**
- Consumes: `useObjectif`, `useSyncObjectif` (Task 5), types `ObjectifResponse`/`Emplacement`.
- Produces: composant `ObjectifTab`, branché comme onglet `"objectif"`.

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/components/objectif-tab.test.tsx`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/queries/garderobe", () => ({
  useObjectif: () => ({
    isLoading: false,
    isError: false,
    data: {
      total_emplacements: 2,
      total_remplis: 1,
      types: [
        {
          nom: "T-shirts",
          ordre: 0,
          quantite_objectif: 2,
          echelle: ["Uniqlo U", "Visvim"],
          rempli: 1,
          emplacements: [
            { statut: "rempli", vetement_id: "v1", vetement_nom: "Tee", marque: "Visvim", position: 100, hors_echelle: false },
            { statut: "vide", vetement_id: null, vetement_nom: null, marque: null, position: null, hors_echelle: false },
          ],
          excedent: [],
        },
      ],
    },
  }),
  useSyncObjectif: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { ObjectifTab } from "@/components/garderobe/ObjectifTab";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("ObjectifTab", () => {
  it("affiche l'en-tête global et un type", () => {
    render(<ObjectifTab />, { wrapper });
    expect(screen.getByText(/1\/2/)).toBeInTheDocument();      // total rempli/emplacements
    expect(screen.getByText("T-shirts")).toBeInTheDocument();
    expect(screen.getByText("Visvim")).toBeInTheDocument();    // marque possédée
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx`
Expected: FAIL — `@/components/garderobe/ObjectifTab` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/components/garderobe/ObjectifBar.tsx`:

```tsx
"use client";

import { type Emplacement } from "@/lib/garderobe";

/** Une ligne d'emplacement : nom de marque + barre 0→100 (Q/P → Qualité Max). */
export function ObjectifBar({ slot, excedent = false }: { slot: Emplacement; excedent?: boolean }) {
  const empty = slot.statut === "vide";
  const pos = slot.position ?? 0;

  let barClass = "bg-[var(--primary)]";
  if (excedent) barClass = "bg-[var(--destructive)]";
  else if (empty) barClass = "bg-transparent";
  else if (slot.hors_echelle) barClass = "bg-[var(--muted-foreground)]"; // marque hors échelle = gris

  return (
    <div className={`flex items-center gap-3 ${excedent ? "text-[var(--destructive)]" : ""}`}>
      <span className="w-32 shrink-0 truncate text-sm">
        {empty ? <span className="text-[var(--muted-foreground)]">—</span> : slot.marque ?? "?"}
      </span>
      <div className="relative h-2 flex-1 rounded-full bg-[var(--muted)]">
        {!empty && (
          <div
            className={`absolute top-0 left-0 h-2 rounded-full ${barClass}`}
            style={{ width: `${Math.max(pos, 2)}%` }}
          />
        )}
      </div>
    </div>
  );
}
```

Create `frontend/components/garderobe/ObjectifTab.tsx`:

```tsx
"use client";

import { RefreshCw } from "lucide-react";
import { useObjectif, useSyncObjectif } from "@/lib/queries/garderobe";
import { ObjectifBar } from "./ObjectifBar";

export function ObjectifTab() {
  const objectifQ = useObjectif();
  const syncMut = useSyncObjectif();

  if (objectifQ.isLoading) {
    return <div className="p-2 text-[var(--muted-foreground)]">Chargement de l'objectif…</div>;
  }
  if (objectifQ.isError || !objectifQ.data) {
    return <div className="p-2 text-[var(--destructive)]">⚠ Impossible de charger l'objectif.</div>;
  }

  const { total_emplacements, total_remplis, types } = objectifQ.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="text-sm text-[var(--muted-foreground)]">
          <span className="font-semibold text-[var(--foreground)]">
            {total_remplis}/{total_emplacements}
          </span>{" "}
          emplacements remplis
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending}
          className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
          Re-synchroniser l'Excel
        </button>
      </div>

      {types.map((t) => (
        <div key={t.nom} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="font-semibold">{t.nom}</h3>
            <span className="text-xs text-[var(--muted-foreground)]">
              {t.rempli}/{t.quantite_objectif}
            </span>
          </div>
          <div className="space-y-2">
            {t.emplacements.map((slot, i) => (
              <ObjectifBar key={`${t.nom}-${i}`} slot={slot} />
            ))}
            {t.excedent.map((slot, i) => (
              <ObjectifBar key={`${t.nom}-x${i}`} slot={slot} excedent />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

Wire into `frontend/components/garderobe/Garderobe.tsx`:

- Add the icon to the imports on line 4:
```tsx
import { Shirt, Sparkles, PieChart, Clock, CalendarDays, Target } from "lucide-react";
```
- Add `ObjectifTab` import alongside the other tab imports (after line 28):
```tsx
import { ObjectifTab } from "./ObjectifTab";
```
- Extend the `Tab` type (line 30):
```tsx
type Tab = "tenue" | "inventaire" | "stats" | "history" | "recs" | "semaine" | "objectif";
```
- Add the tab entry to `TABS` (after the `inventaire` entry, line 33):
```tsx
  { id: "inventaire", label: "Inventaire", Icon: Shirt },
  { id: "objectif", label: "Objectif", Icon: Target },
```
- Add the render branch (after the `inventaire` block, around line 262):
```tsx
        {tab === "objectif" && <ObjectifTab />}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx __tests__/queries/garderobe.test.tsx`
Expected: PASS.

Run (typecheck/build sanity): `npx tsc --noEmit`
Expected: no errors in the touched files.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/garderobe/ObjectifBar.tsx frontend/components/garderobe/ObjectifTab.tsx frontend/components/garderobe/Garderobe.tsx frontend/__tests__/components/objectif-tab.test.tsx
git commit -m "feat(garderobe): onglet Objectif (barre 0→100, emplacements vides/excédent, re-sync Excel)"
```

---

## Task 7: Sync initial + vérification de bout en bout

**Files:** aucun fichier source (étape opérationnelle + vérif).

**Interfaces:** consomme tout l'existant.

- [ ] **Step 1: Lancer la migration sur la vraie base**

Run (depuis `backend/`): `uv run alembic upgrade head`
Expected: `v610objectifgarderobe` appliquée.

- [ ] **Step 2: Démarrer le backend et synchroniser l'Excel**

Run: démarrer l'API (script projet habituel), puis :
```bash
curl -s -X POST http://127.0.0.1:8000/garderobe/objectif/sync
```
Expected: `{"types":55}`

- [ ] **Step 3: Vérifier le GET**

```bash
curl -s http://127.0.0.1:8000/garderobe/objectif | python -c "import sys,json; d=json.load(sys.stdin); print(d['total_emplacements'], len(d['types']))"
```
Expected: `251 55`

- [ ] **Step 4: Suite de tests complète**

Run (backend): `uv run pytest tests/test_garderobe -q`
Run (frontend): `npx vitest run`
Expected: tout vert.

- [ ] **Step 5: Commit (le cas échéant)**

Rien à committer si seules des données runtime ont changé. Sinon :
```bash
git commit --allow-empty -m "chore(garderobe): vérification end-to-end onglet Objectif (sync 55 types / 251 emplacements)"
```

---

## Self-Review

**1. Spec coverage**
- Onglet « Objectif » avec barre 0→100 par élément → Task 1 (`brand_position`/`fill_slots`) + Task 6 (`ObjectifBar`). ✓
- 251 emplacements, 55 types → Task 3 (parser) + Task 4 (`total_emplacements`) + Task 7 (vérif `251 55`). ✓
- Emplacement vide si rien → `_empty_slot` (Task 1), rendu `—` (Task 6). ✓
- Rouge quand élément en trop → `excedent` (Task 1/4), `excedent` prop (Task 6). ✓
- Marque possédée non présente dans l'échelle → ajoutée à l'échelle dans l'Excel (master) ; en attendant, barre grise (`hors_echelle`, Task 1/6). ✓
- Lien pièce ↔ type via champ explicite → `Vetement.type_objectif` + PATCH (Task 2/4). ✓
- Excel = master, sync vers cache → Task 3 (`sync_objectif`) + Task 4 (`POST /objectif/sync`) + bouton re-sync (Task 6). ✓
- Logos / conseils d'achat / BonneGueule → hors scope (déclaré dans Global Constraints). ✓

**2. Placeholder scan** : aucun TODO/«handle edge cases»/«similar to» ; chaque step de code contient le code complet. ✓

**3. Type consistency** : `fill_slots` retourne `{emplacements, excedent, rempli}` (Task 1) — consommé tel quel dans Task 4. `Emplacement`/`ObjectifTypeOut`/`ObjectifResponse` identiques entre schemas backend (Task 4), types frontend (Task 5) et mocks de test (Task 5/6). `type_objectif` ajouté de façon cohérente : modèle (Task 2), schémas + common (Task 4), type front (Task 5). `garderobeKeys.objectif()` et `useObjectif`/`useSyncObjectif` définis Task 5, consommés Task 6. ✓
