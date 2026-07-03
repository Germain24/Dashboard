# Passe de conformité Verre Clair — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Appliquer également le design system Verre Clair sur les 29 segments (palette par tokens, typo, fondus non cumulés, cascades motion, chargement sans flash de header, densité) — spec : `orchestration/a-faire/2026-07-03-conformite-verre-clair-design.md`.

**Architecture:** Lot 0 livre les primitives (`lib/design/colors.ts`, `ui/collapsible-section.tsx`) et la garde CI (`conformity.test.ts`, whitelist nominative pleine). Les lots 1-5 appliquent la checklist par catégorie du Deck et VIDENT la whitelist de leurs fichiers. Le lot 6 supprime le CSS `.stagger`, active l'interdiction stagger, asserte la whitelist vide et marque improvements.md.

**Tech Stack:** Next.js 15 + Tailwind v4, motion/react (`lib/motion`), vitest + @testing-library/react, git grep (gardes).

## Global Constraints

- Commandes depuis `frontend/` : `npx vitest run <chemins>`, `npx tsc --noEmit`.
- Palette DESIGN.md uniquement ; les hex ne vivent QUE dans `frontend/lib/design/colors.ts` (+ globals.css).
- Aucun changement d'API ui/, aucune nouvelle dépendance, aucun changement de logique métier ni de queries.
- `prefers-reduced-motion` respecté (`useReducedMotion` ou neutralisation globale existante).
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`).
- Commits : terminer par `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## Patterns de transformation (référencés par les lots 1-5)

**A. Couleur sémantique** — un état (succès/alerte/danger/info) codé en dur passe au token :
```tsx
// AVANT                                   // APRÈS
className="text-[#16a34a]"                 className="text-[var(--success)]"
className="bg-[#fee2e2] text-[#991b1b]"    className="bg-[var(--destructive-muted)] text-[var(--destructive-foreground)]"
```

**B. Couleur de chart/donnée** — recharts/SVG exigent des couleurs concrètes → import central :
```tsx
import { CHART_SERIES, INK } from "@/lib/design/colors";
// séries: <Cell fill={CHART_SERIES[i % CHART_SERIES.length]} />
// courbe unique: stroke={INK.navy}
```
JAMAIS `INK` pour du texte/surface UI (ne suit pas le thème sombre) — tokens CSS seulement.

**C. Fondu racine de page** — le wrapper racine d'un module ne porte plus `animate-fade-in` (PageTransition anime déjà l'entrée). LÉGITIMES et conservés : `animate-fade-in-up` sur le contenu keyé d'un CHANGEMENT D'ONGLET, et les `animate-fade-in` des `loading.tsx` :
```tsx
// AVANT                                   // APRÈS
<div className="space-y-0 animate-fade-in">   <div className="space-y-0">
```

