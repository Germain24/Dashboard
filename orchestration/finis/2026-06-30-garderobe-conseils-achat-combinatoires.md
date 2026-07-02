# Conseils d'achat combinatoires — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer l'onglet Recommandations (heuristiques) par un modèle combinatoire qui classe les achats (slot × couleur) par nombre de tenues débloquées.

**Architecture:** Des fonctions pures (`count_outfits`, `purchase_advice`) énumèrent les triplets (Haut, Pantalon, Chaussures) couleur-compatibles et calculent le gain marginal de chaque achat candidat. `GET /garderobe/recommendations` est repointé vers ce modèle ; l'ancien `get_purchase_recommendations` est supprimé. Le frontend réécrit l'onglet.

**Tech Stack:** FastAPI + SQLModel ; Next.js + TanStack Query ; pytest, Vitest.

## Global Constraints

- Backend via `uv run` depuis `backend/` ; frontend via `npx vitest run`/`npx tsc --noEmit` depuis `frontend/`.
- Tenue = triplet **(Haut, Pantalon, Chaussures)** (slots ALWAYS) dont les couleurs sont **2-à-2** `colors_compat`. Décompte sur les **pièces réelles**.
- Candidats : 3 slots de base × `PALETTE` (= `NEUTRES + SECONDAIRES + ACCENTS` de `constants.py`).
- `GET /garderobe/recommendations` → `{ total_tenues: int, conseils: [{slot, couleur, debloque, total_apres}] }`.
- Suppression de l'ancien modèle : `recommendations.py`, `test_recommendations.py`, l'export `get_purchase_recommendations` (`__init__.py`), `RecommendationOut` (schemas).
- `vue-360` utilise un AUTRE `useRecommendations` (routines) — NE PAS toucher.
- UI en français. Pas de nouvelle dépendance.
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`/`.`).

---

## Task 1: Fonctions pures combinatoires

**Files:**
- Create: `backend/app/services/garderobe/purchase_combos.py`
- Test: `backend/tests/test_garderobe/test_purchase_combos.py`

**Interfaces:**
- Consumes: `SLOTS`, `NEUTRES`, `SECONDAIRES`, `ACCENTS` (constants), `colors_compat` (style).
- Produces:
  - `base_slot_of(item: dict) -> str | None`
  - `count_outfits(wardrobe: list[dict]) -> int`
  - `purchase_advice(wardrobe: list[dict], top: int = 5) -> list[dict]` (dicts `{"slot","couleur","debloque","total_apres"}`)
  - `PALETTE: list[str]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_purchase_combos.py
"""Conseils d'achat combinatoires (tenues débloquées)."""
from __future__ import annotations

from app.services.garderobe.purchase_combos import (
    base_slot_of,
    count_outfits,
    purchase_advice,
)


def test_base_slot_of():
    assert base_slot_of({"categorie": "Haut"}) == "Haut"
    assert base_slot_of({"categorie": "T-shirt"}) == "Haut"
    assert base_slot_of({"categorie": "Pantalon"}) == "Pantalon"
    assert base_slot_of({"categorie": "Jean"}) == "Pantalon"
    assert base_slot_of({"categorie": "Chaussures"}) == "Chaussures"
    assert base_slot_of({"categorie": "Montre"}) is None
    assert base_slot_of({"categorie": None}) is None


def test_count_outfits_compte_triplets_compatibles():
    wardrobe = [
        {"categorie": "Haut", "couleur": "Noir"},
        {"categorie": "Pantalon", "couleur": "Noir"},
        {"categorie": "Chaussures", "couleur": "Noir"},
    ]
    assert count_outfits(wardrobe) == 1
    # un 2e haut neutre ajoute un triplet
    wardrobe.append({"categorie": "Haut", "couleur": "Blanc"})
    assert count_outfits(wardrobe) == 2


def test_count_outfits_exclut_incompatibles():
    # Or (accent) vs Marron (secondaire) ne sont pas compatibles
    wardrobe = [
        {"categorie": "Haut", "couleur": "Or"},
        {"categorie": "Pantalon", "couleur": "Marron"},
        {"categorie": "Chaussures", "couleur": "Noir"},
    ]
    assert count_outfits(wardrobe) == 0


