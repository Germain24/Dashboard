# P0 — Navigation fluide (transitions & micro-interactions) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Éliminer l'effet « PowerPoint » (fadeIn CSS rejoué à chaque navigation) et généraliser les animations `motion/react` déjà amorcées dans le deck à toute l'application.

**Architecture:** Un `MotionConfig reducedMotion="user"` global + un `PageTransition` client keyé sur le **module** (1er segment d'URL) remplacent `template.tsx` (qui remontait un fade à CHAQUE navigation). Les primitives `ui/` (tabs, dialog, stat-card) passent aux springs des tokens existants (`lib/motion/tokens.ts`). Nouvelles primitives `StaggerGroup`/`StaggerItem` pour les entrées en cascade opt-in.

**Tech Stack:** Next.js 15 App Router, `motion` v12 (`motion/react`), Vitest + Testing Library (jsdom), Tailwind v4 (tokens CSS dans `src/app/globals.css`).

## Global Constraints

- Réutiliser `lib/motion/tokens.ts` (`springs`, `durations`, `EASE_OUT`) — ne JAMAIS créer de nouvelles constantes de durée/spring dans les composants.
- Contrainte documentée dans `globals.css:394-396` : le wrapper de page n'anime **que l'opacité** — un `transform` persistant créerait un bloc conteneur et casserait les `position: fixed` des enfants (rail de points du Deck).
- `prefers-reduced-motion` respecté partout : `MotionConfig reducedMotion="user"` (neutralise les transforms) + `useReducedMotion()` quand on veut désactiver aussi les fondus.
- Libellés et commentaires en français (fr-CA). Style commits : `feat(scope): …` minuscule.
- Chemins : composants dans `frontend/components/`, motion dans `frontend/lib/motion/`, app router dans `frontend/src/app/`, tests dans `frontend/__tests__/`. Alias `@/` = racine `frontend/`.
- Toutes les commandes se lancent depuis `frontend/` : `npm run test -- <fichier>` (vitest run), `npm run lint`, `npm run build`.

---

### Task 1: MotionProvider global + PageTransition par module (remplace template.tsx)

**Files:**
- Create: `frontend/lib/motion/MotionProvider.tsx`
- Create: `frontend/lib/motion/PageTransition.tsx`
- Test: `frontend/__tests__/motion/PageTransition.test.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Delete: `frontend/src/app/template.tsx`
- Modify: `frontend/src/app/globals.css` (retirer `.page-transition`)

**Interfaces:**
- Consumes: `durations`, `EASE_OUT` depuis `@/lib/motion/tokens` (existant).
- Produces: `<MotionProvider>{children}</MotionProvider>` (client, `MotionConfig reducedMotion="user"`) et `<PageTransition>{children}</PageTransition>` (client ; wrapper `data-segment="/<module>"`, fondu d'opacité rejoué uniquement quand le 1er segment d'URL change).

- [ ] **Step 1: Écrire le test qui échoue**

```tsx
// frontend/__tests__/motion/PageTransition.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageTransition } from '@/lib/motion/PageTransition'

const mockPathname = vi.fn<() => string>()
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
}))

