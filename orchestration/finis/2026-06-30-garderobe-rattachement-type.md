# Rattachement pièce → type objectif — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un sélecteur « Type objectif » sur chaque carte de l'onglet Inventaire pour rattacher un vêtement à l'un des 55 types objectif (PATCH `type_objectif`), ce qui remplit l'onglet Objectif.

**Architecture:** Frontend uniquement. `InventaireTab` lit les noms de types via le hook existant `useObjectif()` et les passe à chaque `VetementCard`, qui rend un `<select>` ; à chaque changement il appelle le hook existant `useUpdateVetement()` (`PATCH /garderobe/vetements/{id}`), dont l'`onSuccess` invalide `["garderobe"]` et rafraîchit l'onglet Objectif. Aucun changement backend/API/DB.

**Tech Stack:** Next.js (React client components), TanStack Query, Vitest + @testing-library/react (jsdom).

## Global Constraints

- Frontend uniquement. Aucun endpoint, schéma, ou migration nouveau.
- Tests via `npx vitest run <file>` depuis `frontend/` ; typecheck via `npx tsc --noEmit`.
- UI en français. Conventions composants garde-robe : `"use client"`, CSS vars (`var(--border)`, `var(--card)`), pas de nouvelles dépendances.
- Réutiliser les hooks existants `useObjectif()` (fournit `data.types[].nom`) et `useUpdateVetement()` (mutation `{ id: string; patch: VetementUpdate }`). Ne PAS créer de nouvel endpoint (YAGNI).
- Préférence utilisateur : pas d'aides d'accessibilité ajoutées pour l'utilisateur ; le `title="Type objectif"` sert d'ancrage de test (infobulle), pas un ajout a11y dédié.
- L'option vide (`value=""`) envoie `type_objectif: null` (déliaison). Si `v.type_objectif` existe mais n'est pas dans la liste (orphelin), il reste présent comme option sélectionnée pour ne pas perdre la valeur.

---

## Task 1: Sélecteur « Type objectif » sur la carte Inventaire

**Files:**
- Modify: `frontend/components/garderobe/InventaireTab.tsx` (imports, `InventaireTab` body, `VetementCard` signature + nouveau `<select>`)
- Test: `frontend/__tests__/components/inventaire-type-objectif.test.tsx` (créer)

**Interfaces:**
- Consumes (existants, ne pas redéfinir) :
  - `useObjectif()` → `{ data?: { types: { nom: string }[] } , ... }` (depuis `@/lib/queries/garderobe`)
  - `useUpdateVetement()` → `{ mutate: (p: { id: string; patch: { type_objectif?: string | null } }) => void, ... }`
  - `useUploadVetementPhoto()` → `{ mutateAsync, ... }` (déjà utilisé par `VetementCard`)
  - type `Vetement` (a un champ `type_objectif: string | null`)