def test_purchase_advice_recommande_le_slot_manquant():
    # Haut + Pantalon mais pas de chaussures -> 0 tenue ; le meilleur achat = Chaussures
    wardrobe = [
        {"categorie": "Haut", "couleur": "Noir"},
        {"categorie": "Pantalon", "couleur": "Noir"},
    ]
    advice = purchase_advice(wardrobe, top=5)
    assert advice, "des conseils sont attendus"
    assert advice[0]["slot"] == "Chaussures"
    assert advice[0]["debloque"] >= 1
    assert advice[0]["total_apres"] == advice[0]["debloque"]  # base 0
    # aucun conseil Haut/Pantalon (ils ne débloquent rien sans chaussures)
    assert all(c["slot"] == "Chaussures" for c in advice)


def test_purchase_advice_exclut_gains_nuls_et_trie():
    # Pantalon Noir + Chaussures Marron : ajouter un Haut Or ne débloque rien
    # (Or incompatible avec Marron), un Haut neutre débloque 1.
    wardrobe = [
        {"categorie": "Pantalon", "couleur": "Noir"},
        {"categorie": "Chaussures", "couleur": "Marron"},
    ]
    advice = purchase_advice(wardrobe, top=10)
    assert advice[0]["slot"] == "Haut"
    assert advice[0]["debloque"] == 1
    # tri décroissant
    gains = [c["debloque"] for c in advice]
    assert gains == sorted(gains, reverse=True)
    # aucun gain nul, et "Or" (incompatible) absent des conseils Haut
    assert all(c["debloque"] > 0 for c in advice)
    assert not any(c["couleur"] == "Or" for c in advice)
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `uv run pytest tests/test_garderobe/test_purchase_combos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.garderobe.purchase_combos'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/garderobe/purchase_combos.py
"""Conseils d'achat combinatoires : quel achat (slot × couleur) débloque le plus de tenues.

Une tenue = triplet (Haut, Pantalon, Chaussures) dont les couleurs sont 2-à-2
compatibles (`colors_compat`). On évalue chaque achat candidat par son gain
marginal de tenues.
"""
from __future__ import annotations

from typing import Any

from app.services.garderobe.constants import ACCENTS, NEUTRES, SECONDAIRES, SLOTS
from app.services.garderobe.style import colors_compat

_BASE_SLOTS = ["Haut", "Pantalon", "Chaussures"]
PALETTE: list[str] = list(NEUTRES) + list(SECONDAIRES) + list(ACCENTS)

# categorie -> slot de base (depuis les slots ALWAYS de SLOTS)
_CAT_TO_SLOT: dict[str, str] = {}
for _s in SLOTS:
    if _s["id"] in _BASE_SLOTS:
        for _c in _s["categories"]:
            _CAT_TO_SLOT[_c] = _s["id"]


def base_slot_of(item: dict[str, Any]) -> str | None:
    return _CAT_TO_SLOT.get(item.get("categorie"))


def count_outfits(wardrobe: list[dict[str, Any]]) -> int:
    by_slot: dict[str, list[dict[str, Any]]] = {sid: [] for sid in _BASE_SLOTS}
    for it in wardrobe:
        sid = base_slot_of(it)
        if sid:
            by_slot[sid].append(it)
    n = 0
    for h in by_slot["Haut"]:
        for p in by_slot["Pantalon"]:
            if not colors_compat(h.get("couleur"), p.get("couleur")):
                continue
            for c in by_slot["Chaussures"]:
                if colors_compat(h.get("couleur"), c.get("couleur")) and colors_compat(
                    p.get("couleur"), c.get("couleur")
                ):
                    n += 1
    return n


def purchase_advice(wardrobe: list[dict[str, Any]], top: int = 5) -> list[dict[str, Any]]:
    base = count_outfits(wardrobe)
    out: list[dict[str, Any]] = []
    for slot in _BASE_SLOTS:
        for couleur in PALETTE:
            gain = count_outfits(wardrobe + [{"categorie": slot, "couleur": couleur}]) - base
            if gain > 0:
                out.append(
                    {"slot": slot, "couleur": couleur, "debloque": gain, "total_apres": base + gain}
                )
    out.sort(key=lambda c: (-c["debloque"], _BASE_SLOTS.index(c["slot"]), PALETTE.index(c["couleur"])))
    return out[:top]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_purchase_combos.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/garderobe/purchase_combos.py backend/tests/test_garderobe/test_purchase_combos.py
git commit -m "feat(garderobe): fonctions pures de conseils d'achat combinatoires (tenues débloquées)"
```

