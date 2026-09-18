# Rattachement automatique pièce → type objectif — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dériver automatiquement `Vetement.type_objectif` depuis la `sous_categorie`/`categorie` via une table de correspondance déterministe, déclenché par un bouton « Rattacher automatiquement » qui ne remplit que les valeurs vides.

**Architecture:** Une fonction pure `derive_type_objectif` consulte une table `MAPPING` (libellés normalisés → noms exacts de types objectif). Un endpoint `POST /garderobe/objectif/auto-rattacher` l'applique à toutes les pièces où `type_objectif is None` (jamais d'écrasement). Un bouton frontend déclenche l'endpoint et rafraîchit la vue. Aucun id touché, aucune migration.

**Tech Stack:** FastAPI + SQLModel ; Next.js + TanStack Query ; pytest, Vitest.

## Global Constraints

- Backend via `uv run` depuis `backend/` ; frontend via `npx vitest run`/`npx tsc --noEmit` depuis `frontend/`.
- Mécanisme **déterministe** (pas d'IA). Aucun nouvel id, aucune migration (le champ `type_objectif` existe déjà).
- **Jamais d'écrasement** : l'auto ne touche que `type_objectif is None`.
- `derive_type_objectif` ne renvoie un type que s'il appartient aux noms de types objectif courants (`ObjectifType.nom`) ; sinon `None`.
- `norm(s)` : NFKD→ASCII, minuscules, `[^a-z0-9]+`→espace, trim. Les clés de `MAPPING` ET l'entrée passent par le même `norm`.
- UI en français. Pas de nouvelle dépendance.
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`/`.` — working tree avec des milliers de modifs non liées).

---

## Task 1: Table de correspondance + fonction pure

**Files:**
- Create: `backend/app/services/garderobe/objectif_mapping.py`
- Test: `backend/tests/test_garderobe/test_objectif_mapping.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `norm(s: str | None) -> str`
  - `MAPPING: dict[str, str]` (clés normalisées → nom exact de type)
  - `derive_type_objectif(categorie: str | None, sous_categorie: str | None, type_names) -> str | None` (`type_names` = itérable de noms ; renvoie le type mappé s'il ∈ `type_names`, sinon `None` ; priorité à `sous_categorie` puis `categorie`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_garderobe/test_objectif_mapping.py
"""Table de correspondance sous_categorie/categorie -> type objectif."""
from __future__ import annotations

from app.services.garderobe.objectif_mapping import derive_type_objectif, norm

TYPES = [
    "T-shirts", "Polos", "Chemises", "Bottines", "Pantalons chino",
    "Jeans", "Jogging", "Vestes légères", "Vestes de sport",
    "Pantalons habillés", "Lunettes de soleil",
]


def test_norm_accents_casse_separateurs():
    assert norm("Vert Émeraude") == "vert emeraude"
    assert norm("T-shirt") == "t shirt"
    assert norm("  Button  Up ") == "button up"
    assert norm(None) == ""


def test_derive_mappings_connus():
    assert derive_type_objectif("Haut", "Polo", TYPES) == "Polos"
    assert derive_type_objectif("Haut", "T-shirt", TYPES) == "T-shirts"
    assert derive_type_objectif("Haut", "T-shirt Manches Longues", TYPES) == "T-shirts"
    assert derive_type_objectif("Shirt", "Button Up", TYPES) == "Chemises"
    assert derive_type_objectif("Chaussures", "Chelsea Boots", TYPES) == "Bottines"
    assert derive_type_objectif("Pantalon", "Chino", TYPES) == "Pantalons chino"
    assert derive_type_objectif("Veste", "Veste Sport", TYPES) == "Vestes de sport"
    assert derive_type_objectif("Yeux", "Lunettes de Soleil", TYPES) == "Lunettes de soleil"


def test_derive_insensible_casse_accents():
    assert derive_type_objectif("Haut", "polo", TYPES) == "Polos"
    assert derive_type_objectif("x", "CHINO", TYPES) == "Pantalons chino"


def test_derive_non_mappable_renvoie_none():
    assert derive_type_objectif("Montre", "Smartwatch", TYPES) is None
    assert derive_type_objectif("Bijoux", "Bracelet", TYPES) is None
    assert derive_type_objectif("Yeux", "Lunettes de vue", TYPES) is None
    assert derive_type_objectif(None, None, TYPES) is None


def test_derive_type_absent_des_noms_renvoie_none():
    # "Polos" mappé mais absent de la liste fournie -> None
    assert derive_type_objectif("Haut", "Polo", ["T-shirts"]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `backend/`): `uv run pytest tests/test_garderobe/test_objectif_mapping.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.garderobe.objectif_mapping'`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/garderobe/objectif_mapping.py
"""Table de correspondance déterministe sous_categorie/categorie -> type objectif.

Sert au rattachement automatique des vêtements (POST /garderobe/objectif/auto-rattacher).
Les vocabulaires ne coïncident pas (ex. « Button Up » -> « Chemises »), d'où une
table sémantique. Les pièces sans correspondance (montres, bijoux, lunettes de vue)
restent non rattachées et se gèrent au sélecteur manuel.
"""
from __future__ import annotations

import re
import unicodedata


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Libellés lisibles -> nom EXACT d'un type objectif (cf. Vetements.xlsx).
_RAW_MAPPING: dict[str, str] = {
    "T-shirt": "T-shirts",
    "T-shirt Manches Longues": "T-shirts",
    "Polo": "Polos",
    "Chemise": "Chemises",
    "Button Up": "Chemises",
    "Chino": "Pantalons chino",
    "Jean": "Jeans",
    "Jean Ballon": "Jeans",
    "Wide-Leg": "Pantalons habillés",
    "Trackpants": "Jogging",
    "Bomber": "Vestes légères",
    "Veste Sport": "Vestes de sport",
    "Chelsea Boots": "Bottines",
    "Bottes de Neige": "Bottines",
    "Lunettes de Soleil": "Lunettes de soleil",
}

# Clés normalisées au chargement -> lookup robuste (casse/accents/séparateurs).
MAPPING: dict[str, str] = {norm(k): v for k, v in _RAW_MAPPING.items()}


def derive_type_objectif(categorie, sous_categorie, type_names) -> str | None:
    """Type objectif dérivé de la pièce, ou None si non mappable / type absent.

    Priorité à `sous_categorie`, repli sur `categorie`. Ne renvoie un type que
    s'il appartient à `type_names` (les noms d'ObjectifType courants).
    """
    names = set(type_names)
    for key in (norm(sous_categorie), norm(categorie)):
        val = MAPPING.get(key) if key else None
        if val and val in names:
            return val
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_garderobe/test_objectif_mapping.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/garderobe/objectif_mapping.py backend/tests/test_garderobe/test_objectif_mapping.py
git commit -m "feat(garderobe): table de correspondance sous_categorie -> type objectif (fonction pure)"
```

---

## Task 2: Endpoint `POST /objectif/auto-rattacher` (+ run réel)

**Files:**
- Modify: `backend/app/api/garderobe/objectif.py` (import + nouvelle route)
- Test: `backend/tests/test_garderobe/test_objectif_api.py` (tests ajoutés)

**Interfaces:**
- Consumes: `derive_type_objectif` (Task 1), `ObjectifType`/`Vetement`.
- Produces: `POST /garderobe/objectif/auto-rattacher` → `{"rattaches": int, "non_mappes": int}` (ne remplit que `type_objectif is None`).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_garderobe/test_objectif_api.py`:

```python
def test_auto_rattacher_remplit_vides_sans_ecraser(client, session):
    session.add(ObjectifType(nom="Polos", ordre=0, quantite_objectif=3, echelle=["Lacoste"]))
    session.add(ObjectifType(nom="T-shirts", ordre=1, quantite_objectif=3, echelle=["Uniqlo"]))
    # pièce vide mappable
    session.add(Vetement(id="p1", nom="Polo vert", categorie="Haut", sous_categorie="Polo"))
    # pièce déjà rattachée manuellement (ne doit PAS bouger)
    session.add(Vetement(id="p2", nom="Tee", categorie="Haut", sous_categorie="T-shirt",
                         type_objectif="Polos"))
    # pièce vide non mappable
    session.add(Vetement(id="w1", nom="Montre", categorie="Montre", sous_categorie="Smartwatch"))
    session.commit()

    r = client.post("/garderobe/objectif/auto-rattacher")
    assert r.status_code == 200
    assert r.json() == {"rattaches": 1, "non_mappes": 1}

    assert session.get(Vetement, "p1").type_objectif == "Polos"      # rattaché
    assert session.get(Vetement, "p2").type_objectif == "Polos"      # inchangé (manuel préservé)
    assert session.get(Vetement, "w1").type_objectif is None         # non mappable
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_garderobe/test_objectif_api.py::test_auto_rattacher_remplit_vides_sans_ecraser -v`
Expected: FAIL — 404 (route inexistante).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/api/garderobe/objectif.py`, add the import (next to the other service imports):

```python
from app.services.garderobe.objectif import fill_slots
from app.services.garderobe.objectif_import import sync_objectif
from app.services.garderobe.objectif_mapping import derive_type_objectif
```

And add the route (after `post_objectif_sync`):

```python
@router.post("/objectif/auto-rattacher")
def post_objectif_auto_rattacher(session: Session = Depends(get_session)) -> dict:
    type_names = {t.nom for t in session.exec(select(ObjectifType)).all()}
    vets = session.exec(select(Vetement).where(Vetement.type_objectif.is_(None))).all()
    rattaches = 0
    non_mappes = 0
    for v in vets:
        t = derive_type_objectif(v.categorie, v.sous_categorie, type_names)
        if t:
            v.type_objectif = t
            rattaches += 1
        else:
            non_mappes += 1
    session.commit()
    return {"rattaches": rattaches, "non_mappes": non_mappes}
```

- [ ] **Step 4: Run test + regression**

Run: `uv run pytest tests/test_garderobe/test_objectif_api.py -v`
Expected: PASS (incl. le nouveau).

Run: `uv run pytest tests/test_garderobe -q`
Expected: all green.

- [ ] **Step 5: Run the auto-rattachement once on the real dev DB**

Run:
```bash
uv run python -c "
from sqlmodel import Session, select
from app.core.db import engine
from app.models.garderobe import Vetement, ObjectifType
from app.services.garderobe.objectif_mapping import derive_type_objectif
with Session(engine) as s:
    names = {t.nom for t in s.exec(select(ObjectifType)).all()}
    vets = s.exec(select(Vetement).where(Vetement.type_objectif.is_(None))).all()
    r = nm = 0
    for v in vets:
        t = derive_type_objectif(v.categorie, v.sous_categorie, names)
        if t:
            v.type_objectif = t; r += 1
        else:
            nm += 1
    s.commit()
    print('rattaches', r, 'non_mappes', nm)
"
```
Expected: `rattaches <N> non_mappes <M>` avec `N > 0` (les pièces mappables, ex. Polo/T-shirt/Chino/Chelsea Boots/Veste Sport…) ; `M` = pièces non mappables (montres, bijoux, lunettes de vue, et tout libellé pas encore dans la table). Aucune erreur.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/garderobe/objectif.py backend/tests/test_garderobe/test_objectif_api.py
git commit -m "feat(garderobe): endpoint auto-rattacher (remplit type_objectif vide via la table)"
```

(Le run du Step 5 ne modifie que la base dev — rien à committer pour ça.)

---

## Task 3: Frontend — client + hook + bouton « Rattacher automatiquement »

**Files:**
- Modify: `frontend/lib/garderobe.ts` (méthode `autoRattacher`)
- Modify: `frontend/lib/queries/garderobe.ts` (hook `useAutoRattacher`)
- Modify: `frontend/components/garderobe/ObjectifTab.tsx` (bouton)
- Modify: `frontend/__tests__/components/objectif-tab.test.tsx` (mock + test)

**Interfaces:**
- Consumes: endpoint `POST /garderobe/objectif/auto-rattacher` (Task 2).
- Produces: `garderobeApi.autoRattacher()` ; `useAutoRattacher()`.

- [ ] **Step 1: Write the failing test**

In `frontend/__tests__/components/objectif-tab.test.tsx`, add `useAutoRattacher` to the `vi.mock("@/lib/queries/garderobe", ...)` factory. First add a stable mock fn at the top of the file (before the `vi.mock` call uses it — vitest hoists `vi.mock`, so declare the fn with `vi.hoisted`):

```tsx
const autoMutate = vi.hoisted(() => vi.fn());
```

Then inside the mock factory object, add:

```tsx
  useAutoRattacher: () => ({ mutate: autoMutate, isPending: false }),
```

Add a test inside the existing `describe`:

```tsx
  it("le bouton Rattacher automatiquement déclenche la mutation", () => {
    render(<ObjectifTab />, { wrapper });
    fireEvent.click(screen.getByText(/Rattacher automatiquement/i));
    expect(autoMutate).toHaveBeenCalled();
  });
```

Ensure `fireEvent` is imported from `@testing-library/react` at the top of the file (add it to the existing import if missing).

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/components/objectif-tab.test.tsx`
Expected: FAIL — pas de bouton « Rattacher automatiquement » / `useAutoRattacher` non exporté.

- [ ] **Step 3: Write minimal implementation**

In `frontend/lib/garderobe.ts`, add to the `garderobeApi` object (after `syncObjectif`):

```ts
  autoRattacher: () =>
    api<{ rattaches: number; non_mappes: number }>(`/garderobe/objectif/auto-rattacher`, {
      method: "POST",
    }),
```

In `frontend/lib/queries/garderobe.ts`, add the hook (after `useSyncObjectif`):

```ts
export function useAutoRattacher() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: garderobeApi.autoRattacher, onSuccess: invalidate });
}
```

In `frontend/components/garderobe/ObjectifTab.tsx`:

- Update the imports (line 3-4):

```tsx
import { RefreshCw, Sparkles } from "lucide-react";
import { useObjectif, useSyncObjectif, useAutoRattacher } from "@/lib/queries/garderobe";
```

- Add the hook next to the others (after `const syncMut = useSyncObjectif();`):

```tsx
  const autoMut = useAutoRattacher();