- Produces: rien (feuille de l'arbre de composants).

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/components/inventaire-type-objectif.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { Vetement } from "@/lib/garderobe";

const mutate = vi.fn();

vi.mock("@/lib/queries/garderobe", () => ({
  useUploadVetementPhoto: () => ({ mutateAsync: vi.fn() }),
  useUpdateVetement: () => ({ mutate }),
  useObjectif: () => ({ data: { types: [{ nom: "T-shirts" }, { nom: "Polos" }] } }),
}));

import { InventaireTab } from "@/components/garderobe/InventaireTab";

const tee: Vetement = {
  id: "v1", nom: "Tee", marque: "Uniqlo", categorie: "Haut",
  sous_categorie: null, matiere: null, couleur: "Noir",
  temp_min: null, temp_max: null, etat_propre: null, usure_max: null,
  portes: 0, impermeable: false, style: null, extra: null,
  type_objectif: "T-shirts",
  proprete_pct: 100, vie_pct: 100, needs_wash: false, is_worn_out: false,
  ports_avant_lavage: 3, thermal_score: 0, saison: "toutes", entretien: null,
};

describe("InventaireTab — rattachement type objectif", () => {
  beforeEach(() => mutate.mockClear());

  it("le select montre le type courant et PATCH au changement", () => {
    render(<InventaireTab wardrobe={[tee]} />);
    const select = screen.getByTitle(/type objectif/i) as HTMLSelectElement;
    expect(select.value).toBe("T-shirts");
    fireEvent.change(select, { target: { value: "Polos" } });
    expect(mutate).toHaveBeenCalledWith({ id: "v1", patch: { type_objectif: "Polos" } });
  });

  it("l'option vide envoie null (déliaison)", () => {
    render(<InventaireTab wardrobe={[tee]} />);
    const select = screen.getByTitle(/type objectif/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "" } });
    expect(mutate).toHaveBeenCalledWith({ id: "v1", patch: { type_objectif: null } });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/components/inventaire-type-objectif.test.tsx`
Expected: FAIL — pas de `<select title="Type objectif">` rendu (`Unable to find an element with the title: /type objectif/i`).

- [ ] **Step 3: Write minimal implementation**

In `frontend/components/garderobe/InventaireTab.tsx`:

3a. Replace the imports block (lines 1-7) with (adds `useMemo` is already imported; add the two hooks):

```tsx
"use client";

import { useMemo, useRef, useState } from "react";
import type { Vetement } from "@/lib/garderobe";
import { emojiForCategorie, assetUrl, mediaUrl } from "@/lib/garderobe";
import { useObjectif, useUpdateVetement, useUploadVetementPhoto } from "@/lib/queries/garderobe";
import { dominantColorFromFile } from "@/lib/dominantColor";
```

3b. Inside `InventaireTab`, after the existing `useState` declarations (right before the `cats` memo, around line 15), add:

```tsx
  const objectifQ = useObjectif();
  const typeNames = useMemo(
    () => (objectifQ.data?.types ?? []).map((t) => t.nom),
    [objectifQ.data],
  );
```

3c. Pass `typeNames` to each card — change the render line (currently `<VetementCard key={v.id} v={v} onReload={onReload} />`) to:

```tsx
            <VetementCard key={v.id} v={v} onReload={onReload} typeNames={typeNames} />
```

3d. Change the `VetementCard` signature to accept `typeNames`:

```tsx
function VetementCard({ v, onReload, typeNames }: { v: Vetement; onReload?: () => void; typeNames: string[] }) {
```

3e. Inside `VetementCard`, after the existing `const uploadMutation = useUploadVetementPhoto();` line, add the update hook and the option list:

```tsx
  const updateMutation = useUpdateVetement();
  const current = v.type_objectif ?? "";
  const opts = current && !typeNames.includes(current) ? [current, ...typeNames] : typeNames;
```

3f. Add the `<select>` as the last child inside the card's outer `<div>` (just before its closing `</div>`, after the `v.entretien` block):

```tsx
      <select
        title="Type objectif"
        value={current}
        onChange={(e) => updateMutation.mutate({ id: v.id, patch: { type_objectif: e.target.value || null } })}
        className="mt-1 w-full rounded border border-[var(--border)] bg-[var(--card)] px-1.5 py-1 text-[10px]"
      >
        <option value="">— Type objectif —</option>
        {opts.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/components/inventaire-type-objectif.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 5: Typecheck + regression**

Run: `npx tsc --noEmit`
Expected: no new errors.

Run: `npx vitest run __tests__/components/objectif-tab.test.tsx __tests__/queries/garderobe.test.tsx`
Expected: still green (no regression in the garde-robe front tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/components/garderobe/InventaireTab.tsx frontend/__tests__/components/inventaire-type-objectif.test.tsx
git commit -m "feat(garderobe): sélecteur type objectif sur les cartes Inventaire (rattachement pièce->type)"
```

(Never `git add -A`/`git add .` — the working tree carries thousands of unrelated pre-existing modifications.)

---

## Self-Review

**1. Spec coverage**
- Sélecteur sur chaque carte Inventaire → Step 3f. ✓
- Options = `useObjectif().types[].nom` (réutilisé, pas de nouvel endpoint) → Step 3b. ✓
- `value = v.type_objectif ?? ""` ; option vide → `null` → Step 3e/3f + tests. ✓
- Orphelin préservé comme option sélectionnée → `opts` en Step 3e. ✓
- PATCH via `useUpdateVetement` (invalide `["garderobe"]`, rafraîchit Objectif) → Step 3e/3f. ✓
- Test composant (valeur courante + PATCH au changement + null sur vide) → Step 1. ✓
- Frontend only, aucun backend → confirmé. ✓

**2. Placeholder scan** : aucun TODO/placeholder ; tout le code est complet.

**3. Type consistency** : `useUpdateVetement().mutate({ id, patch })` correspond à la signature réelle (`{ id: string; patch: VetementUpdate }`, et `VetementUpdate` inclut `type_objectif?: string | null`). `useObjectif().data?.types[].nom` correspond au type `ObjectifResponse`. `typeNames: string[]` cohérent entre `InventaireTab` (produit) et `VetementCard` (consomme).