---

## Task 2: API repointée + suppression de l'ancien modèle

**Files:**
- Modify: `backend/app/api/garderobe/insights.py` (imports + route `/recommendations`)
- Modify: `backend/app/api/garderobe/schemas.py:201-206` (remplace `RecommendationOut`)
- Modify: `backend/app/services/garderobe/__init__.py:19,46` (retire import + export)
- Delete: `backend/app/services/garderobe/recommendations.py`
- Delete: `backend/tests/test_garderobe/test_recommendations.py`
- Test: `backend/tests/test_garderobe/test_conseils_achat_api.py` (créer)

**Interfaces:**
- Consumes: `count_outfits`, `purchase_advice` (Task 1).
- Produces: `GET /garderobe/recommendations` → `ConseilsAchatResponse{ total_tenues:int, conseils: ConseilAchat[] }` ; `ConseilAchat{slot,couleur,debloque,total_apres}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_conseils_achat_api.py
"""API conseils d'achat combinatoires (GET /garderobe/recommendations)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.core.db import get_session
from app.main import create_app
from app.models.garderobe import Vetement


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


def test_recommendations_combinatoire(client, session):
    session.add(Vetement(id="h", nom="Haut", categorie="Haut", couleur="Noir"))
    session.add(Vetement(id="p", nom="Pant", categorie="Pantalon", couleur="Noir"))
    session.commit()

    r = client.get("/garderobe/recommendations")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"total_tenues", "conseils"}
    assert data["total_tenues"] == 0  # pas de chaussures -> aucune tenue
    assert data["conseils"][0]["slot"] == "Chaussures"
    assert data["conseils"][0]["debloque"] >= 1
    assert set(data["conseils"][0].keys()) == {"slot", "couleur", "debloque", "total_apres"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_conseils_achat_api.py -v`
Expected: FAIL — la réponse a encore l'ancienne forme (liste de `{nom,raison,potentiel,type}`), `data` n'a pas `total_tenues`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/garderobe/schemas.py`, replace the `RecommendationOut` class (lines 201-206) with:

```python
class ConseilAchat(BaseModel):
    slot: str
    couleur: str
    debloque: int
    total_apres: int


class ConseilsAchatResponse(BaseModel):
    total_tenues: int
    conseils: list[ConseilAchat]
```

In `backend/app/services/garderobe/__init__.py`:
- delete line 19: `from app.services.garderobe.recommendations import get_purchase_recommendations`
- delete the `"get_purchase_recommendations",` entry from `__all__` (line 46).

Delete the two files:

```bash
git rm backend/app/services/garderobe/recommendations.py backend/tests/test_garderobe/test_recommendations.py
```

In `backend/app/api/garderobe/insights.py`:
- Update the schemas import to drop `RecommendationOut` and add the new names:

```python
from app.api.garderobe.schemas import (
    ConseilAchat,
    ConseilsAchatResponse,
    CountEntry,
    StatsResponse,
    TenueHistoryOut,
    VetementRead,
)
```

- Update the services import to drop `get_purchase_recommendations`:

```python
from app.services.garderobe import is_worn_out, needs_wash
from app.services.garderobe.frequency import wear_buckets
from app.services.garderobe.purchase_combos import count_outfits, purchase_advice
from app.services.garderobe.style import get_color_category
```

- Replace the `recommendations` route (the `@router.get("/recommendations" …)` block) with:

```python
@router.get("/recommendations", response_model=ConseilsAchatResponse)
def recommendations(session: Session = Depends(get_session)) -> ConseilsAchatResponse:
    items = [vetement_to_dict(v) for v in session.exec(select(Vetement)).all()]
    return ConseilsAchatResponse(
        total_tenues=count_outfits(items),
        conseils=[ConseilAchat(**c) for c in purchase_advice(items)],
    )
