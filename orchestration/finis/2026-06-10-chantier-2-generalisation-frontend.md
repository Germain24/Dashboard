# Chantier 2 — Généralisation frontend : Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chaque module frontend a sa couche `lib/queries/<module>.ts` (TanStack Query), une error boundary sur sa page, des tests vitest, et plus aucun composant > 400 lignes.

**Architecture:** Même schéma que la référence finance : le client bas niveau `lib/<module>.ts` est conservé tel quel ; `lib/queries/<module>.ts` ajoute clés de cache centralisées + hooks `useQuery`/`useMutation` avec invalidation ; les composants remplacent leurs `useEffect`+`useState` de chargement par les hooks. La page du module enveloppe son contenu dans `<ErrorBoundary label="…">` (modèle : `src/app/finance/page.tsx`).

**Tech Stack:** TanStack Query v5 (QueryProvider global déjà en place), vitest + jsdom + @testing-library/react (config existante : `vitest.config.ts`, alias `@`), Testing Library jest-dom.

**Suivi :** 1 module = 1 item W (#518–#533) = 1 commit, marqué `← FINIS ✓ (date)` dans `orchestration/AMELIORATIONS_200.txt`.

**Commandes (depuis `frontend/`)** : `npm test` (vitest run), `npx tsc --noEmit` (typecheck rapide). Build complet `npm run build` (avec `NEXT_PUBLIC_API_BASE_URL` défini) une fois en clôture, pas à chaque commit.

---

### Task 1: Module de référence — habitudes (#525)

**Files:**
- Create: `frontend/lib/queries/habitudes.ts`
- Create: `frontend/__tests__/queries/habitudes.test.tsx`
- Modify: `frontend/components/habitudes/AujourdhuiTab.tsx`, `GestionTab.tsx`, `HeatmapTab.tsx`, `MoisTab.tsx` (remplacer useEffect+fetch par hooks)
- Modify: `frontend/src/app/habitudes/page.tsx` (ErrorBoundary)

- [ ] **Step 1: Test rouge — hooks de requête + invalidation après mutation**

```tsx
// frontend/__tests__/queries/habitudes.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/habitudes", () => ({
  fetchHabits: vi.fn().mockResolvedValue([{ id: 1, nom: "Lecture" }]),
  fetchStreaks: vi.fn().mockResolvedValue([]),
  checkEntry: vi.fn().mockResolvedValue({ id: 9 }),
}));

import { useHabits, useCheckEntry, habitudesKeys } from "@/lib/queries/habitudes";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("queries/habitudes", () => {
  it("useHabits charge la liste via lib/habitudes", async () => {
    const { result } = renderHook(() => useHabits(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, nom: "Lecture" }]);
  });

  it("les clés de cache sont stables et préfixées par module", () => {
    expect(habitudesKeys.all).toEqual(["habitudes"]);
    expect(habitudesKeys.habits()).toEqual(["habitudes", "habits"]);
  });

  it("useCheckEntry déclenche la mutation", async () => {
    const { result } = renderHook(() => useCheckEntry(), { wrapper });
    result.current.mutate({ habit_id: 1, date: "2026-06-10", valeur: 1 });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
```

- [ ] **Step 2: Vérifier l'échec** — `npm test -- __tests__/queries/habitudes.test.tsx` → FAIL (`Cannot find module '@/lib/queries/habitudes'`).

- [ ] **Step 3: Implémenter `lib/queries/habitudes.ts`**

```tsx
"use client";

/** Couche TanStack Query du module Habitudes (#525) — modèle : lib/queries/finance.ts. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveHabit, checkEntry, createHabit, deleteEntry,
  fetchGamification, fetchHabits, fetchHeatmap, fetchStats,
  fetchStreaks, fetchToday, updateHabit, type Habit,
} from "@/lib/habitudes";

export const habitudesKeys = {
  all: ["habitudes"] as const,
  habits: () => [...habitudesKeys.all, "habits"] as const,
  today: () => [...habitudesKeys.all, "today"] as const,
  streaks: () => [...habitudesKeys.all, "streaks"] as const,
  gamification: () => [...habitudesKeys.all, "gamification"] as const,
  stats: () => [...habitudesKeys.all, "stats"] as const,
  heatmap: (habitId: number, year: number) =>
    [...habitudesKeys.all, "heatmap", habitId, year] as const,
};

export function useHabits() {
  return useQuery({ queryKey: habitudesKeys.habits(), queryFn: fetchHabits });
}
export function useToday() {
  return useQuery({ queryKey: habitudesKeys.today(), queryFn: fetchToday });
}
export function useStreaks() {
  return useQuery({ queryKey: habitudesKeys.streaks(), queryFn: fetchStreaks });
}
export function useGamification() {
  return useQuery({ queryKey: habitudesKeys.gamification(), queryFn: fetchGamification });
}
export function useHabitudesStats() {
  return useQuery({ queryKey: habitudesKeys.stats(), queryFn: fetchStats });
}
export function useHeatmap(habitId: number | null, year: number) {
  return useQuery({
    queryKey: habitudesKeys.heatmap(habitId ?? 0, year),
    queryFn: () => fetchHeatmap(habitId as number, year),
    enabled: habitId != null,
  });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: habitudesKeys.all });
}

export function useCheckEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { habit_id: number; date: string; valeur?: number }) =>
      checkEntry(p.habit_id, p.date, p.valeur ?? 1),
    onSuccess: invalidate,
  });
}
export function useDeleteEntry() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => deleteEntry(id), onSuccess: invalidate });
}
export function useCreateHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: createHabit, onSuccess: invalidate });
}
export function useUpdateHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<Habit> }) => updateHabit(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useArchiveHabit() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => archiveHabit(id), onSuccess: invalidate });
}
```

- [ ] **Step 4: Vert** — `npm test -- __tests__/queries/habitudes.test.tsx` → PASS.

- [ ] **Step 5: Migrer les composants** — dans chaque Tab, remplacer le couple `useState`+`useEffect(load)` par les hooks (ex. `const { data: habits = [] } = useHabits()`), et les appels de mutation par `useCheckEntry().mutate(...)` etc. Supprimer les `load()` manuels : l'invalidation TanStack rafraîchit. Garder l'UI identique.

- [ ] **Step 6: ErrorBoundary sur la page** — envelopper le contenu de `src/app/habitudes/page.tsx` :

```tsx
import { ErrorBoundary } from "@/components/ErrorBoundary";
// … dans le render :
<ErrorBoundary label="Habitudes">{/* contenu existant */}</ErrorBoundary>
```

- [ ] **Step 7: Vérifier** — `npm test` (suite complète) + `npx tsc --noEmit` → PASS, 0 erreur.

- [ ] **Step 8: Marquage + commit**

```powershell
git add frontend/lib/queries/habitudes.ts frontend/__tests__/queries frontend/components/habitudes frontend/src/app/habitudes orchestration/AMELIORATIONS_200.txt
git commit -m "feat(habitudes): #525 lib/queries/habitudes.ts (TanStack) + error boundary + tests"
```

---

### Tasks 2–14: Modules restants — même recette instanciée

Un commit par module. Pour CHAQUE ligne du tableau, dérouler les Steps 1–8 de la Task 1 en remplaçant `habitudes` (clés `<module>Keys`, hooks nommés d'après les fonctions du client bas niveau existant `lib/<module>.ts`) :

| Task | Item | Client bas niveau | Composants | Découpe incluse |
|------|------|-------------------|------------|-----------------|
| 2 | #518 | `lib/agenda.ts` | `components/agenda/*` | — |
| 3 | #519 | `lib/budget.ts` | `components/budget/*` | `MoisTab.tsx` (377 l.) → extraire sous-composants |
| 4 | #520 | `lib/cuisine.ts` | `components/cuisine/*` | `RecettesTab.tsx` (558 l.) → extraire `RecetteCard`, `RecetteDetailModal` |
| 5 | #521 | `lib/data.ts` | `src/app/donnees/page.tsx` | — |
| 6 | #522 | `lib/entrainement.ts` | `components/entrainement/*` | `AujourdhuiTab.tsx` (421 l.) → extraire `SlotCard`, `SeanceEnCours` |
| 7 | #523 | `lib/etudes.ts` | `components/etudes/*` | — |
| 8 | #524 | `lib/garderobe.ts` | `components/garderobe/*` | — |
| 9 | #526 | `lib/jobs.ts` + `lib/notifications.ts` | `src/app/jobs/page.tsx`, `components/layout/*` | — |
| 10 | #527 | `lib/journal.ts` | `components/journal/*` | — |
| 11 | #528 | `lib/livres.ts` | `components/livres/*` | — |
| 12 | #529 | `lib/musique.ts` | `components/musique/*` | — |
| 13 | #530 | `lib/sante.ts` | `components/sante/*` | — |
| 14 | #531 | `lib/skincare.ts` | `components/skincare/*` | — |

Règles d'instanciation (appliquées à chaque module) :

- **Step 1 (test rouge)** : même squelette que `__tests__/queries/habitudes.test.tsx` — mocker `@/lib/<module>` avec `vi.mock`, tester 1 hook de lecture (succès + data), la stabilité des clés, et 1 mutation si le module en a.
- **Step 3 (implémentation)** : un hook par fonction exportée du client bas niveau réellement consommée par les composants (vérifier par `Select-String -Path frontend/components/<module> -Pattern 'from .@/lib/<module>'`). Ne PAS créer de hooks pour des fonctions que personne n'appelle (YAGNI).
- **Step 5 (migration)** : seuls les chargements de données passent aux hooks ; l'état purement UI (onglet actif, modal ouverte) reste en `useState`.
- **Découpe** (#519, #520, #522) : extraire les sous-composants dans `components/<module>/<Nom>.tsx`, props typées, sans changer le rendu. Le fichier hôte doit passer sous 400 lignes.
- **ErrorBoundary** : si la page rend plusieurs onglets, une seule boundary au niveau page suffit.
- **Step 7** : `npm test` + `npx tsc --noEmit` verts avant commit.
- Si un module n'a PAS de client bas niveau dans `lib/` (composants qui fetch en direct), créer d'abord `lib/<module>.ts` sur le modèle de `lib/habitudes.ts` (fonctions nommées, types exportés), puis dérouler la recette.

---

### Task 15: Découpe BuffettTab (#532)

**Files:**
- Modify: `frontend/components/finance/BuffettTab.tsx` (391 l.)
- Create: sous-composants extraits dans `frontend/components/finance/`

- [ ] **Step 1:** Lire le fichier, identifier 2–3 blocs cohérents (ex. tableau de runs, panneau de détail, formulaire de lancement) et les extraire en composants propres avec props typées.
- [ ] **Step 2:** `npm test` + `npx tsc --noEmit` → PASS. Fichier hôte < 400 lignes.
- [ ] **Step 3:** Marquage #532 + commit `refactor(finance): #532 decoupe BuffettTab en sous-composants`.

### Task 16: Sweep final des appels directs (#533)

- [ ] **Step 1:** `Select-String -Path frontend/components -Pattern 'fetch\(' -Recurse` et `-Pattern "from .@/lib/(?!queries)"` — inventorier les composants qui contournent encore lib/queries.
- [ ] **Step 2:** Migrer les retardataires vers les hooks (ou documenter pourquoi ils restent : upload de fichier, EventSource, etc.).
- [ ] **Step 3:** Build complet — `$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'; npm run build` → succès.
- [ ] **Step 4:** Marquage #533 + commit + passage au plan du Chantier 3.
