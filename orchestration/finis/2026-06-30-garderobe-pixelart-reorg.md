# Réorganisation images pixel art + vignette Objectif — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Découpler l'image pixel art de l'`id` du vêtement via un champ `Vetement.image`, ranger les 23 PNG en `assets/<catégorie>/<slug>.png`, et afficher la vignette dans l'onglet Objectif.

**Architecture:** Nouvelle colonne `Vetement.image` (chemin relatif). Un script one-time range/renomme les PNG et peuple `image`. La fonction pure `fill_slots` et le schéma `Emplacement` transportent `image` jusqu'à `GET /objectif`. Le frontend lit `image` via un helper `imageUrl(v)` (repli sur `assetUrl(v.id)` puis emoji) dans l'Inventaire, la Tenue, et l'onglet Objectif.

**Tech Stack:** FastAPI + SQLModel + Alembic + openpyxl ; Next.js + TanStack Query ; pytest, Vitest.

## Global Constraints

- **Aucun `id` de vêtement n'est modifié** (PK référencées dans `TenueHistory`/planner).
- Backend via `uv run` depuis `backend/` ; frontend via `npx vitest run` / `npx tsc --noEmit` depuis `frontend/`.
- `Vetement.image` = chemin relatif sous `assets/`, ex. `Haut/t-shirt-uniqlo-gris-anthracite.png`. Servi en statique Next sous `/garderobe/assets/` (pas de préfixe base media).
- Slug = `slugify(sous_categorie)-slugify(marque)-slugify(couleur)`, tokens vides ignorés, `-` dédupliqués ; collision `<cat>/<slug>` → suffixe `-2`, `-3` déterministe par ordre d'`id` croissant.
- `slugify` : NFKD → ASCII, minuscules, `[^a-z0-9]+` → `-`, trim/dedup des `-`.
- Repli conservé : si `image` nul → `assetUrl(v.id)` (`/garderobe/assets/{id}.png`) → emoji (via `onError`).
- Migration Alembic `down_revision = "v610objectifgarderobe"` (tête courante).
- UI en français. Pas de nouvelle dépendance. Pas d'aides d'accessibilité ajoutées.
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`/`.` — le working tree porte des milliers de modifs non liées).

---

## Task 1: Colonne `Vetement.image` + migration + schémas

**Files:**
- Modify: `backend/app/models/garderobe.py` (champ `image` sur `Vetement`)
- Modify: `backend/app/api/garderobe/schemas.py` (`VetementBase`, `VetementUpdate`)
- Modify: `backend/app/api/garderobe/common.py` (`vetement_to_dict`)
- Create: `backend/alembic/versions/20260630_1400_i620_garderobe_image.py`
- Test: `backend/tests/test_garderobe/test_objectif_api.py` (1 test ajouté)

**Interfaces:**
- Consumes: rien.
- Produces: `Vetement.image: Optional[str]` ; `VetementRead.image`/`VetementUpdate.image` ; PATCH `/vetements/{id}` accepte `{"image": str|null}`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_garderobe/test_objectif_api.py`:

```python
def test_patch_vetement_image(client, session):
    session.add(Vetement(id="vi", nom="Tee", categorie="Haut"))
    session.commit()
    r = client.patch("/garderobe/vetements/vi", json={"image": "Haut/tee-uniqlo-noir.png"})
    assert r.status_code == 200
    assert r.json()["image"] == "Haut/tee-uniqlo-noir.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `uv run pytest tests/test_garderobe/test_objectif_api.py::test_patch_vetement_image -v`
Expected: FAIL — `image` non accepté / absent de la réponse.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/models/garderobe.py`, add after the `type_objectif` line in `Vetement`:

```python
    type_objectif: Optional[str] = None  # relie la pièce à un ObjectifType.nom
    image: Optional[str] = None  # chemin relatif sous assets/, ex. "Haut/xxx.png"
```

In `backend/app/api/garderobe/schemas.py`, add `image` to `VetementBase` (after `type_objectif`) and to `VetementUpdate` (after `type_objectif`):

```python
    type_objectif: Optional[str] = None
    image: Optional[str] = None
```

In `backend/app/api/garderobe/common.py`, add to the dict in `vetement_to_dict` (after the `type_objectif` line):

```python
        "type_objectif": v.type_objectif,
        "image": v.image,
```