```

- Add the button just before the « Re-synchroniser l'Excel » button (inside the same header `div`, so both sit on the right). Replace the single `<button>…Re-synchroniser…</button>` block with a wrapper holding both:

```tsx
        <div className="flex items-center gap-2">
          <button
            onClick={() => autoMut.mutate()}
            disabled={autoMut.isPending}
            className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <Sparkles className={`h-4 w-4 ${autoMut.isPending ? "animate-pulse" : ""}`} />
            Rattacher automatiquement
          </button>
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending}
            className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
            Re-synchroniser l'Excel
          </button>
        </div>
```

- [ ] **Step 4: Run tests + typecheck**

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx __tests__/queries/garderobe.test.tsx`
Expected: PASS.

Run: `npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/garderobe.ts frontend/lib/queries/garderobe.ts frontend/components/garderobe/ObjectifTab.tsx frontend/__tests__/components/objectif-tab.test.tsx
git commit -m "feat(garderobe): bouton Rattacher automatiquement dans l'onglet Objectif"
```

---

## Self-Review

**1. Spec coverage**
- Table `MAPPING` + `norm` + `derive_type_objectif` (priorité sous_cat, contrôle ∈ type_names) → Task 1. ✓
- Endpoint `auto-rattacher` (remplit `is None`, n'écrase pas, compteurs) → Task 2. ✓
- Run réel pour les 23 → Task 2 Step 5. ✓
- Frontend client + hook + bouton dans l'onglet → Task 3. ✓
- Jamais d'écrasement → `where(type_objectif.is_(None))` (Task 2) + test « manuel préservé ». ✓
- Pièces non mappables → `derive` renvoie None (Task 1 test) → comptées `non_mappes`. ✓
- Sélecteur manuel inchangé (override) → on ne le touche pas. ✓

**2. Placeholder scan** : aucun TODO/placeholder ; code complet à chaque step.

**3. Type consistency** :
- `derive_type_objectif(categorie, sous_categorie, type_names)` même signature en Task 1 (def), Task 2 (appel) et le run Step 5. ✓
- `MAPPING` clés normalisées (via `norm`) ET entrée normalisée à l'appel → lookup cohérent. ✓
- `autoRattacher()` → `{rattaches, non_mappes}` (Task 3 client) cohérent avec la réponse de l'endpoint (Task 2). ✓
- `useAutoRattacher`/`autoMutate` cohérents entre hook (Task 3), mock et test (Task 3). ✓
- `vi.hoisted` requis car `vi.mock` est hoisté au-dessus des déclarations → `autoMutate` doit être hoisté pour être référencé dans la factory. ✓