describe('PageTransition', () => {
  beforeEach(() => mockPathname.mockReset())

  it('rend les enfants', () => {
    mockPathname.mockReturnValue('/finance')
    render(<PageTransition><p>Contenu</p></PageTransition>)
    expect(screen.getByText('Contenu')).toBeInTheDocument()
  })

  it('expose le module courant (1er segment) comme clé de transition', () => {
    mockPathname.mockReturnValue('/finance/transactions')
    render(<PageTransition><p>A</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe('/finance')
  })

  it('garde la même clé pour une navigation intra-module', () => {
    mockPathname.mockReturnValue('/finance')
    const { rerender } = render(<PageTransition><p>A</p></PageTransition>)
    const first = screen.getByTestId('page-transition').dataset.segment
    mockPathname.mockReturnValue('/finance/transactions')
    rerender(<PageTransition><p>B</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe(first)
  })

  it('change de clé quand on change de module', () => {
    mockPathname.mockReturnValue('/finance')
    const { rerender } = render(<PageTransition><p>A</p></PageTransition>)
    mockPathname.mockReturnValue('/garderobe')
    rerender(<PageTransition><p>B</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe('/garderobe')
  })
})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `npm run test -- __tests__/motion/PageTransition.test.tsx`
Expected: FAIL — « Failed to resolve import "@/lib/motion/PageTransition" »

- [ ] **Step 3: Implémenter**

```tsx
// frontend/lib/motion/MotionProvider.tsx
'use client'

/**
 * Configuration Motion globale : `reducedMotion="user"` neutralise les
 * transforms (translate/scale) quand l'OS demande moins de mouvement,
 * en ne laissant que les fondus d'opacité. Posé une fois dans le layout.
 */

import { MotionConfig } from 'motion/react'

export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
```

```tsx
// frontend/lib/motion/PageTransition.tsx
'use client'

/**
 * Transition d'entrée de page, keyée sur le MODULE (1er segment d'URL) :
 * naviguer à l'intérieur d'un module ne rejoue rien (fini le « flash »
 * à chaque clic), changer de module rejoue un fondu court.
 * Opacité seule : un transform persistant créerait un bloc conteneur et
 * casserait les `position: fixed` des enfants (rail de points du Deck).
 * Remplace src/app/template.tsx (qui remontait à CHAQUE navigation).
 */

import { usePathname } from 'next/navigation'
import { motion, useReducedMotion } from 'motion/react'
import { durations, EASE_OUT } from './tokens'

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const reduced = useReducedMotion()
  const segment = '/' + (pathname.split('/')[1] ?? '')

  if (reduced) {
    return (
      <div data-testid="page-transition" data-segment={segment}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      key={segment}
      data-testid="page-transition"
      data-segment={segment}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: durations.fast, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  )
}
```

Dans `frontend/src/app/layout.tsx` :
- ajouter les imports `import { MotionProvider } from "@/lib/motion/MotionProvider";` et `import { PageTransition } from "@/lib/motion/PageTransition";`
- envelopper le contenu de `<QueryProvider>` avec `<MotionProvider>` (juste à l'intérieur), et `{children}` avec `<PageTransition>` :

```tsx
<QueryProvider>
  <MotionProvider>
    {/* Palette de commandes globale (Cmd/Ctrl+K) + raccourcis j/k */}
    <CommandPalette />
    <KeyboardShortcuts />
    <ShortcutsHelp />

    {/* Navigation mobile (fixed header + hamburger drawer) */}
    <MobileNav />

    {/* Dock flottant en verre (remplace la sidebar desktop). */}
    <Dock />

    {/* Contenu : l'accueil est le Deck plein écran ; les pages module
        défilent normalement avec une garde basse pour le Dock. */}
    <div className="flex min-h-screen">
      <MainShell>
        <Breadcrumbs />
        <PageTransition>{children}</PageTransition>
      </MainShell>
    </div>
  </MotionProvider>
</QueryProvider>
```

- supprimer `frontend/src/app/template.tsx`
- dans `frontend/src/app/globals.css`, supprimer la règle `.page-transition { … }` (ligne ~397) et son commentaire (lignes ~394-396). Garder `fadeIn` (encore utilisé par `.animate-fade-in`).

- [ ] **Step 4: Vérifier que les tests passent**

Run: `npm run test -- __tests__/motion/PageTransition.test.tsx`
Expected: 4 PASS

- [ ] **Step 5: Vérifier qu'il ne reste aucune référence**

Run: `grep -rn "page-transition" src components lib e2e __tests__` (depuis `frontend/`)
Expected: aucun résultat. Puis `npm run lint` → OK (warnings préexistants tolérés, zéro nouvelle erreur).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/motion/MotionProvider.tsx frontend/lib/motion/PageTransition.tsx frontend/__tests__/motion/PageTransition.test.tsx frontend/src/app/layout.tsx frontend/src/app/globals.css
git rm frontend/src/app/template.tsx
git commit -m "feat(navigation): transition de page par module via motion (fini le flash à chaque clic)"
```

---

### Task 2: Tabs — pastille active animée (layoutId) + entrée douce des panneaux

**Files:**
- Modify: `frontend/components/ui/tabs.tsx`
- Test: `frontend/__tests__/components/tabs.test.tsx` (nouveau)

**Interfaces:**
- Consumes: `springs` depuis `@/lib/motion/tokens` ; API `Tabs/TabsList/TabsTrigger/TabsContent` INCHANGÉE (aucun appelant à modifier).
- Produces: la pastille active est un `motion.span layoutId` partagé par groupe de tabs (`data-testid="tab-pill"`) qui GLISSE d'un onglet à l'autre ; les panneaux entrent en fondu + 4 px.

- [ ] **Step 1: Écrire le test qui échoue**

```tsx
// frontend/__tests__/components/tabs.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useState } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

function Harness() {
  const [tab, setTab] = useState('un')
  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="un">Un</TabsTrigger>
        <TabsTrigger value="deux">Deux</TabsTrigger>
      </TabsList>
      <TabsContent value="un">Panneau un</TabsContent>
      <TabsContent value="deux">Panneau deux</TabsContent>
    </Tabs>
  )
}

describe('Tabs — pastille animée', () => {
  it("rend la pastille dans l'onglet actif uniquement", () => {
    render(<Harness />)
    const active = screen.getByRole('tab', { name: 'Un' })
    const inactive = screen.getByRole('tab', { name: 'Deux' })
    expect(active.querySelector('[data-testid="tab-pill"]')).not.toBeNull()
    expect(inactive.querySelector('[data-testid="tab-pill"]')).toBeNull()
  })

  it("déplace la pastille vers l'onglet cliqué", () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('tab', { name: 'Deux' }))
    expect(
      screen.getByRole('tab', { name: 'Deux' }).querySelector('[data-testid="tab-pill"]'),
    ).not.toBeNull()
    expect(screen.getByText('Panneau deux')).toBeInTheDocument()
  })

  it('conserve la navigation clavier (flèches)', () => {
    render(<Harness />)
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Un' }), { key: 'ArrowRight' })
    expect(
      screen.getByRole('tab', { name: 'Deux' }).querySelector('[data-testid="tab-pill"]'),
    ).not.toBeNull()
  })
})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `npm run test -- __tests__/components/tabs.test.tsx`
Expected: FAIL — `tab-pill` introuvable (3 échecs).

- [ ] **Step 3: Implémenter**

Dans `frontend/components/ui/tabs.tsx` :
- ajouter `import { motion } from "motion/react";` et `import { springs } from "@/lib/motion/tokens";`
- remplacer le `return` de `TabsTrigger` (l'actif garde la couleur via CSS, le fond devient une pastille `layoutId` qui glisse) :

```tsx
  return (
    <button
      role="tab"
      id={ctx.id + "-tab-" + value}
      aria-selected={active}
      aria-controls={ctx.id + "-panel-" + value}
      tabIndex={active ? 0 : -1}
      onClick={() => ctx.onChange(value)}
      onKeyDown={handleKeyDown}
      className={cn(
        "relative shrink-0 rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm",
        "transition-[color] duration-200 ease-[var(--ease-out)]",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-1 focus-visible:rounded-[var(--radius-full)]",
        active
          ? "text-[var(--foreground)] font-medium"
          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
        className,
      )}
    >
      {active && (
        <motion.span
          layoutId={ctx.id + "-pill"}
          transition={springs.soft}
          data-testid="tab-pill"
          aria-hidden
          className="absolute inset-0 rounded-[var(--radius-full)] bg-[var(--glass-strong)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)]"
        />
      )}
      <span className="relative z-10">{children}</span>
    </button>
  );
```

- remplacer le `return` de `TabsContent` (entrée fondu + léger y ; le `y` est neutralisé sous reduced-motion par le MotionConfig global) :

```tsx
  return (
    <motion.div
      role="tabpanel"
      id={ctx.id + "-panel-" + value}
      aria-labelledby={ctx.id + "-tab-" + value}
      tabIndex={0}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springs.soft}
      className={cn("focus-visible:outline-none", className)}
    >
      {children}
    </motion.div>
  );
```

- [ ] **Step 4: Vérifier que les tests passent**

Run: `npm run test -- __tests__/components/tabs.test.tsx`
Expected: 3 PASS. Puis suite complète `npm run test` → aucun test existant cassé (les modules qui rendent des Tabs ne dépendent pas du markup interne du trigger).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/tabs.tsx frontend/__tests__/components/tabs.test.tsx
git commit -m "feat(ui): pastille d'onglet animée (layoutId) et entrée douce des panneaux"
```

---

### Task 3: Dialog — spring d'entrée et sortie propre (AnimatePresence)

**Files:**
- Modify: `frontend/components/ui/dialog.tsx`
- Test: `frontend/__tests__/components/dialog.test.tsx` (nouveau)

**Interfaces:**
- Consumes: `springs`, `durations`, `EASE_OUT` depuis `@/lib/motion/tokens` ; API `Dialog({ open, onClose, children, className })` INCHANGÉE.
- Produces: ouverture = fondu du voile + spring du panneau (scale 0.97→1) ; fermeture = animation de sortie AVANT le démontage (aujourd'hui : disparition sèche).

- [ ] **Step 1: Écrire le test qui échoue**

```tsx
// frontend/__tests__/components/dialog.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Dialog, DialogBody } from '@/components/ui/dialog'

describe('Dialog', () => {
  it('rend le contenu quand ouvert, rien quand fermé', () => {
    const { rerender } = render(
      <Dialog open onClose={() => {}}><DialogBody>Bonjour</DialogBody></Dialog>,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    rerender(<Dialog open={false} onClose={() => {}}><DialogBody>Bonjour</DialogBody></Dialog>)
    return waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('appelle onClose au clic sur le voile', () => {
    const onClose = vi.fn()
    render(<Dialog open onClose={onClose}><DialogBody>Corps</DialogBody></Dialog>)
    fireEvent.click(screen.getByTestId('dialog-backdrop'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('appelle onClose sur Échap', () => {
    const onClose = vi.fn()
    render(<Dialog open onClose={onClose}><DialogBody>Corps</DialogBody></Dialog>)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `npm run test -- __tests__/components/dialog.test.tsx`
Expected: FAIL — `dialog-backdrop` introuvable (le test 1 et 3 peuvent déjà passer ; le 2 échoue).

- [ ] **Step 3: Implémenter**

Remplacer la fonction `Dialog` de `frontend/components/ui/dialog.tsx` (les autres exports ne changent pas) et ajouter les imports `import { AnimatePresence, motion } from "motion/react";` + `import { springs, durations, EASE_OUT } from "@/lib/motion/tokens";` :

```tsx
export function Dialog({ open, onClose, children, className }: DialogProps) {
  React.useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div
          className="fixed inset-0 z-40 flex items-end sm:items-center justify-center p-4"
          role="dialog"
          aria-modal
        >
          {/* Backdrop : voile flouté, le contenu reste deviné derrière le verre */}
          <motion.div
            data-testid="dialog-backdrop"
            className="absolute inset-0 bg-black/30 backdrop-blur-[6px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: durations.fast, ease: EASE_OUT }}
            onClick={onClose}
            aria-hidden
          />
          {/* Panel : verre épais, ressort amorti sans rebond */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 4 }}
            transition={springs.soft}
            className={cn(
              "glass-modal relative z-10 w-full max-w-lg rounded-[var(--radius-lg)]",
              // On mobile: bottom sheet; sm+: centered modal
              "max-h-[90dvh] overflow-y-auto",
              className,
            )}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
```

Note : les classes CSS `animate-fade-in` / `animate-scale-in` disparaissent de ce fichier mais restent dans globals.css (encore utilisées ailleurs — vérifier avec `grep -rn "animate-scale-in" src components` avant d'envisager leur suppression ; ne PAS les supprimer dans cette tâche si utilisées).

- [ ] **Step 4: Vérifier que les tests passent**

Run: `npm run test -- __tests__/components/dialog.test.tsx`
Expected: 3 PASS. Puis `npm run test` complet → aucun test existant cassé.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/dialog.tsx frontend/__tests__/components/dialog.test.tsx
git commit -m "feat(ui): dialog en spring avec animation de sortie (AnimatePresence)"
```

---

### Task 4: StatCard — valeurs numériques en count-up (AnimatedNumber)

**Files:**
- Modify: `frontend/components/ui/stat-card.tsx`
- Test: `frontend/__tests__/components/stat-card.test.tsx` (nouveau)

**Interfaces:**
- Consumes: `AnimatedNumber` depuis `@/lib/motion/AnimatedNumber` (existant : `{ value: number; format?: (v: number) => string; className? }`, affiche la valeur finale immédiatement sous reduced-motion).
- Produces: API `StatCard` INCHANGÉE (`value: string | number`) ; un `value` numérique compte désormais en spring, un `value` string reste statique.

- [ ] **Step 1: Écrire le test qui échoue**

```tsx
// frontend/__tests__/components/stat-card.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { StatCard } from '@/components/ui/stat-card'

const reduced = (ui: React.ReactNode) =>
  render(<MotionConfig reducedMotion="always">{ui}</MotionConfig>)

describe('StatCard', () => {
  it('affiche une valeur string telle quelle', () => {
    reduced(<StatCard label="Poids" value="57,2 kg" />)
    expect(screen.getByText('57,2 kg')).toBeInTheDocument()
  })

  it('affiche une valeur numérique entière (count-up, valeur finale sous reduced-motion)', () => {
    reduced(<StatCard label="Séances" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('préserve les décimales de la valeur numérique (format fr-CA)', () => {
    reduced(<StatCard label="Ratio" value={1.25} />)
    expect(screen.getByText('1,25')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `npm run test -- __tests__/components/stat-card.test.tsx`
Expected: le test des décimales FAIL (`1.25` rendu brut, pas `1,25`) — les deux premiers peuvent passer.

- [ ] **Step 3: Implémenter**

Remplacer `frontend/components/ui/stat-card.tsx` :

```tsx
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  color?: 'default' | 'success' | 'danger' | 'info'
}

export function StatCard({ label, value, sub, trend, color = 'default' }: StatCardProps) {
  const colors = {
    default: 'text-[var(--foreground)]',
    success: 'text-[var(--success)]',
    danger: 'text-[var(--destructive)]',
    info: 'text-[var(--ring)]',
  }
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : ''

  // Count-up seulement pour les nombres ; on fige le nombre de décimales de
  // la cible pour que le format ne « saute » pas pendant l'animation.
  const decimals =
    typeof value === 'number' && !Number.isInteger(value)
      ? (String(value).split('.')[1]?.length ?? 0)
      : 0
  const formatted =
    typeof value === 'number' ? (
      <AnimatedNumber
        value={value}
        format={(v) =>
          v.toLocaleString('fr-CA', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          })
        }
      />
    ) : (
      value
    )

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] p-5 card-hover space-y-1">
      <p className="text-[13px] text-[var(--muted-foreground)]">{label}</p>
      <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${colors[color]}`}>
        {formatted}
        {trendIcon && <span className="ml-1.5 text-base opacity-60">{trendIcon}</span>}
      </p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  )
}
```

Note : `AnimatedNumber` est un composant client ; `StatCard` reste importable côté serveur (frontière client au niveau du chiffre).

- [ ] **Step 4: Vérifier que les tests passent**

Run: `npm run test -- __tests__/components/stat-card.test.tsx`
Expected: 3 PASS. Puis `npm run test` complet → si des tests existants assertent un nombre brut rendu par StatCard (ex. `getByText('42')` sur un nombre passé en `value`), ils passent toujours (le count-up rend la valeur finale en jsdom sous reduced-motion ; sinon adapter le test concerné en l'enveloppant de `MotionConfig reducedMotion="always"`).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/stat-card.tsx frontend/__tests__/components/stat-card.test.tsx
git commit -m "feat(ui): count-up des valeurs numériques de StatCard (AnimatedNumber)"
```

---

### Task 5: Primitives Stagger + PageLayout en spring (et nettoyage CSS `.stagger`)

**Files:**
- Create: `frontend/lib/motion/Stagger.tsx`
- Test: `frontend/__tests__/motion/Stagger.test.tsx`
- Modify: `frontend/components/layout/PageLayout.tsx`
- Modify: `frontend/src/app/globals.css` (supprimer le bloc `.stagger` inutilisé)

**Interfaces:**
- Consumes: `fadeUp`, `staggerContainer` depuis `@/lib/motion/variants` (existants).
- Produces: `<StaggerGroup className?>` (conteneur `initial="hidden" animate="visible"`) + `<StaggerItem className?>` (enfant `fadeUp`) — cascade opt-in SANS wrapper automatique des enfants (ne casse jamais grids/col-span). `PageLayout` inchangé côté API, contenu en fadeUp spring.

- [ ] **Step 1: Écrire le test qui échoue**

```tsx
// frontend/__tests__/motion/Stagger.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { StaggerGroup, StaggerItem } from '@/lib/motion/Stagger'

describe('StaggerGroup / StaggerItem', () => {
  it('rend les enfants et applique la className du conteneur', () => {
    render(
      <MotionConfig reducedMotion="always">
        <StaggerGroup className="grid grid-cols-2">
          <StaggerItem>Un</StaggerItem>
          <StaggerItem className="col-span-2">Deux</StaggerItem>
        </StaggerGroup>
      </MotionConfig>,
    )
    expect(screen.getByText('Un')).toBeInTheDocument()
    expect(screen.getByText('Deux').className).toContain('col-span-2')
    expect(screen.getByTestId('stagger-group').className).toContain('grid-cols-2')
  })
})
```

- [ ] **Step 2: Vérifier l'échec**

Run: `npm run test -- __tests__/motion/Stagger.test.tsx`
Expected: FAIL — « Failed to resolve import "@/lib/motion/Stagger" »

- [ ] **Step 3: Implémenter**

```tsx
// frontend/lib/motion/Stagger.tsx
'use client'

/**
 * Cascade d'entrée déclarative (remplace l'ancien utilitaire CSS `.stagger`
 * limité à 6 enfants). Opt-in : chaque item est posé explicitement, le
 * conteneur peut être une grid (l'item porte les classes de placement,
 * ex. col-span-2). Sous reduced-motion, seuls les fondus restent.
 */

import { motion } from 'motion/react'
import { fadeUp, staggerContainer } from './variants'

export function StaggerGroup({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.div
      data-testid="stagger-group"
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {children}
    </motion.div>
  )
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <motion.div className={className} variants={fadeUp}>
      {children}
    </motion.div>
  )
}
```

Puis `frontend/components/layout/PageLayout.tsx` (API inchangée ; l'en-tête sticky ne fond plus — c'est du chrome, le faire clignoter participait à l'effet « PowerPoint » ; le contenu entre en fadeUp spring) :

```tsx
'use client'

import { ReactNode } from 'react'
import { motion } from 'motion/react'
import { fadeUp } from '@/lib/motion/variants'

interface PageLayoutProps {
  title: string
  actions?: ReactNode
  children: ReactNode
}

export default function PageLayout({ title, actions, children }: PageLayoutProps) {
  return (
    <div className="flex flex-col min-h-full">
      {/* En-tête collant en verre : le contenu glisse dessous au scroll. */}
      <div className="glass-panel sticky top-0 z-[var(--z-header)] flex items-center justify-between border-b border-[var(--glass-border)] px-6 py-4">
        <h1 className="font-display text-2xl text-[var(--foreground)]">{title}</h1>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <motion.div
        className="flex-1 p-6"
        variants={fadeUp}
        initial="hidden"
        animate="visible"
      >
        {children}
      </motion.div>
    </div>
  )
}
```

Enfin, dans `frontend/src/app/globals.css`, supprimer le bloc `/* Stagger children */` (`.stagger > *:nth-child(1..6)`, lignes ~401-407) — vérifié inutilisé (`grep -rn "className=.*stagger" src components` → aucun résultat).

- [ ] **Step 4: Vérifier que les tests passent**

Run: `npm run test -- __tests__/motion/Stagger.test.tsx` puis `npm run test` (suite complète)
Expected: PASS partout — PageLayout garde le même markup hormis les classes d'animation.

- [ ] **Step 5: Build de vérification**

Run: `npm run build`
Expected: build OK (PageLayout devient client component — ses enfants restent rendus côté serveur car passés en props).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/motion/Stagger.tsx frontend/__tests__/motion/Stagger.test.tsx frontend/components/layout/PageLayout.tsx frontend/src/app/globals.css
git commit -m "feat(ui): primitives StaggerGroup/StaggerItem et entrée spring de PageLayout"
```

---

## Vérification finale (après Task 5)

- [ ] `npm run test` — suite Vitest complète verte.
- [ ] `npm run lint` — zéro nouvelle erreur par rapport à `main`.
- [ ] `npm run build` — build Next OK.
- [ ] Vérification manuelle (`make dev` à la racine) : naviguer Deck → Finance → onglet interne → Garde-robe. Attendu : aucun flash intra-module, fondu court entre modules, pastille d'onglet qui glisse, dialog avec sortie animée, chiffres en count-up.
- [ ] Les snapshots visuels Playwright (`npm run test:e2e`) nécessitent le backend lancé ; si des snapshots divergent à cause des nouvelles animations, re-générer avec `npm run test:e2e:update` après stabilisation.
- [ ] Marquer les items correspondants dans `improvements.md` (§1.1, 1.3 partiel, 1.4, 1.6, 1.7 pour les tabs) et noter la date.