```

- [ ] **Step 4: Run test + regression**

Run: `uv run pytest tests/test_garderobe/test_conseils_achat_api.py -v`
Expected: PASS.

Run: `uv run pytest tests/test_garderobe -q`
Expected: all green (et plus aucune référence à `test_recommendations.py`, supprimé).

Run (garde-fou import) : `uv run python -c "import app.api.garderobe.insights, app.services.garderobe"`
Expected: no error (l'export retiré ne casse aucun import).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/garderobe/insights.py backend/app/api/garderobe/schemas.py backend/app/services/garderobe/__init__.py backend/app/services/garderobe/recommendations.py backend/tests/test_garderobe/test_recommendations.py backend/tests/test_garderobe/test_conseils_achat_api.py
git commit -m "feat(garderobe): /recommendations renvoie les conseils combinatoires (retrait des heuristiques)"
```

(Le `git rm` a déjà mis en scène les suppressions ; le `git add` des deux chemins supprimés confirme leur retrait dans le commit.)

---

## Task 3: Frontend — types + onglet réécrit

**Files:**
- Modify: `frontend/lib/garderobe.ts` (type `Recommendation` → `ConseilAchat`/`ConseilsAchat` + retour de `recommendations()`)
- Modify: `frontend/components/garderobe/Garderobe.tsx:71` (défaut de `recs`)
- Modify: `frontend/components/garderobe/RecommandationsTab.tsx` (réécriture)
- Modify: `frontend/__tests__/queries/garderobe.test.tsx:13` (mock)
- Test: `frontend/__tests__/components/recommandations-tab.test.tsx` (créer)

**Interfaces:**
- Consumes: endpoint `GET /garderobe/recommendations` (Task 2).
- Produces: types `ConseilAchat`, `ConseilsAchat`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/components/recommandations-tab.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecommandationsTab } from "@/components/garderobe/RecommandationsTab";