Create `backend/alembic/versions/20260630_1400_i620_garderobe_image.py`:

```python
"""vetement.image : chemin pixel art relatif (#garderobe-pixelart)

Revision ID: i620garderobeimage
Revises: v610objectifgarderobe
Create Date: 2026-06-30 14:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "i620garderobeimage"
down_revision = "v610objectifgarderobe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.add_column(sa.Column("image", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vetement") as batch_op:
        batch_op.drop_column("image")
```

- [ ] **Step 4: Run test + migration**

Run: `uv run pytest tests/test_garderobe/test_objectif_api.py -v`
Expected: PASS (incl. `test_patch_vetement_image`).

Run: `uv run alembic upgrade head`
Expected: applies `i620garderobeimage` cleanly.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/garderobe.py backend/app/api/garderobe/schemas.py backend/app/api/garderobe/common.py backend/alembic/versions/20260630_1400_i620_garderobe_image.py backend/tests/test_garderobe/test_objectif_api.py
git commit -m "feat(garderobe): colonne Vetement.image (chemin pixel art) + migration"
```

---

## Task 2: `fill_slots` + `Emplacement` transportent `image`

**Files:**
- Modify: `backend/app/services/garderobe/objectif.py` (`fill_slots`, `_empty_slot`)
- Modify: `backend/app/api/garderobe/schemas.py` (`Emplacement`)
- Modify: `backend/app/api/garderobe/objectif.py` (`get_objectif` owned dict)
- Test: `backend/tests/test_garderobe/test_objectif.py` (1 test) + `backend/tests/test_garderobe/test_objectif_api.py` (1 test)

**Interfaces:**
- Consumes: `Vetement.image` (Task 1).
- Produces: chaque dict d'emplacement/excédent de `fill_slots` contient `"image"` ; `Emplacement.image: Optional[str]` ; `GET /objectif` renvoie `image` par emplacement.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_garderobe/test_objectif.py`:

```python
def test_fill_slots_transporte_image():
    ech = ["Uniqlo U", "Visvim"]
    owned = [{"id": "a", "nom": "A", "marque": "Visvim", "image": "Haut/a.png"}]
    res = fill_slots(ech, 1, owned)
    assert res["emplacements"][0]["image"] == "Haut/a.png"


def test_fill_slots_empty_slot_image_none():
    res = fill_slots(["X"], 2, [])
    assert res["emplacements"][0]["image"] is None
```

Append to `backend/tests/test_garderobe/test_objectif_api.py`:

```python
def test_get_objectif_emplacement_image(client, session):
    session.add(ObjectifType(nom="T-shirts", ordre=0, quantite_objectif=1,
                             echelle=["Uniqlo U"]))
    session.add(Vetement(id="t", nom="Tee", categorie="Haut", marque="Uniqlo U",
                         type_objectif="T-shirts", image="Haut/tee.png"))
    session.commit()
    data = client.get("/garderobe/objectif").json()
    emp = data["types"][0]["emplacements"][0]
    assert emp["image"] == "Haut/tee.png"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_garderobe/test_objectif.py::test_fill_slots_transporte_image tests/test_garderobe/test_objectif_api.py::test_get_objectif_emplacement_image -v`
Expected: FAIL — `KeyError: 'image'` / `image` absent de la réponse.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/services/garderobe/objectif.py`, add `"image": None` to `_empty_slot`:

```python
def _empty_slot() -> dict:
    return {
        "statut": "vide",
        "vetement_id": None,
        "vetement_nom": None,
        "marque": None,
        "position": None,
        "hors_echelle": False,
        "image": None,
    }
```

And in `fill_slots`, add `"image"` to the enriched dict (after `"marque"`):

```python
        enriched.append(
            {
                "statut": "rempli",
                "vetement_id": o.get("id"),
                "vetement_nom": o.get("nom"),
                "marque": o.get("marque"),
                "position": pos,
                "hors_echelle": pos is None,
                "image": o.get("image"),
            }
        )
```

In `backend/app/api/garderobe/schemas.py`, add to `Emplacement` (after `hors_echelle`):

```python
    hors_echelle: bool = False
    image: Optional[str] = None