**D. Migration `.stagger`** — la cascade CSS devient déclarative :
```tsx
// AVANT
<div className="grid gap-3 sm:grid-cols-3 stagger">
  {items.map((it) => <Card key={it.id} className="animate-fade-in-up">…</Card>)}
</div>
// APRÈS
import { StaggerGroup, StaggerItem } from "@/lib/motion/Stagger";
<StaggerGroup className="grid gap-3 sm:grid-cols-3">
  {items.map((it) => <StaggerItem key={it.id}><Card>…</Card></StaggerItem>)}
</StaggerGroup>
```
(retirer `animate-fade-in-up` des enfants — `StaggerItem` porte l'entrée ; les classes de placement grid vont sur `StaggerItem`).

**E. Chargement sans flash de header** — l'early-return plein écran devient un fallback de contenu :
```tsx
// AVANT
if (xQ.isLoading) return <PageSkeleton />;
return (<div className="space-y-0"><ModuleHeader … />{contenu}</div>);
// APRÈS — le header ne disparaît jamais
return (
  <div className="space-y-0">
    <ModuleHeader … />
    {xQ.isLoading ? (
      <div className="p-6 space-y-6"><SkeletonStatRow count={3} /><SkeletonCardGrid count={6} cols={3} /></div>
    ) : (
      {contenu}
    )}
  </div>
);
```
(adapter les blocs skeleton à la géométrie du module — mêmes exports `@/components/ui/skeleton` que les loading.tsx).

**F. Typo/espacements (manuel)** — display réservé h1/`font-display` ; titres de cartes `text-sm font-semibold` ; chiffres financiers `font-mono tabular-nums` ; contenu `p-6`, grilles `gap-3`/`gap-4`, sections `space-y-6`. Corriger les écarts FLAGRANTS seulement.

---

### Task 0: Primitives + garde de conformité

**Files:**
- Create: `frontend/lib/design/colors.ts`
- Create: `frontend/components/ui/collapsible-section.tsx`
- Test: `frontend/__tests__/design/conformity.test.ts` (créer)
- Test: `frontend/__tests__/components/collapsible-section.test.tsx` (créer)

**Interfaces:**
- Consumes: `cn` (`@/lib/utils`), `springs`, `durations`, `EASE_OUT` (`@/lib/motion/tokens`), `motion/react`.
- Produces:
  - `INK: { navy; brass; green; oxblood; slate; ochre; vermilion }` (hex strings)
  - `CHART_SERIES: string[]` (7 couleurs, ordre contrasté)
  - `CollapsibleSection({ title: string; defaultOpen?: boolean; children: React.ReactNode; className?: string })`
  - Garde `conformity.test.ts` avec `HEX_WHITELIST` que les lots 1-5 réduisent.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/__tests__/components/collapsible-section.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

describe("CollapsibleSection", () => {
  it("fermé par défaut : contenu absent, aria-expanded=false", () => {
    render(<CollapsibleSection title="Détails">contenu-caché</CollapsibleSection>);
    expect(screen.queryByText("contenu-caché")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Détails/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("defaultOpen : contenu visible", () => {
    render(<CollapsibleSection title="Détails" defaultOpen>contenu-visible</CollapsibleSection>);
    expect(screen.getByText("contenu-visible")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("clic ouvre puis ferme", () => {
    render(<CollapsibleSection title="Détails">contenu</CollapsibleSection>);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("contenu")).toBeInTheDocument();
  });

  it("aria-controls pointe la zone", () => {
    render(<CollapsibleSection title="Détails" defaultOpen>x</CollapsibleSection>);
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-controls")).toBeTruthy();
  });
});
```

```ts
// frontend/__tests__/design/conformity.test.ts
/**
 * Garde de conformité Verre Clair : les couleurs vivent dans les tokens
 * (globals.css) ou lib/design/colors.ts — jamais en dur dans les composants.
 * HEX_WHITELIST = dette connue (constat 2026-07-03), vidée lot par lot ;
 * le lot 6 l'asserte vide.
 */
import { it, expect } from "vitest";
import { execSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

export const HEX_WHITELIST = [
  "components/agenda/Agenda.tsx",
  "components/agenda/SemaineTab.tsx",
  "components/budget/charts.tsx",
  "components/budget/EnveloppesTab.tsx",
  "components/budget/MoisTab.tsx",
  "components/deck/modules/ScoreRingModule.tsx",
  "components/entrainement/AujourdhuiTab.tsx",
  "components/films/WatchlistSection.tsx",
  "components/finance/Finance.tsx",
  "components/finance/CompositionTab.tsx",
  "components/finance/PatrimoineTab.tsx",
  "components/finance/SuiviTab.tsx",
  "components/garderobe/Garderobe.tsx",
  "components/garderobe/RecommandationsTab.tsx",
  "components/habitudes/AujourdhuiTab.tsx",
  "components/habitudes/GestionTab.tsx",
  "components/livres/BibliothequeTab.tsx",
  "components/musique/Bibliotheque.tsx",
  "components/sante/TendanceTab.tsx",
];

function gitGrepFiles(pattern: string): string[] {
  try {
    const out = execSync(
      `git grep -lE "${pattern}" -- "components/*.tsx" "src/*.tsx"`,
      { cwd: frontendRoot, encoding: "utf8" },
    );
    return out.trim().split("\n").filter(Boolean).map((f) => f.replace(/\\/g, "/"));
  } catch {
    return []; // git grep sort en code 1 quand zéro correspondance
  }
}

it("aucune couleur hex/rgb hardcodée hors whitelist", () => {
  const offenders = gitGrepFiles("#[0-9a-fA-F]{6}|rgb\\([0-9]").filter(
    (f) => !HEX_WHITELIST.includes(f),
  );
  expect(offenders, `couleurs hardcodées hors whitelist:\n${offenders.join("\n")}`).toEqual([]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (depuis `frontend/`): `npx vitest run __tests__/components/collapsible-section.test.tsx __tests__/design/conformity.test.ts`
Expected: collapsible FAIL (`Cannot find module '@/components/ui/collapsible-section'`). conformity : si un fichier hors whitelist apparaît dans l'échec, l'AJOUTER à `HEX_WHITELIST` (le constat fait foi : la whitelist initiale = exactement l'état courant, la garde doit être VERTE à la fin de cette tâche).

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/lib/design/colors.ts
/**
 * Palette DESIGN.md pour les CHARTS (recharts/SVG exigent des couleurs
 * concrètes). Pour le texte et les surfaces UI : tokens CSS uniquement
 * (ces hex ne suivent pas le thème sombre).
 */
export const INK = {
  navy: "#04142c",
  brass: "#C5A059",
  green: "#536252",
  oxblood: "#501312",
  slate: "#384762",
  ochre: "#8a6d1f",
  vermilion: "#ba1a1a",
} as const;

/** Série catégorielle (ordre = contraste maximal entre voisins). */
export const CHART_SERIES: string[] = [
  INK.navy, INK.brass, INK.green, INK.oxblood, INK.slate, INK.ochre, INK.vermilion,
];
```

```tsx
// frontend/components/ui/collapsible-section.tsx
"use client";

import { useId, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { springs, durations, EASE_OUT } from "@/lib/motion/tokens";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Section repliable pour les pages denses (densité 2.6) : en-tête Title,
 * chevron à ressort, hauteur animée. Reduced-motion : bascule sèche.
 */
export function CollapsibleSection({
  title,
  defaultOpen = false,
  children,
  className,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const reduced = useReducedMotion();
  const id = useId();

  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border)]",
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-[var(--foreground)]"
      >
        {title}
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={reduced ? { duration: 0 } : springs.soft}
          aria-hidden
        >
          <ChevronDown className="h-4 w-4 text-[var(--muted-foreground)]" />
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            initial={reduced ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduced ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: durations.fast, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run __tests__/components/collapsible-section.test.tsx __tests__/design/conformity.test.ts`
Expected: PASS (4 + 1). Puis `npx vitest run` et `npx tsc --noEmit` — tout vert.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/design/colors.ts frontend/components/ui/collapsible-section.tsx frontend/__tests__/design/conformity.test.ts frontend/__tests__/components/collapsible-section.test.tsx
git commit -m "feat(design): palette charts centralisee + CollapsibleSection + garde de conformite (whitelist pleine)"
```

---

### Task 1: Lot Finance (finance, patrimoine, budget) + densité finance

**Files:**
- Modify: `frontend/components/finance/Finance.tsx`, `SuiviTab.tsx`, `CompositionTab.tsx`, `PatrimoineTab.tsx` (+ autres onglets finance si écarts F), `frontend/components/budget/charts.tsx`, `EnveloppesTab.tsx`, `MoisTab.tsx` (+ page budget), pages `src/app/{finance,patrimoine,budget}/page.tsx` si fondu racine.
- Modify: `frontend/__tests__/design/conformity.test.ts` (retirer les 7 fichiers du lot de `HEX_WHITELIST`)

**Interfaces:**
- Consumes: `INK`, `CHART_SERIES` (`@/lib/design/colors`), `StaggerGroup`/`StaggerItem` (`@/lib/motion/Stagger`), `CollapsibleSection` (`@/components/ui/collapsible-section`), blocs skeleton (`@/components/ui/skeleton`).
- Produces: modules Finance conformes ; whitelist réduite de 7 entrées.

- [ ] **Step 1: Appliquer la checklist (Patterns A-F) aux modules du lot**

Écarts CONNUS (constat 2026-07-03, à re-vérifier par grep sur le lot) :
- Couleurs hardcodées : `budget/charts.tsx` (3), `budget/EnveloppesTab.tsx` (5), `budget/MoisTab.tsx` (2), `finance/Finance.tsx` (1), `finance/CompositionTab.tsx` (2), `finance/PatrimoineTab.tsx` (2), `finance/SuiviTab.tsx` (1) → Patterns A/B.
- `.stagger` : `finance/SuiviTab.tsx`, `budget/MoisTab.tsx`, `budget/EnveloppesTab.tsx` → Pattern D.
- Fondu racine : `Finance.tsx` (`space-y-0 animate-fade-in`) → Pattern C ; vérifier patrimoine/budget pages.
- Typo/espacements : Pattern F sur chaque fichier touché.

- [ ] **Step 2: Densité 2.6 — finance**

Dans `SuiviTab.tsx` et/ou `PatrimoineTab.tsx` : envelopper les sections SECONDAIRES (ex. tableau benchmark, historique long, répartitions détaillées) dans `<CollapsibleSection title="…" defaultOpen={false}>` ; les stats/graphique principal restent hors CollapsibleSection. 2 à 4 sections maximum — la densité se réduit, la page ne devient pas un accordéon.

- [ ] **Step 3: Vider la whitelist du lot**

Dans `conformity.test.ts`, retirer de `HEX_WHITELIST` les 7 entrées finance/budget.

- [ ] **Step 4: Verify**

Run: `npx vitest run __tests__/design/ && npx vitest run && npx tsc --noEmit`
Expected: garde verte (plus aucun hex dans le lot), suite complète verte, 0 erreur TS.
Grep de contrôle : `git grep -nE "stagger" -- "components/finance/*.tsx" "components/budget/*.tsx"` → 0 usage de la classe CSS (seuls `StaggerGroup/Item` restent).

- [ ] **Step 5: Commit**

```bash
git add <fichiers du lot nominativement> frontend/__tests__/design/conformity.test.ts
git commit -m "refactor(design): conformite Verre Clair lot Finance (tokens, stagger motion, densite, fondus)"
```

---

### Task 2: Lot Corps (sante, entrainement, score, skincare, garderobe) + densité santé + fix flash header

**Files:**
- Modify: `frontend/components/sante/Sante.tsx`, `TendanceTab.tsx`, `JourTab.tsx`, `frontend/components/garderobe/Garderobe.tsx`, `InventaireTab.tsx`, `RecommandationsTab.tsx`, `frontend/components/entrainement/AujourdhuiTab.tsx` (+ score/skincare si écarts).
- Modify: `frontend/__tests__/design/conformity.test.ts` (retirer les 4 fichiers du lot)

**Interfaces:**
- Consumes: idem Task 1.
- Produces: modules Corps conformes ; header jamais masqué (Sante, Garderobe) ; whitelist réduite de 4 entrées.

- [ ] **Step 1: Fix flash header (Pattern E)**

`Sante.tsx` (early-return plein écran ~lignes 71-79) et `Garderobe.tsx` (~lignes 157-165) : ModuleHeader toujours rendu, fallback skeleton du contenu seulement (géométrie : santé = stats + grille 2 col ; garderobe = filtres + grille 4 col, cf. leurs loading.tsx).

- [ ] **Step 2: Appliquer la checklist (Patterns A-F)**

Écarts CONNUS : couleurs — `entrainement/AujourdhuiTab.tsx` (1), `garderobe/Garderobe.tsx` (1), `garderobe/RecommandationsTab.tsx` (1), `sante/TendanceTab.tsx` (1) → A/B. `.stagger` — `garderobe/InventaireTab.tsx`, `sante/JourTab.tsx`, `entrainement/AujourdhuiTab.tsx` → D. Fondus racine + typo/espacements → C/F.

- [ ] **Step 3: Densité 2.6 — santé**

Dans `JourTab.tsx` (ou la page santé la plus dense) : sections secondaires en `CollapsibleSection` (2-4 max), primaires ouvertes.

- [ ] **Step 4: Vider la whitelist du lot** (4 entrées)

- [ ] **Step 5: Verify**

Run: `npx vitest run __tests__/design/ && npx vitest run && npx tsc --noEmit` — tout vert.
Grep : plus de classe `.stagger` dans `components/{sante,garderobe,entrainement}/`.

- [ ] **Step 6: Commit**

```bash
git add <fichiers du lot nominativement> frontend/__tests__/design/conformity.test.ts
git commit -m "refactor(design): conformite Verre Clair lot Corps (fix flash header, tokens, stagger, densite sante)"
```

---

### Task 3: Lot Quotidien (cuisine, routines, agenda, habitudes)

**Files:**
- Modify: `frontend/components/agenda/Agenda.tsx`, `SemaineTab.tsx`, `frontend/components/habitudes/GestionTab.tsx`, `AujourdhuiTab.tsx` (+ cuisine/routines si écarts).
- Modify: `frontend/__tests__/design/conformity.test.ts` (retirer les 4 fichiers du lot)

**Interfaces:** idem Task 1. Produces: modules Quotidien conformes ; whitelist réduite de 4 entrées.

- [ ] **Step 1: Appliquer la checklist (Patterns A-F)**

Écarts CONNUS : couleurs — `agenda/Agenda.tsx` (1), `agenda/SemaineTab.tsx` (1), `habitudes/GestionTab.tsx` (1), `habitudes/AujourdhuiTab.tsx` (1). `.stagger` — `habitudes/AujourdhuiTab.tsx`. Fondu racine — `Agenda.tsx` (2 occurrences `animate-fade-in*` dont la racine ; l'occurrence tab keyée reste). `src/app/cuisine/page.tsx` : fondu racine à vérifier. Vérifier au passage que routines/cuisine ne masquent pas leur header pendant chargement (Pattern E si besoin).

- [ ] **Step 2: Vider la whitelist du lot** (4 entrées)

- [ ] **Step 3: Verify** — `npx vitest run __tests__/design/ && npx vitest run && npx tsc --noEmit` ; grep `.stagger` sur le lot = 0.

- [ ] **Step 4: Commit**

```bash
git add <fichiers du lot nominativement> frontend/__tests__/design/conformity.test.ts
git commit -m "refactor(design): conformite Verre Clair lot Quotidien (tokens, stagger, fondus)"
```

---

### Task 4: Lot Savoir (etudes, travail, jobs, langues, documents, livres)

**Files:**
- Modify: `frontend/components/livres/BibliothequeTab.tsx` (+ autres modules du lot si écarts), `src/app/documents/page.tsx` (fondu racine constaté).
- Modify: `frontend/__tests__/design/conformity.test.ts` (retirer 1 entrée)

**Interfaces:** idem Task 1. Produces: modules Savoir conformes ; whitelist réduite de 1 entrée ; DERNIER usage `.stagger` migré.

- [ ] **Step 1: Appliquer la checklist (Patterns A-F)**

Écarts CONNUS : couleurs — `livres/BibliothequeTab.tsx` (2). `.stagger` — `livres/BibliothequeTab.tsx` (dernier usage restant du repo). Fondus racine — `src/app/documents/page.tsx`, `src/app/bilan/page.tsx` est au lot 5. Typo/espacements F sur les modules du lot (etudes, travail, jobs, langues rapides — peu d'écarts constatés).

- [ ] **Step 2: Vider la whitelist** (1 entrée)

- [ ] **Step 3: Verify** — gardes + suite + tsc verts ; `git grep -nE '["'"'"' ]stagger["'"'"' ]' -- "components/*.tsx" "src/*.tsx"` → 0 (plus AUCUN usage de la classe dans le repo).

- [ ] **Step 4: Commit**

```bash
git add <fichiers du lot nominativement> frontend/__tests__/design/conformity.test.ts
git commit -m "refactor(design): conformite Verre Clair lot Savoir (tokens, dernier stagger migre)"
```

---

### Task 5: Lot Loisirs + transverse (musique, film, series, gaming, voyage, journal, vue-360, bilan, snapshot, objectifs, parametres, donnees, deck)

**Files:**
- Modify: `frontend/components/musique/Bibliotheque.tsx`, `frontend/components/films/WatchlistSection.tsx`, `frontend/components/deck/modules/ScoreRingModule.tsx`, pages `src/app/{vue-360,bilan,snapshot,film}/page.tsx` (fondus racine constatés) + autres modules du lot si écarts.
- Modify: `frontend/__tests__/design/conformity.test.ts` (retirer les 3 dernières entrées)

**Interfaces:** idem Task 1. Produces: tout le repo conforme ; `HEX_WHITELIST` réduite à `[]` de fait (le lot 6 l'asserte).

- [ ] **Step 1: Appliquer la checklist (Patterns A-F)**

Écarts CONNUS : couleurs — `musique/Bibliotheque.tsx` (1), `films/WatchlistSection.tsx` (2), `deck/modules/ScoreRingModule.tsx` (2, SVG → Pattern B avec `INK`). Fondus racine — `vue-360`, `bilan`, `snapshot`, `film` pages. Typo/espacements F sur les modules du lot.

- [ ] **Step 2: Vider la whitelist** (3 dernières entrées → tableau vide `[]`)

- [ ] **Step 3: Verify** — gardes + suite + tsc verts.

- [ ] **Step 4: Commit**

```bash
git add <fichiers du lot nominativement> frontend/__tests__/design/conformity.test.ts
git commit -m "refactor(design): conformite Verre Clair lot Loisirs+transverse (whitelist videe)"
```

---

### Task 6: Clôture — suppression CSS .stagger, gardes définitives, marquages

**Files:**
- Modify: `frontend/src/app/globals.css` (supprimer le bloc `.stagger` déprécié, lignes ~397-405 : le commentaire + les 6 règles nth-child)
- Modify: `frontend/__tests__/design/conformity.test.ts` (ajouter l'interdiction stagger + asserter la whitelist vide)
- Modify: `orchestration/en-cours/improvements.md`
- Move: `orchestration/a-faire/2026-07-03-conformite-verre-clair-design.md` et `…-conformite-verre-clair.md` → `orchestration/finis/` (via `git mv`, depuis l'emplacement RÉEL au moment de la tâche — `en-cours/` si le contrôleur les y a déplacés au lancement)

- [ ] **Step 1: Ajouter les assertions finales à conformity.test.ts**

```ts
it("la whitelist de couleurs est vide (dette résorbée)", () => {
  expect(HEX_WHITELIST).toEqual([]);
});

it("classe CSS .stagger disparue (migrée vers StaggerGroup)", () => {
  const offenders = gitGrepFiles(`["' ]stagger["' ]`);
  expect(offenders, `usages .stagger restants:\n${offenders.join("\n")}`).toEqual([]);
});
```

(NB : le pattern `["' ]stagger["' ]` ne matche PAS `stagger-group`/`StaggerGroup` — délimiteurs exigés des deux côtés.)

- [ ] **Step 2: Supprimer le bloc CSS déprécié**

Dans `globals.css`, supprimer intégralement le bloc commençant par `/* Stagger children — DÉPRÉCIÉ … */` jusqu'à `.stagger > *:nth-child(6) { animation-delay: 250ms; }` inclus.

- [ ] **Step 3: Verify**

Run: `npx vitest run __tests__/design/ && npx vitest run && npx tsc --noEmit` — tout vert (les 2 nouvelles assertions passent).

- [ ] **Step 4: Marquer improvements.md**

- `2.1` : `← FINIS ✓ (<date du jour>) passe par lots de catégorie, garde conformity.test.ts (0 hex hors lib/design/colors.ts)`
- `2.6` : `← FINIS ✓ (<date du jour>) CollapsibleSection (ui/) sur finance + santé`
- `1.3` : remplacer la ligne `← PARTIEL …` par `← FINIS ✓ (<date du jour>) 8 usages CSS migrés StaggerGroup/Item, bloc .stagger supprimé de globals.css`
- `1.6` : compléter la ligne PARTIEL existante avec `; header jamais masqué pendant chargement (Sante/Garderobe) (<date du jour>)`

- [ ] **Step 5: Déplacer spec + plan vers finis/ et commit**

```bash
git mv orchestration/en-cours/2026-07-03-conformite-verre-clair-design.md orchestration/finis/
git mv orchestration/en-cours/2026-07-03-conformite-verre-clair.md orchestration/finis/
git add frontend/src/app/globals.css frontend/__tests__/design/conformity.test.ts orchestration/en-cours/improvements.md
git commit -m "feat(design): cloture conformite Verre Clair — CSS .stagger supprime, gardes definitives, marquages"
```

---

## Self-Review

**1. Spec coverage**
- Checklist §1 (6 points) → Patterns A-F appliqués dans chaque lot (Tasks 1-5). ✓
- `colors.ts` (§2) → Task 0 (INK + CHART_SERIES, avertissement thème sombre). ✓
- Garde (§3 : hex interdit hors whitelist nominative, vidée lot par lot, stagger interdit, whitelist vide assertée au final) → Tasks 0 (whitelist pleine), 1-5 (réduction), 6 (assertions finales). ✓
- `CollapsibleSection` (§4) → Task 0 ; appliquée finance (Task 1 Step 2) et santé (Task 2 Step 3) UNIQUEMENT. ✓
- Fix flash header (§5, Sante+Garderobe, queries inchangées) → Task 2 Step 1 (Pattern E) ; vigilance sur les autres modules dans chaque lot. ✓
- Lots (§6, tableau) → Tasks 0-6, mêmes périmètres. ✓
- Clôture (marquage 2.1/2.6/1.3/1.6, docs → finis/) → Task 6. ✓

**2. Placeholder scan** : les Patterns A-F contiennent le code de transformation complet ; les lots listent leurs fichiers et écarts CONNUS avec re-vérification par grep (le constat exact au moment de l'exécution fait foi — c'est une passe de conformité, pas une réécriture spécifiée ligne à ligne). Aucun TBD.

**3. Type consistency**
- `INK`/`CHART_SERIES` : définis Task 0, consommés Patterns B (Tasks 1-5). ✓
- `CollapsibleSection({ title, defaultOpen?, children, className? })` : définie Task 0, consommée Tasks 1-2 avec les mêmes props. ✓
- `HEX_WHITELIST` exporté Task 0 ; Tasks 1-5 le réduisent ; Task 6 l'asserte `[]` — même symbole, même fichier. ✓
- `gitGrepFiles` définie Task 0, réutilisée par les assertions Task 6 (même fichier). ✓
- `StaggerGroup`/`StaggerItem` : import `@/lib/motion/Stagger` (chemin réel vérifié). ✓