describe("RecommandationsTab", () => {
  it("affiche le total et un conseil", () => {
    render(
      <RecommandationsTab
        recs={{ total_tenues: 3, conseils: [{ slot: "Chaussures", couleur: "Noir", debloque: 2, total_apres: 5 }] }}
      />,
    );
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText(/Ajouter Chaussures Noir/)).toBeInTheDocument();
    expect(screen.getByText(/\+2/)).toBeInTheDocument();
  });

  it("invite quand aucun conseil", () => {
    render(<RecommandationsTab recs={{ total_tenues: 0, conseils: [] }} />);
    expect(screen.getByText(/Ajoute d'abord/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/components/recommandations-tab.test.tsx`
Expected: FAIL — `RecommandationsTab` attend encore `Recommendation[]` ; le rendu ne correspond pas.

- [ ] **Step 3: Write minimal implementation**

In `frontend/lib/garderobe.ts`, replace the `Recommendation` type (the `export type Recommendation = { nom; raison; potentiel; type };` block) with:

```ts
export type ConseilAchat = {
  slot: string;
  couleur: string;
  debloque: number;
  total_apres: number;
};

export type ConseilsAchat = {
  total_tenues: number;
  conseils: ConseilAchat[];
};
```

And change the `recommendations` API method return type:

```ts
  recommendations: () => api<ConseilsAchat>(`/garderobe/recommendations`),
```

Rewrite `frontend/components/garderobe/RecommandationsTab.tsx`:

```tsx
"use client";

import type { ConseilsAchat } from "@/lib/garderobe";

export function RecommandationsTab({ recs }: { recs: ConseilsAchat }) {
  const { total_tenues, conseils } = recs;
  const maxGain = conseils.length ? conseils[0].debloque : 1;

  return (
    <div className="space-y-3">
      <div className="text-sm text-[var(--muted-foreground)]">
        Tu as actuellement{" "}
        <span className="font-semibold text-[var(--foreground)]">{total_tenues}</span> tenue
        {total_tenues > 1 ? "s" : ""} possible{total_tenues > 1 ? "s" : ""}.
      </div>

      {conseils.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Ajoute d'abord des hauts, pantalons et chaussures pour débloquer des tenues.
        </p>
      ) : (
        conseils.map((c, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center gap-2 mb-1">
              <div className="text-sm font-semibold">
                Ajouter {c.slot} {c.couleur}
              </div>
              <span className="ml-auto text-xs font-mono text-[var(--success,#16a34a)]">
                +{c.debloque} tenue{c.debloque > 1 ? "s" : ""}
              </span>
            </div>
            <div className="mt-2 h-1.5 bg-[var(--muted)] rounded overflow-hidden">
              <div
                className="h-full bg-[var(--ring)]"
                style={{ width: `${(c.debloque / maxGain) * 100}%` }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  );
}
```

In `frontend/components/garderobe/Garderobe.tsx`, change the `recs` default (line 71) from `const recs = recsQ.data ?? [];` to:

```tsx
  const recs = recsQ.data ?? { total_tenues: 0, conseils: [] };
```

In `frontend/__tests__/queries/garderobe.test.tsx`, change the `recommendations` mock (line 13) from `recommendations: vi.fn().mockResolvedValue([]),` to:

```tsx
    recommendations: vi.fn().mockResolvedValue({ total_tenues: 0, conseils: [] }),
```

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run __tests__/components/recommandations-tab.test.tsx __tests__/queries/garderobe.test.tsx`
Expected: PASS.

Run: `npx tsc --noEmit`
Expected: no errors (le type `Recommendation` n'est plus référencé nulle part).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/garderobe.ts frontend/components/garderobe/Garderobe.tsx frontend/components/garderobe/RecommandationsTab.tsx frontend/__tests__/queries/garderobe.test.tsx frontend/__tests__/components/recommandations-tab.test.tsx
git commit -m "feat(garderobe): onglet Recommandations -> conseils d'achat combinatoires (front)"
```

---

## Self-Review

**1. Spec coverage**
- `base_slot_of` / `count_outfits` / `purchase_advice` + PALETTE → Task 1. ✓
- Tenue = triplet couleur-compat 2-à-2, décompte pièces réelles → `count_outfits` (Task 1) + tests. ✓
- Candidats slot × PALETTE, gain marginal, tri déterministe, gains nuls exclus, top N → `purchase_advice` (Task 1) + tests. ✓
- API repointée + nouvelle réponse `{total_tenues, conseils}` → Task 2. ✓
- Suppression heuristiques (recommendations.py, test, export, RecommendationOut) → Task 2. ✓
- Frontend types + Garderobe + RecommandationsTab + cas vide + mock → Task 3. ✓
- `vue-360` non touché (routines) → confirmé (hors périmètre). ✓

**2. Placeholder scan** : aucun TODO/placeholder ; code complet à chaque step.

**3. Type consistency** :
- `purchase_advice` renvoie des dicts `{slot,couleur,debloque,total_apres}` (Task 1) → `ConseilAchat(**c)` (Task 2) → champs identiques au schéma `ConseilAchat` (Task 2) → type TS `ConseilAchat` (Task 3). ✓
- `count_outfits` → `total_tenues` (Task 2) → `ConseilsAchat.total_tenues` (Task 3). ✓
- `recommendations()` renvoie `ConseilsAchat` (Task 3) ; `Garderobe.tsx` défaut `{total_tenues:0,conseils:[]}` ; `RecommandationsTab` prop `recs: ConseilsAchat`. ✓
- `RecommendationOut` retiré de schemas (Task 2) ET de l'import insights (Task 2) — pas de référence pendante. ✓
- `get_purchase_recommendations` retiré de `__init__` + insights ; fichier + test supprimés → aucun import pendant (garde-fou import au Step 4). ✓