```

In `backend/app/api/garderobe/objectif.py`, include `image` in the owned dict:

```python
        owned_by_type.setdefault(v.type_objectif, []).append(
            {"id": v.id, "nom": v.nom, "marque": v.marque, "image": v.image}
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_garderobe/test_objectif.py tests/test_garderobe/test_objectif_api.py -v`
Expected: PASS (anciens + nouveaux).

Run (régression): `uv run pytest tests/test_garderobe -q`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/garderobe/objectif.py backend/app/api/garderobe/schemas.py backend/app/api/garderobe/objectif.py backend/tests/test_garderobe/test_objectif.py backend/tests/test_garderobe/test_objectif_api.py
git commit -m "feat(garderobe): emplacement Objectif transporte l'image pixel art de la pièce"
```

---

## Task 3: Script de réorganisation des PNG + peuplement `image`

**Files:**
- Create: `backend/scripts/reorg_garderobe_assets.py`
- Test: `backend/tests/test_garderobe/test_reorg_assets.py`

**Interfaces:**
- Consumes: `Vetement` (a `image`, Task 1).
- Produces: fonctions pures `slugify(s) -> str`, `build_slug(sous_categorie, marque, couleur) -> str`, `assign_paths(rows: list[dict]) -> dict[str, str]` (clé = id, valeur = `"<categorie>/<slug>.png"`). `main()` déplace les PNG et écrit `Vetement.image`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_garderobe/test_reorg_assets.py`:

```python
"""Fonctions pures du script de réorganisation des images pixel art."""
from __future__ import annotations

from scripts.reorg_garderobe_assets import assign_paths, build_slug, slugify


def test_slugify_accents_espaces_casse():
    assert slugify("Vert Émeraude") == "vert-emeraude"
    assert slugify("  COS  ") == "cos"
    assert slugify("Noir/Anthracite") == "noir-anthracite"
    assert slugify(None) == ""


def test_build_slug_ignore_tokens_vides():
    assert build_slug("T-shirt", "Uniqlo", "Gris anthracite") == "t-shirt-uniqlo-gris-anthracite"
    assert build_slug(None, "Garmin", "Noir") == "garmin-noir"
    assert build_slug("", "", "") == "sans-nom"


def test_assign_paths_collision_suffixe_deterministe():
    rows = [
        {"id": "Fossil02", "categorie": "Montre", "sous_categorie": "Montre Automatique",
         "marque": "Fossil", "couleur": "Marron"},
        {"id": "Fossil01", "categorie": "Montre", "sous_categorie": "Montre Analogique",
         "marque": "Fossil", "couleur": "Marron"},
    ]
    paths = assign_paths(rows)
    # sous-catégorie distingue déjà → pas de suffixe
    assert paths["Fossil01"] == "Montre/montre-analogique-fossil-marron.png"
    assert paths["Fossil02"] == "Montre/montre-automatique-fossil-marron.png"


def test_assign_paths_vraie_collision_recoit_suffixe():
    rows = [
        {"id": "b", "categorie": "Haut", "sous_categorie": "Polo", "marque": "Lacoste", "couleur": "Vert"},
        {"id": "a", "categorie": "Haut", "sous_categorie": "Polo", "marque": "Lacoste", "couleur": "Vert"},
    ]
    paths = assign_paths(rows)
    # ordre par id croissant : 'a' d'abord (n=1), 'b' ensuite (n=2)
    assert paths["a"] == "Haut/polo-lacoste-vert.png"
    assert paths["b"] == "Haut/polo-lacoste-vert-2.png"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_reorg_assets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.reorg_garderobe_assets'`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/scripts/reorg_garderobe_assets.py`:

```python
"""Réorganise les images pixel art : assets/<catégorie>/<slug>.png + Vetement.image.

One-time. Idempotent : ne refait rien si l'image est déjà à la bonne place.

Usage (depuis backend/) :
    uv run python -m scripts.reorg_garderobe_assets
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.models.garderobe import Vetement


def slugify(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def build_slug(sous_categorie: str | None, marque: str | None, couleur: str | None) -> str:
    parts = [p for p in (slugify(sous_categorie), slugify(marque), slugify(couleur)) if p]
    return "-".join(parts) or "sans-nom"


def assign_paths(rows: list[dict]) -> dict[str, str]:
    """id -> '<categorie>/<slug>.png', dédup déterministe (tri par id croissant)."""
    out: dict[str, str] = {}
    used: dict[str, int] = {}
    for r in sorted(rows, key=lambda r: r["id"]):
        cat = r.get("categorie") or "Autre"
        slug = build_slug(r.get("sous_categorie"), r.get("marque"), r.get("couleur"))
        base = f"{cat}/{slug}"
        n = used.get(base, 0) + 1
        used[base] = n
        out[r["id"]] = f"{base}.png" if n == 1 else f"{base}-{n}.png"
    return out


def _find_source_png(assets_dir: Path, vetement_id: str) -> Path | None:
    """PNG source à plat dont le stem == id (insensible à la casse)."""
    target = vetement_id.casefold()
    for p in assets_dir.glob("*.png"):
        if p.stem.casefold() == target:
            return p
    return None


def _git_mv(repo_root: Path, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "mv", str(src), str(dst)],
            check=True, capture_output=True,
        )
    except Exception:
        shutil.move(str(src), str(dst))
        subprocess.run(["git", "-C", str(repo_root), "add", str(dst)], check=False)


def main() -> dict:
    assets_dir = settings.repo_root / "frontend" / "public" / "garderobe" / "assets"
    moved = 0
    missing: list[str] = []
    with Session(engine) as s:
        vets = s.exec(select(Vetement)).all()
        rows = [
            {"id": v.id, "categorie": v.categorie, "sous_categorie": v.sous_categorie,
             "marque": v.marque, "couleur": v.couleur}
            for v in vets
        ]
        paths = assign_paths(rows)
        for v in vets:
            rel = paths[v.id]
            dst = assets_dir / rel
            if v.image == rel and dst.exists():
                continue
            src = _find_source_png(assets_dir, v.id)
            if src is None:
                missing.append(v.id)
                continue
            _git_mv(settings.repo_root, src, dst)
            v.image = rel
            moved += 1
        s.commit()
    print(f"déplacés={moved} sans_png={missing}")
    return {"moved": moved, "missing": missing}


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_reorg_assets.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the reorg once + verify**

Run: `uv run python -m scripts.reorg_garderobe_assets`
Expected: `déplacés=23 sans_png=[]` (les 23 PNG déplacés en sous-dossiers, `image` peuplé).

Run (vérif): `uv run python -c "from sqlmodel import Session, select; from app.core.db import engine; from app.models.garderobe import Vetement; s=Session(engine); vs=s.exec(select(Vetement)).all(); print('avec image:', sum(1 for v in vs if v.image), '/', len(vs)); print(vs[0].image)"`
Expected: `avec image: 23 / 23` et un chemin type `Haut/...png`.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/reorg_garderobe_assets.py backend/tests/test_garderobe/test_reorg_assets.py "frontend/public/garderobe/assets"
git commit -m "feat(garderobe): script de réorg des images pixel art (assets/<catégorie>/<slug>.png)"
```

(Le `git mv` a déjà mis en scène les déplacements ; `git add` du dossier assets capture les nouveaux chemins. Vérifier avec `git status` que seuls les PNG garde-robe + les 2 fichiers de script sont stagés.)

---

## Task 4: Frontend — type `image` + helper `imageUrl` + Inventaire/Tenue

**Files:**
- Modify: `frontend/lib/garderobe.ts` (type `Vetement.image`, fonction `imageUrl`)
- Modify: `frontend/components/garderobe/InventaireTab.tsx:128` (`assetUrl(v.id)` → `imageUrl(v)`)
- Modify: `frontend/components/garderobe/SlotCard.tsx:78` (`assetUrl(item.id)` → `imageUrl(item)`)
- Modify: `frontend/__tests__/components/inventaire-type-objectif.test.tsx` (fixture `tee` : ajouter `image`)
- Test: `frontend/__tests__/lib-imageurl.test.ts` (créer)

**Interfaces:**
- Consumes: `Vetement.image` (exposé par l'API, Task 1).
- Produces: `imageUrl(v: Pick<Vetement, "image" | "id">): string` ; `Vetement.image: string | null`.

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/lib-imageurl.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { imageUrl } from "@/lib/garderobe";

describe("imageUrl", () => {
  it("utilise image si présent", () => {
    expect(imageUrl({ id: "v1", image: "Haut/tee.png" })).toBe("/garderobe/assets/Haut/tee.png");
  });
  it("repli sur l'id si image nul", () => {
    expect(imageUrl({ id: "v1", image: null })).toBe("/garderobe/assets/v1.png");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/lib-imageurl.test.ts`
Expected: FAIL — `imageUrl` non exporté.

- [ ] **Step 3: Write minimal implementation**

In `frontend/lib/garderobe.ts`, add `image` to the `Vetement` type (after `couleur`):

```ts
  couleur: string | null;
  type_objectif: string | null;
  image: string | null;
```

(Note : `type_objectif` est déjà présent ; ajouter seulement la ligne `image`.)

And add `imageUrl` next to `assetUrl` (near the bottom, after the `assetUrl` function):

```ts
/** URL de la vignette : `image` (chemin rangé) si présent, sinon repli sur l'id. */
export function imageUrl(v: Pick<Vetement, "image" | "id">): string {
  if (v.image) return `/garderobe/assets/${v.image}`;
  return assetUrl(v.id);
}
```

In `frontend/components/garderobe/InventaireTab.tsx`: update the import to include `imageUrl`, and replace the pixel-art `<img src>`:

- Change the import line `import { emojiForCategorie, assetUrl, mediaUrl } from "@/lib/garderobe";` to:

```tsx
import { emojiForCategorie, imageUrl, mediaUrl } from "@/lib/garderobe";
```

- Change `src={assetUrl(v.id)}` (the pixel-art fallback img) to:

```tsx
        <img src={imageUrl(v)} alt={v.nom} onError={() => setFailed(true)} style={{ imageRendering: "pixelated", height: "56px", width: "auto" }} />
```

In `frontend/components/garderobe/SlotCard.tsx`: update the import and the img src:

- Change `import { emojiForCategorie, assetUrl } from "@/lib/garderobe";` to:

```tsx
import { emojiForCategorie, imageUrl } from "@/lib/garderobe";
```

- Change `src={assetUrl(item.id)}` to:

```tsx
          src={imageUrl(item)}
```

In `frontend/__tests__/components/inventaire-type-objectif.test.tsx`, add `image: null,` to the `tee` fixture (after `type_objectif: "T-shirts",`) so the `Vetement` literal stays type-complete:

```tsx
  type_objectif: "T-shirts",
  image: null,
```

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run __tests__/lib-imageurl.test.ts __tests__/components/inventaire-type-objectif.test.tsx`
Expected: PASS.

Run: `npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/garderobe.ts frontend/components/garderobe/InventaireTab.tsx frontend/components/garderobe/SlotCard.tsx frontend/__tests__/components/inventaire-type-objectif.test.tsx frontend/__tests__/lib-imageurl.test.ts
git commit -m "feat(garderobe): helper imageUrl (champ image -> repli id) sur Inventaire + Tenue"
```

---

## Task 5: Frontend — vignette pixel art dans `ObjectifBar`

**Files:**
- Modify: `frontend/lib/garderobe.ts` (type `Emplacement.image`)
- Modify: `frontend/components/garderobe/ObjectifBar.tsx` (vignette)
- Modify: `frontend/__tests__/components/objectif-tab.test.tsx` (mock `image` + assertion)

**Interfaces:**
- Consumes: `Emplacement.image` (renvoyé par `GET /objectif`, Task 2).
- Produces: rien.

- [ ] **Step 1: Write the failing test**

In `frontend/__tests__/components/objectif-tab.test.tsx`, add `image` to the two mock emplacements (the filled one gets a path, the empty one `null`). Change the `emplacements` array (filled + empty) to:

```tsx
      emplacements: [
        { statut: "rempli", vetement_id: "v1", vetement_nom: "Tee", marque: "Visvim", position: 100, hors_echelle: false, image: "Haut/tee.png" },
        { statut: "vide", vetement_id: null, vetement_nom: null, marque: null, position: null, hors_echelle: false, image: null },
      ],
```

Then add a test inside the existing `describe`:

```tsx
  it("affiche la vignette pixel art d'un emplacement rempli", () => {
    render(<ObjectifTab />, { wrapper });
    const img = screen.getByAltText("Tee") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/garderobe/assets/Haut/tee.png");
  });
```

(If `ObjectifTab` is imported at the top of the file already, reuse it; otherwise it is the component under test in this file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx`
Expected: FAIL — pas de `<img alt="Tee">` (ObjectifBar ne rend pas encore d'image), et/ou erreur TS sur `image` manquant si le type n'est pas encore étendu.

- [ ] **Step 3: Write minimal implementation**

In `frontend/lib/garderobe.ts`, add `image` to the `Emplacement` type (after `hors_echelle`):

```ts
  hors_echelle: boolean;
  image: string | null;
```

Rewrite `frontend/components/garderobe/ObjectifBar.tsx`:

```tsx
"use client";

import { useState } from "react";
import { type Emplacement } from "@/lib/garderobe";

/** Une ligne d'emplacement : vignette + nom de marque + barre 0→100 (Q/P → Qualité Max). */
export function ObjectifBar({ slot, excedent = false }: { slot: Emplacement; excedent?: boolean }) {
  const empty = slot.statut === "vide";
  const pos = slot.position ?? 0;
  const [imgFailed, setImgFailed] = useState(false);

  let barClass = "bg-[var(--primary)]";
  if (excedent) barClass = "bg-[var(--destructive)]";
  else if (empty) barClass = "bg-transparent";
  else if (slot.hors_echelle) barClass = "bg-[var(--muted-foreground)]"; // marque hors échelle = gris

  return (
    <div className={`flex items-center gap-3 ${excedent ? "text-[var(--destructive)]" : ""}`}>
      <div className="h-6 w-6 shrink-0 flex items-center justify-center">
        {!empty && slot.image && !imgFailed && (
          <img
            src={`/garderobe/assets/${slot.image}`}
            alt={slot.vetement_nom ?? ""}
            onError={() => setImgFailed(true)}
            style={{ imageRendering: "pixelated" }}
            className="max-h-6 max-w-6 object-contain"
          />
        )}
      </div>
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

(La `<div className="h-6 w-6 shrink-0 ...">` réserve toujours la largeur de vignette, donc les barres restent alignées même sur les lignes vides.)

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx __tests__/queries/garderobe.test.tsx`
Expected: PASS.

Run: `npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/garderobe.ts frontend/components/garderobe/ObjectifBar.tsx frontend/__tests__/components/objectif-tab.test.tsx
git commit -m "feat(garderobe): vignette pixel art dans les emplacements de l'onglet Objectif"
```

---

## Self-Review

**1. Spec coverage**
- `Vetement.image` colonne + migration + schémas + common → Task 1. ✓
- `Emplacement.image` + `fill_slots` transporte image + GET → Task 2. ✓
- Slug `<sous_cat>-<marque>-<couleur>`, collision déterministe, `slugify` NFKD → Task 3 (`slugify`/`build_slug`/`assign_paths` + tests, dont la collision Fossil/Lacoste). ✓
- Réorg one-time (déplacement PNG + peuplement `image`, insensible à la casse, idempotent) → Task 3 `main()` + Step 5. ✓
- Helper `imageUrl` (image → repli id → emoji via onError) + bascule Inventaire/Tenue → Task 4. ✓
- Vignette `ObjectifBar` (rempli/excédent, vide réserve l'espace, onError) → Task 5. ✓
- Aucun id modifié → confirmé (seul `image` ajouté). ✓
- Repli `assetUrl(v.id)` conservé → `imageUrl` (Task 4). ✓

**2. Placeholder scan** : aucun TODO/placeholder ; code complet à chaque step.

**3. Type consistency** :
- `fill_slots` ajoute la clé `"image"` aux dicts (Task 2) → `Emplacement(**e)` (déjà en place dans `get_objectif`) accepte `image` car `Emplacement` gagne le champ (Task 2). ✓
- `owned` dict porte `"image"` (Task 2 GET) → `fill_slots` lit `o.get("image")` (Task 2). ✓
- `imageUrl(v: Pick<Vetement,"image"|"id">)` (Task 4) cohérent avec `Vetement.image: string|null` (Task 4) et l'usage `imageUrl(v)`/`imageUrl(item)`. ✓
- `Emplacement.image: string|null` (Task 5 type) cohérent avec le mock de test et `slot.image` dans ObjectifBar. ✓
- Migration `down_revision="v610objectifgarderobe"` = tête courante vérifiée. ✓
- Tâche 4 met à jour la fixture `tee: Vetement` (ajout `image`) → pas de rupture TS sur le littéral `Vetement`. ✓
