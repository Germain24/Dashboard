# Deck Framer Motion + expérience « Corps » — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refondre la coquille d'accueil (`Deck`) avec Framer Motion et transformer le groupe *Santé & Performance* en une « expérience Corps » riche en données (vitrine + drill-in), comme prototype de la nouvelle norme.

**Architecture :** Le scroll-snap reste piloté en CSS (classes `.deck` / `.deck-section` déjà présentes dans `globals.css`, composées au niveau GPU). Framer Motion (paquet `motion`, import `motion/react`) pilote tout le reste à l'intérieur des sections : entrée en stagger, parallax souris, tilt 3D, count-up. Les modules de données sont des aperçus en lecture seule qui consomment les hooks React Query existants (dédupliqués par `queryKey`) et renvoient un `Link` drill-in vers la page dédiée. On construit `components/deck/` à côté de l'ancien `components/layout/Deck.tsx` ; bascule de `page.tsx` une fois Corps validé.

**Tech Stack :** Next.js 15 (App Router) · React 19 · TanStack Query v5 · `motion` (Framer Motion) · Tailwind v4 · Vitest + Testing Library · Playwright.

## Global Constraints

- Bibliothèque d'animation : **`motion`** (successeur de `framer-motion`), import depuis `motion/react`. Aucune autre dépendance ajoutée.
- **Le snap reste CSS** (`scroll-snap-type`). Ne jamais réimplémenter le snap en JS.
- **`tabular-nums`** sur **tout** chiffre animé (score, compteurs, macros, sommeil).
- **Tilt 3D ≤ ±4°** sur les modules satellites ; inertie spring sur le retour de hover.
- **`prefers-reduced-motion`** (via `useReducedMotion()`) : conserver les fondus fluides ; désactiver parallax souris, parallax scroll, tilt 3D, count-up (valeur finale immédiate).
- **Aucun nouvel endpoint backend.** 100 % des données via hooks existants.
- Chaque module = aperçu **lecture seule** + `Link` drill-in. Aucune mutation dans la coquille.
- Copie en **français** (cohérent avec l'app).
- Tests : `npx vitest run <chemin>` ; convention RTL `@testing-library/react`, alias `@/`.
- Les chiffres animés se testent en enveloppant le rendu dans `<MotionConfig reducedMotion="always">` → la valeur finale s'affiche immédiatement (déterministe).

---

### Task 1: Dépendance `motion` + tokens de mouvement

**Files:**
- Modify: `frontend/package.json` (ajout dépendance)
- Create: `frontend/lib/motion/tokens.ts`
- Test: `frontend/__tests__/motion/tokens.test.ts`

**Interfaces:**
- Produces:
  - `springs: { soft: Spring; countUp: Spring; tilt: Spring }` où `Spring = { type: "spring"; stiffness: number; damping: number; mass?: number }`
  - `durations: { fast: number; base: number; slow: number }` (secondes)
  - `EASE_OUT: [number, number, number, number]` (cubic-bézier mappé sur `--ease-out`)

- [ ] **Step 1: Installer la dépendance**

Run: `cd frontend && npm install motion`
Expected: `motion` apparaît dans `package.json > dependencies`.

- [ ] **Step 2: Écrire le test (échec)**

Create `frontend/__tests__/motion/tokens.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { springs, durations, EASE_OUT } from '@/lib/motion/tokens'

describe('motion tokens', () => {
  it('expose trois springs typés', () => {
    for (const key of ['soft', 'countUp', 'tilt'] as const) {
      expect(springs[key].type).toBe('spring')
      expect(springs[key].stiffness).toBeGreaterThan(0)
      expect(springs[key].damping).toBeGreaterThan(0)
    }
  })
  it('expose des durées croissantes', () => {
    expect(durations.fast).toBeLessThan(durations.base)
    expect(durations.base).toBeLessThan(durations.slow)
  })
  it('EASE_OUT est une courbe de Bézier à 4 points', () => {
    expect(EASE_OUT).toHaveLength(4)
  })
})
```

- [ ] **Step 3: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/tokens.test.ts`
Expected: FAIL — `Cannot find module '@/lib/motion/tokens'`.

- [ ] **Step 4: Implémenter les tokens**

Create `frontend/lib/motion/tokens.ts`:

```ts
/**
 * Tokens de mouvement — source unique des springs, durées et easings.
 * Toute animation Framer Motion du Deck y puise (cohérence + ajustement central).
 * Mappé sur l'esthétique « quiet luxury » : ressorts amortis, pas de rebond.
 */

export type Spring = {
  type: 'spring'
  stiffness: number
  damping: number
  mass?: number
}

export const springs = {
  /** Entrées / éléments généraux : doux, sans rebond. */
  soft: { type: 'spring', stiffness: 120, damping: 20, mass: 1 } as Spring,
  /** Count-up de chiffres : un peu plus rapide, fortement amorti (pas d'overshoot). */
  countUp: { type: 'spring', stiffness: 90, damping: 26, mass: 1 } as Spring,
  /** Tilt / parallax au survol : inertie marquée mais retour calme. */
  tilt: { type: 'spring', stiffness: 150, damping: 18, mass: 0.6 } as Spring,
} as const

export const durations = {
  fast: 0.25,
  base: 0.45,
  slow: 0.7,
} as const

/** Équivalent JS de --ease-out (globals.css). */
export const EASE_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1]
```

- [ ] **Step 5: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/tokens.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/lib/motion/tokens.ts frontend/__tests__/motion/tokens.test.ts
git commit -m "feat(deck): dépendance motion + tokens de mouvement"
```

---

### Task 2: `AnimatedNumber` (count-up)

**Files:**
- Create: `frontend/lib/motion/AnimatedNumber.tsx`
- Test: `frontend/__tests__/motion/AnimatedNumber.test.tsx`

**Interfaces:**
- Consumes: `springs.countUp` (Task 1)
- Produces: `AnimatedNumber({ value: number; format?: (v: number) => string; className?: string }): JSX.Element`
  - Anime de 0 → `value`. Sous `reduced-motion`, affiche `value` immédiatement.
  - `format` par défaut : `(v) => String(Math.round(v))`.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/motion/AnimatedNumber.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'

function renderReduced(ui: React.ReactNode) {
  return render(<MotionConfig reducedMotion="always">{ui}</MotionConfig>)
}

describe('AnimatedNumber', () => {
  it('affiche la valeur finale immédiatement sous reduced-motion', () => {
    renderReduced(<AnimatedNumber value={78} />)
    expect(screen.getByText('78')).toBeInTheDocument()
  })
  it('applique la classe transmise (ex. tabular-nums)', () => {
    renderReduced(<AnimatedNumber value={42} className="tabular-nums" />)
    expect(screen.getByText('42').className).toContain('tabular-nums')
  })
  it('utilise le format fourni', () => {
    renderReduced(<AnimatedNumber value={1840} format={(v) => `${Math.round(v)} kcal`} />)
    expect(screen.getByText('1840 kcal')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/AnimatedNumber.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter le composant**

Create `frontend/lib/motion/AnimatedNumber.tsx`:

```tsx
'use client'

/**
 * Chiffre animé en count-up (0 → value) via un ressort amorti.
 * Respecte reduced-motion : la valeur finale s'affiche immédiatement.
 * Toujours utilisé avec `tabular-nums` côté appelant pour éviter les sauts.
 */

import { useEffect, useState } from 'react'
import { useSpring, useReducedMotion, useMotionValueEvent } from 'motion/react'
import { springs } from './tokens'

type Props = {
  value: number
  format?: (v: number) => string
  className?: string
}

export function AnimatedNumber({ value, format = (v) => String(Math.round(v)), className }: Props) {
  const reduced = useReducedMotion()
  const spring = useSpring(0, springs.countUp)
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (reduced) {
      spring.jump(value)
      setDisplay(value)
    } else {
      spring.set(value)
    }
  }, [value, reduced, spring])

  useMotionValueEvent(spring, 'change', (v) => setDisplay(v))

  return <span className={className}>{format(display)}</span>
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/AnimatedNumber.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/motion/AnimatedNumber.tsx frontend/__tests__/motion/AnimatedNumber.test.tsx
git commit -m "feat(deck): AnimatedNumber (count-up, reduced-motion safe)"
```

---

### Task 3: Variants d'entrée réutilisables

**Files:**
- Create: `frontend/lib/motion/variants.ts`
- Test: `frontend/__tests__/motion/variants.test.ts`

**Interfaces:**
- Consumes: `springs.soft` (Task 1)
- Produces:
  - `fadeUp: Variants` — `hidden: { opacity: 0, y: 16 }`, `visible: { opacity: 1, y: 0, transition: spring }`
  - `staggerContainer: Variants` — `visible.transition.staggerChildren > 0`
  - `STAGGER_STEP: number` (secondes entre enfants)

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/motion/variants.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { fadeUp, staggerContainer, STAGGER_STEP } from '@/lib/motion/variants'

describe('motion variants', () => {
  it('fadeUp part masqué et décalé vers le bas, arrive en place', () => {
    expect(fadeUp.hidden).toMatchObject({ opacity: 0 })
    expect((fadeUp.hidden as { y: number }).y).toBeGreaterThan(0)
    expect(fadeUp.visible).toMatchObject({ opacity: 1, y: 0 })
  })
  it('staggerContainer cascade ses enfants', () => {
    const v = staggerContainer.visible as { transition: { staggerChildren: number } }
    expect(v.transition.staggerChildren).toBeCloseTo(STAGGER_STEP)
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/variants.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter les variants**

Create `frontend/lib/motion/variants.ts`:

```ts
/**
 * Variants Framer Motion partagés par les sections du Deck.
 * `staggerContainer` orchestre l'entrée en cascade des enfants `fadeUp`.
 * Sous reduced-motion, Framer Motion neutralise automatiquement les transforms
 * (les `y` sont ignorés), il ne reste que le fondu d'opacité.
 */

import type { Variants } from 'motion/react'
import { springs } from './tokens'

/** Décalage temporel (s) entre chaque enfant d'un conteneur en stagger. */
export const STAGGER_STEP = 0.07

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: springs.soft },
}

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: STAGGER_STEP, delayChildren: 0.05 },
  },
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/variants.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/motion/variants.ts frontend/__tests__/motion/variants.test.ts
git commit -m "feat(deck): variants d'entrée (fadeUp + staggerContainer)"
```

---

### Task 4: Parallax souris (`computeParallax` + `useParallax`)

**Files:**
- Create: `frontend/lib/motion/useParallax.ts`
- Test: `frontend/__tests__/motion/useParallax.test.ts`

**Interfaces:**
- Consumes: `springs.tilt` (Task 1)
- Produces:
  - `computeParallax(clientX, clientY, rect, strength): { x: number; y: number }` — pure ; `rect = { left, top, width, height }` ; décalage borné à `±strength` px, **inversé** par rapport à la souris (effet profondeur).
  - `useParallax(strength: number): { ref: RefObject<HTMLDivElement | null>; x: MotionValue<number>; y: MotionValue<number> }` — désactivé (0,0) sous reduced-motion.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/motion/useParallax.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { computeParallax } from '@/lib/motion/useParallax'

const rect = { left: 0, top: 0, width: 200, height: 200 } // centre = (100,100)

describe('computeParallax', () => {
  it('renvoie (0,0) quand la souris est au centre', () => {
    expect(computeParallax(100, 100, rect, 10)).toEqual({ x: 0, y: 0 })
  })
  it('inverse le sens (souris à droite → décalage négatif en x)', () => {
    const { x } = computeParallax(200, 100, rect, 10)
    expect(x).toBeLessThan(0)
  })
  it('borne le décalage à ±strength', () => {
    const { x, y } = computeParallax(10000, 10000, rect, 10)
    expect(x).toBeGreaterThanOrEqual(-10)
    expect(y).toBeGreaterThanOrEqual(-10)
    expect(Math.abs(x)).toBeLessThanOrEqual(10)
    expect(Math.abs(y)).toBeLessThanOrEqual(10)
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/useParallax.test.ts`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/lib/motion/useParallax.ts`:

```ts
'use client'

/**
 * Parallax souris pour un élément héros (anneau de score).
 * `computeParallax` est pure et testée ; `useParallax` la branche aux
 * MotionValues + springs. Désactivé sous reduced-motion (reste à 0,0).
 */

import { useEffect, useRef } from 'react'
import { useMotionValue, useSpring, useReducedMotion, type MotionValue } from 'motion/react'
import { springs } from './tokens'

type Rect = { left: number; top: number; width: number; height: number }

export function computeParallax(
  clientX: number,
  clientY: number,
  rect: Rect,
  strength: number,
): { x: number; y: number } {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  const nx = (clientX - cx) / (rect.width / 2) // -1..1 (hors borne possible)
  const ny = (clientY - cy) / (rect.height / 2)
  const clamp = (v: number) => Math.max(-1, Math.min(1, v))
  // Inversé : l'élément « recule » dans le sens opposé à la souris.
  return { x: -clamp(nx) * strength, y: -clamp(ny) * strength }
}

export function useParallax(strength: number): {
  ref: React.RefObject<HTMLDivElement | null>
  x: MotionValue<number>
  y: MotionValue<number>
} {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLDivElement | null>(null)
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const x = useSpring(rawX, springs.tilt)
  const y = useSpring(rawY, springs.tilt)

  useEffect(() => {
    if (reduced) {
      rawX.set(0)
      rawY.set(0)
      return
    }
    const handle = (e: MouseEvent) => {
      const el = ref.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const { x: px, y: py } = computeParallax(e.clientX, e.clientY, rect, strength)
      rawX.set(px)
      rawY.set(py)
    }
    window.addEventListener('mousemove', handle)
    return () => window.removeEventListener('mousemove', handle)
  }, [reduced, strength, rawX, rawY])

  return { ref, x, y }
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/useParallax.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/motion/useParallax.ts frontend/__tests__/motion/useParallax.test.ts
git commit -m "feat(deck): parallax souris (computeParallax + useParallax)"
```

---

### Task 5: `TiltCard` (tilt 3D ≤ ±4° + inertie spring)

**Files:**
- Create: `frontend/lib/motion/TiltCard.tsx`
- Test: `frontend/__tests__/motion/TiltCard.test.tsx`

**Interfaces:**
- Consumes: `springs.tilt` (Task 1)
- Produces:
  - `computeTilt(clientX, clientY, rect, maxDeg): { rotateX: number; rotateY: number }` — pure ; bornes `±maxDeg`. Souris en haut → `rotateX > 0` (la carte « se penche » vers l'utilisateur en haut).
  - `MAX_TILT_DEG = 4`
  - `TiltCard({ children, className }): JSX.Element` — wrapper appliquant le tilt au survol, désactivé sous reduced-motion.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/motion/TiltCard.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { computeTilt, MAX_TILT_DEG, TiltCard } from '@/lib/motion/TiltCard'

const rect = { left: 0, top: 0, width: 100, height: 100 }

describe('computeTilt', () => {
  it('ne dépasse jamais ±MAX_TILT_DEG', () => {
    const { rotateX, rotateY } = computeTilt(99999, -99999, rect, MAX_TILT_DEG)
    expect(Math.abs(rotateX)).toBeLessThanOrEqual(MAX_TILT_DEG)
    expect(Math.abs(rotateY)).toBeLessThanOrEqual(MAX_TILT_DEG)
  })
  it('reste à 0 au centre', () => {
    expect(computeTilt(50, 50, rect, MAX_TILT_DEG)).toEqual({ rotateX: 0, rotateY: 0 })
  })
  it('MAX_TILT_DEG vaut 4 (quiet luxury)', () => {
    expect(MAX_TILT_DEG).toBe(4)
  })
})

describe('TiltCard', () => {
  it('rend ses enfants', () => {
    render(
      <MotionConfig reducedMotion="always">
        <TiltCard>contenu</TiltCard>
      </MotionConfig>,
    )
    expect(screen.getByText('contenu')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/TiltCard.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/lib/motion/TiltCard.tsx`:

```tsx
'use client'

/**
 * Carte avec tilt 3D très subtil (≤ ±4°) suivant la souris, retour en inertie
 * spring. Esthétique quiet luxury : perceptible seulement si l'on est attentif.
 * Désactivé sous reduced-motion (rend un simple <div>).
 */

import { useRef } from 'react'
import { motion, useMotionValue, useSpring, useReducedMotion } from 'motion/react'
import { springs } from './tokens'
import { cn } from '@/lib/utils'

export const MAX_TILT_DEG = 4

type Rect = { left: number; top: number; width: number; height: number }

export function computeTilt(
  clientX: number,
  clientY: number,
  rect: Rect,
  maxDeg: number,
): { rotateX: number; rotateY: number } {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  const nx = (clientX - cx) / (rect.width / 2)
  const ny = (clientY - cy) / (rect.height / 2)
  const clamp = (v: number) => Math.max(-1, Math.min(1, v))
  // Souris en haut (ny<0) → bord haut vers l'utilisateur → rotateX positif.
  return { rotateX: -clamp(ny) * maxDeg, rotateY: clamp(nx) * maxDeg }
}

export function TiltCard({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLDivElement | null>(null)
  const rx = useMotionValue(0)
  const ry = useMotionValue(0)
  const rotateX = useSpring(rx, springs.tilt)
  const rotateY = useSpring(ry, springs.tilt)

  if (reduced) {
    return <div className={className}>{children}</div>
  }

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el) return
    const t = computeTilt(e.clientX, e.clientY, el.getBoundingClientRect(), MAX_TILT_DEG)
    rx.set(t.rotateX)
    ry.set(t.rotateY)
  }
  const onLeave = () => {
    rx.set(0)
    ry.set(0)
  }

  return (
    <div ref={ref} style={{ perspective: 1000 }} onMouseMove={onMove} onMouseLeave={onLeave}>
      <motion.div
        className={cn(className)}
        style={{ rotateX, rotateY, transformStyle: 'preserve-3d' }}
      >
        {children}
      </motion.div>
    </div>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/motion/TiltCard.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/motion/TiltCard.tsx frontend/__tests__/motion/TiltCard.test.tsx
git commit -m "feat(deck): TiltCard (tilt 3D ≤4° + inertie spring)"
```

---

### Task 6: `DeckSection` (orchestration d'entrée)

**Files:**
- Create: `frontend/components/deck/DeckSection.tsx`
- Test: `frontend/__tests__/deck/DeckSection.test.tsx`

**Interfaces:**
- Consumes: `staggerContainer` (Task 3)
- Produces:
  - `DeckSection({ children, label, index, sectionRef }): JSX.Element` — `<section>` avec classe `deck-section`, `aria-label={label}`, conteneur motion en `staggerContainer` qui s'anime quand visible (`useInView({ once: true, amount: 0.4 })`). `sectionRef` est un callback ref transmis au `<section>` (pour le snap/nav). `index` sert au libellé `NN / TT` optionnel côté appelant — ici simple passthrough.
  - `MotionFadeUp` réexporté pour les enfants : `MotionFadeUp = motion.div` configuré sur `variants={fadeUp}` (helper).

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/DeckSection.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { DeckSection } from '@/components/deck/DeckSection'

describe('DeckSection', () => {
  it('rend une section étiquetée contenant ses enfants', () => {
    render(
      <MotionConfig reducedMotion="always">
        <DeckSection label="Corps" index={2}>
          <p>contenu</p>
        </DeckSection>
      </MotionConfig>,
    )
    const section = screen.getByRole('region', { name: 'Corps' })
    expect(section).toBeInTheDocument()
    expect(section.className).toContain('deck-section')
    expect(screen.getByText('contenu')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/DeckSection.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/DeckSection.tsx`:

```tsx
'use client'

/**
 * Wrapper générique d'une section du Deck. Conserve le snap CSS (.deck-section)
 * et délègue l'orchestration d'entrée à Framer Motion : le conteneur passe en
 * `visible` (stagger) dès qu'il entre dans le viewport. Réutilisable par toutes
 * les expériences de domaine.
 */

import { useRef, type ReactNode } from 'react'
import { motion, useInView } from 'motion/react'
import { fadeUp, staggerContainer } from '@/lib/motion/variants'

/** Enfant standard d'une DeckSection : entre en fondu + slide-up. */
export const MotionFadeUp = motion.create('div')

export function DeckSection({
  children,
  label,
  index,
  sectionRef,
}: {
  children: ReactNode
  label: string
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  const inViewRef = useRef<HTMLDivElement>(null)
  const inView = useInView(inViewRef, { once: true, amount: 0.4 })

  return (
    <section ref={sectionRef} className="deck-section" aria-label={label} data-index={index}>
      <motion.div
        ref={inViewRef}
        variants={staggerContainer}
        initial="hidden"
        animate={inView ? 'visible' : 'hidden'}
        className="mx-auto w-full max-w-[1280px] px-[max(24px,calc((100vw-1280px)/2+24px))]"
      >
        {children}
      </motion.div>
    </section>
  )
}

/** Helper : enfant fadeUp prêt à l'emploi. */
export function FadeUpItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <MotionFadeUp variants={fadeUp} className={className}>
      {children}
    </MotionFadeUp>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/DeckSection.test.tsx`
Expected: PASS (1 test). `getByRole('region', { name })` fonctionne car `<section aria-label>` a le rôle `region`.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/DeckSection.tsx frontend/__tests__/deck/DeckSection.test.tsx
git commit -m "feat(deck): DeckSection (orchestration d'entrée en stagger)"
```

---

### Task 7: `ScoreRingModule` (héros)

**Files:**
- Create: `frontend/components/deck/modules/ScoreRingModule.tsx`
- Test: `frontend/__tests__/deck/ScoreRingModule.test.tsx`

**Interfaces:**
- Consumes: `useScore()` (existant) → `{ data?: ScoreDay; isLoading; isError }` ; `ScoreDay.score: number | null`, `ScoreDay.composantes: { sommeil, sport, nutrition }` ; `AnimatedNumber` (Task 2) ; `useParallax` (Task 4).
- Produces: `ScoreRingModule(): JSX.Element` — héros : anneau SVG (`pathLength` proportionnel au score), `AnimatedNumber` au centre en `tabular-nums`, sous-scores ; `Link href="/score"`. États loading (skeleton) / erreur (valeur `—`).

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/ScoreRingModule.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn() }))
import { useScore } from '@/lib/queries/sante'
import { ScoreRingModule } from '@/components/deck/modules/ScoreRingModule'

const mockUseScore = vi.mocked(useScore)

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <ScoreRingModule />
    </MotionConfig>,
  )
}

beforeEach(() => mockUseScore.mockReset())

describe('ScoreRingModule', () => {
  it('affiche le score en tabular-nums et un drill-in vers /score', () => {
    mockUseScore.mockReturnValue({
      data: { date: '2026-06-24', score: 78, composantes: { sommeil: 80, sport: 70, nutrition: 84 }, details: { sommeil_h: 7.6, sessions_7j: 4, kcal_consommees: 1840, kcal_cible: 2100 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByText('78').className).toContain('tabular-nums')
    expect(screen.getByRole('link', { name: /score/i })).toHaveAttribute('href', '/score')
  })

  it('affiche un skeleton au chargement', () => {
    mockUseScore.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByTestId('score-skeleton')).toBeInTheDocument()
  })

  it('affiche — quand le score est indisponible', () => {
    mockUseScore.mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useScore>)
    renderModule()
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/ScoreRingModule.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/modules/ScoreRingModule.tsx`:

```tsx
'use client'

/**
 * Module héros « Score de forme » : anneau SVG dont l'arc se remplit selon le
 * score (0–100), valeur centrale en count-up `tabular-nums`, parallax souris
 * léger, sous-scores sommeil/sport/nutrition. Drill-in vers /score.
 */

import Link from 'next/link'
import { motion } from 'motion/react'
import { useScore } from '@/lib/queries/sante'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'
import { useParallax } from '@/lib/motion/useParallax'
import { Skeleton } from '@/components/ui/skeleton'

const R = 86
const CIRC = 2 * Math.PI * R

function tone(score: number): string {
  if (score >= 80) return 'var(--success)'
  if (score >= 60) return '#22c55e'
  if (score >= 40) return '#f59e0b'
  return 'var(--destructive)'
}

export function ScoreRingModule() {
  const { data, isLoading } = useScore()
  const { ref, x, y } = useParallax(8)

  if (isLoading) {
    return <Skeleton data-testid="score-skeleton" className="h-[220px] w-[220px] rounded-full" />
  }

  const score = data?.score ?? null
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100
  const color = tone(score ?? 0)
  const comps = data?.composantes

  return (
    <Link
      href="/score"
      aria-label={`Score de forme${score != null ? ` : ${score} sur 100` : ''}`}
      className="group inline-flex flex-col items-center gap-4 rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--ring)]"
    >
      <motion.div ref={ref} style={{ x, y }} className="relative h-[220px] w-[220px]">
        <svg viewBox="0 0 200 200" className="h-full w-full -rotate-90">
          <circle cx="100" cy="100" r={R} fill="none" stroke="var(--muted)" strokeWidth="10" />
          <motion.circle
            cx="100" cy="100" r={R} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={CIRC}
            initial={{ strokeDashoffset: CIRC }}
            animate={{ strokeDashoffset: CIRC * (1 - pct) }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {score == null ? (
            <span className="font-display text-5xl tabular-nums text-[var(--muted-foreground)]">—</span>
          ) : (
            <AnimatedNumber value={score} className="font-display text-6xl tabular-nums text-[var(--foreground)]" />
          )}
          <span className="text-xs uppercase tracking-wide text-[var(--muted-foreground)]">score</span>
        </div>
      </motion.div>

      {comps && (
        <div className="flex gap-5 text-sm">
          <SubScore label="Sommeil" value={comps.sommeil} />
          <SubScore label="Sport" value={comps.sport} />
          <SubScore label="Nutrition" value={comps.nutrition} />
        </div>
      )}
    </Link>
  )
}

function SubScore({ label, value }: { label: string; value: number | null }) {
  return (
    <span className="flex flex-col items-center">
      <span className="font-medium tabular-nums text-[var(--foreground)]">{value ?? '—'}</span>
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
    </span>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/ScoreRingModule.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/modules/ScoreRingModule.tsx frontend/__tests__/deck/ScoreRingModule.test.tsx
git commit -m "feat(deck): ScoreRingModule (héros, anneau + count-up + parallax)"
```

---

### Task 8: `MacrosModule` (+ hydratation)

**Files:**
- Create: `frontend/components/deck/modules/MacrosModule.tsx`
- Test: `frontend/__tests__/deck/MacrosModule.test.tsx`

**Interfaces:**
- Consumes: `useScore()` → `data.details.kcal_consommees | kcal_cible` ; `useWaterToday()` → `{ data?: { eau_ml; cible_ml; pct } }` ; `AnimatedNumber` (Task 2) ; `TiltCard` (Task 5).
- Produces: `MacrosModule(): JSX.Element` — calories du jour `consommées / cible` (count-up `tabular-nums`) + barre ; **indicateur d'hydratation discret** (`pct %`) ; `Link href="/sante"`. Skeleton au chargement.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/MacrosModule.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
import { useScore, useWaterToday } from '@/lib/queries/sante'
import { MacrosModule } from '@/components/deck/modules/MacrosModule'

const mockScore = vi.mocked(useScore)
const mockWater = vi.mocked(useWaterToday)

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <MacrosModule />
    </MotionConfig>,
  )
}

beforeEach(() => {
  mockScore.mockReset()
  mockWater.mockReset()
})

describe('MacrosModule', () => {
  it('affiche calories du jour + hydratation, drill-in /sante', () => {
    mockScore.mockReturnValue({
      data: { date: '2026-06-24', score: 70, composantes: { sommeil: 1, sport: 1, nutrition: 1 }, details: { sommeil_h: 7, sessions_7j: 3, kcal_consommees: 1840, kcal_cible: 2100 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    mockWater.mockReturnValue({
      data: { date: '2026-06-24', eau_ml: 1500, cible_ml: 2500, pct: 60 }, isLoading: false, isError: false,
    } as ReturnType<typeof useWaterToday>)
    renderModule()
    expect(screen.getByText('1840').className).toContain('tabular-nums')
    expect(screen.getByText(/2100/)).toBeInTheDocument()
    expect(screen.getByText(/60\s*%/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /nutrition|macros|santé/i })).toHaveAttribute('href', '/sante')
  })

  it('skeleton au chargement', () => {
    mockScore.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useScore>)
    mockWater.mockReturnValue({ data: undefined, isLoading: true, isError: false } as ReturnType<typeof useWaterToday>)
    renderModule()
    expect(screen.getByTestId('macros-skeleton')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/MacrosModule.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/modules/MacrosModule.tsx`:

```tsx
'use client'

/**
 * Module « Macros du jour » : calories consommées / cible (count-up), barre de
 * progression, et hydratation intégrée en indicateur discret (pas de module
 * séparé). Drill-in vers /sante.
 */

import Link from 'next/link'
import { Droplet } from 'lucide-react'
import { useScore, useWaterToday } from '@/lib/queries/sante'
import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function MacrosModule() {
  const { data: score, isLoading: loadingScore } = useScore()
  const { data: water } = useWaterToday()

  if (loadingScore) {
    return <Skeleton data-testid="macros-skeleton" className="h-28 w-full" />
  }

  const kcal = score?.details.kcal_consommees ?? null
  const cible = score?.details.kcal_cible ?? null
  const pct = kcal != null && cible ? Math.min(100, (kcal / cible) * 100) : 0
  const waterPct = water?.pct ?? null

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/sante"
        aria-label="Macros et nutrition du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-baseline justify-between">
          <h3 className="font-display text-xl text-[var(--foreground)]">Macros</h3>
          <p className="text-sm text-[var(--muted-foreground)]">
            {kcal == null ? (
              <span className="tabular-nums">—</span>
            ) : (
              <AnimatedNumber value={kcal} className="tabular-nums text-[var(--foreground)]" />
            )}
            <span className="tabular-nums"> / {cible ?? '—'} kcal</span>
          </p>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded bg-[var(--muted)]">
          <div className="h-full bg-[var(--ring)]" style={{ width: `${pct}%` }} />
        </div>
        {waterPct != null && (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
            <Droplet className="h-3.5 w-3.5" aria-hidden="true" />
            Hydratation <span className="tabular-nums">{waterPct}&nbsp;%</span>
          </p>
        )}
      </Link>
    </TiltCard>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/MacrosModule.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/modules/MacrosModule.tsx frontend/__tests__/deck/MacrosModule.test.tsx
git commit -m "feat(deck): MacrosModule (calories + hydratation discrète)"
```

---

### Task 9: `SleepModule` (`formatSleepHours`)

**Files:**
- Create: `frontend/components/deck/modules/SleepModule.tsx`
- Test: `frontend/__tests__/deck/SleepModule.test.tsx`

**Interfaces:**
- Consumes: `useScore()` → `data.details.sommeil_h: number | null` ; `TiltCard` (Task 5).
- Produces:
  - `formatSleepHours(h: number | null): string` — pure ; `7.6 → "7 h 36"`, `null → "—"`.
  - `SleepModule(): JSX.Element` — affiche la durée de la dernière nuit en `tabular-nums`, `Link href="/score"`.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/SleepModule.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn() }))
import { useScore } from '@/lib/queries/sante'
import { SleepModule, formatSleepHours } from '@/components/deck/modules/SleepModule'

const mockScore = vi.mocked(useScore)
beforeEach(() => mockScore.mockReset())

describe('formatSleepHours', () => {
  it('formate les heures décimales en « h min »', () => {
    expect(formatSleepHours(7.5)).toBe('7 h 30')
    expect(formatSleepHours(8)).toBe('8 h 00')
  })
  it('renvoie — pour null', () => {
    expect(formatSleepHours(null)).toBe('—')
  })
})

describe('SleepModule', () => {
  it('affiche la durée et un drill-in /score', () => {
    mockScore.mockReturnValue({
      data: { date: '2026-06-24', score: 70, composantes: { sommeil: 1, sport: 1, nutrition: 1 }, details: { sommeil_h: 7.5, sessions_7j: 3, kcal_consommees: 1, kcal_cible: 1 } },
      isLoading: false, isError: false,
    } as ReturnType<typeof useScore>)
    render(
      <MotionConfig reducedMotion="always">
        <SleepModule />
      </MotionConfig>,
    )
    expect(screen.getByText('7 h 30').className).toContain('tabular-nums')
    expect(screen.getByRole('link', { name: /sommeil/i })).toHaveAttribute('href', '/score')
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/SleepModule.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/modules/SleepModule.tsx`:

```tsx
'use client'

/**
 * Module « Sommeil » : durée de la dernière nuit (via le score de forme).
 * Drill-in vers /score. Chiffre en tabular-nums.
 */

import Link from 'next/link'
import { Moon } from 'lucide-react'
import { useScore } from '@/lib/queries/sante'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function formatSleepHours(h: number | null): string {
  if (h == null) return '—'
  const total = Math.round(h * 60)
  const hh = Math.floor(total / 60)
  const mm = total % 60
  return `${hh} h ${String(mm).padStart(2, '0')}`
}

export function SleepModule() {
  const { data, isLoading } = useScore()
  if (isLoading) return <Skeleton data-testid="sleep-skeleton" className="h-24 w-full" />

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/score"
        aria-label="Sommeil de la dernière nuit"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Moon className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Sommeil</span>
        </div>
        <p className="mt-1 font-display text-2xl tabular-nums text-[var(--foreground)]">
          {formatSleepHours(data?.details.sommeil_h ?? null)}
        </p>
      </Link>
    </TiltCard>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/SleepModule.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/modules/SleepModule.tsx frontend/__tests__/deck/SleepModule.test.tsx
git commit -m "feat(deck): SleepModule (durée dernière nuit, formatSleepHours)"
```

---

### Task 10: `NextWorkoutModule`

**Files:**
- Create: `frontend/components/deck/modules/NextWorkoutModule.tsx`
- Test: `frontend/__tests__/deck/NextWorkoutModule.test.tsx`

**Interfaces:**
- Consumes: `useEntrainementToday()` (existant, `@/lib/queries/entrainement`) → `{ data?: TodayResponse }` ; `TodayResponse.jour_label: string`, `TodayResponse.slots: { label: string }[]` ; `TiltCard` (Task 5).
- Produces: `NextWorkoutModule(): JSX.Element` — titre de la séance du jour (`jour_label`) + 1er bloc (`slots[0].label`) ou état « repos », `Link href="/entrainement"`.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/NextWorkoutModule.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { NextWorkoutModule } from '@/components/deck/modules/NextWorkoutModule'

const mockToday = vi.mocked(useEntrainementToday)
beforeEach(() => mockToday.mockReset())

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <NextWorkoutModule />
    </MotionConfig>,
  )
}

describe('NextWorkoutModule', () => {
  it('affiche la séance du jour + drill-in /entrainement', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', weekday: 2, jour_label: 'Push', programme_jour_id: 1, slots: [{ label: 'Développé couché' }], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null },
      isLoading: false, isError: false,
    } as ReturnType<typeof useEntrainementToday>)
    renderModule()
    expect(screen.getByText('Push')).toBeInTheDocument()
    expect(screen.getByText(/Développé couché/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /séance|entraînement/i })).toHaveAttribute('href', '/entrainement')
  })

  it('affiche un état repos si aucun bloc', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', weekday: 6, jour_label: 'Repos', programme_jour_id: null, slots: [], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null },
      isLoading: false, isError: false,
    } as ReturnType<typeof useEntrainementToday>)
    renderModule()
    expect(screen.getByText(/repos/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/NextWorkoutModule.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/modules/NextWorkoutModule.tsx`:

```tsx
'use client'

/**
 * Module « Séance du jour » : libellé du jour programmé + premier bloc.
 * État repos si aucun bloc. Drill-in vers /entrainement.
 */

import Link from 'next/link'
import { Dumbbell } from 'lucide-react'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function NextWorkoutModule() {
  const { data, isLoading } = useEntrainementToday()
  if (isLoading) return <Skeleton data-testid="workout-skeleton" className="h-24 w-full" />

  const label = data?.jour_label ?? '—'
  const firstBlock = data?.slots?.[0]?.label ?? null

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/entrainement"
        aria-label="Séance d'entraînement du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Dumbbell className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Séance du jour</span>
        </div>
        <p className="mt-1 font-display text-2xl text-[var(--foreground)]">{label}</p>
        <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">
          {firstBlock ?? 'Jour de repos'}
        </p>
      </Link>
    </TiltCard>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/NextWorkoutModule.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/modules/NextWorkoutModule.tsx frontend/__tests__/deck/NextWorkoutModule.test.tsx
git commit -m "feat(deck): NextWorkoutModule (séance du jour)"
```

---

### Task 11: `SkincareModule`

**Files:**
- Create: `frontend/components/deck/modules/SkincareModule.tsx`
- Test: `frontend/__tests__/deck/SkincareModule.test.tsx`

**Interfaces:**
- Consumes: `useSkincareToday()` (existant, `@/lib/queries/skincare`) → `{ data?: SkincareToday }` ; `SkincareToday.due: unknown[]`, `PM: unknown[]` ; `TiltCard` (Task 5).
- Produces: `SkincareModule(): JSX.Element` — nombre de produits dus (`due.length`) → `"N dû"` ou `"à jour"`, `Link href="/skincare"`.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/SkincareModule.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))
import { useSkincareToday } from '@/lib/queries/skincare'
import { SkincareModule } from '@/components/deck/modules/SkincareModule'

const mockToday = vi.mocked(useSkincareToday)
beforeEach(() => mockToday.mockReset())

function renderModule() {
  return render(
    <MotionConfig reducedMotion="always">
      <SkincareModule />
    </MotionConfig>,
  )
}

describe('SkincareModule', () => {
  it('affiche le nombre de produits dus + drill-in /skincare', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', AM: [], PM: [{}, {}], due: [{}, {}, {}] }, isLoading: false, isError: false,
    } as ReturnType<typeof useSkincareToday>)
    renderModule()
    expect(screen.getByText(/3\s*dû/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /skincare/i })).toHaveAttribute('href', '/skincare')
  })

  it('affiche « à jour » quand rien n\'est dû', () => {
    mockToday.mockReturnValue({
      data: { date: '2026-06-24', AM: [], PM: [], due: [] }, isLoading: false, isError: false,
    } as ReturnType<typeof useSkincareToday>)
    renderModule()
    expect(screen.getByText(/à jour/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/SkincareModule.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/modules/SkincareModule.tsx`:

```tsx
'use client'

/**
 * Module « Skincare » : nombre de produits dus aujourd'hui. Drill-in /skincare.
 */

import Link from 'next/link'
import { Sparkles } from 'lucide-react'
import { useSkincareToday } from '@/lib/queries/skincare'
import { TiltCard } from '@/lib/motion/TiltCard'
import { Skeleton } from '@/components/ui/skeleton'

export function SkincareModule() {
  const { data, isLoading } = useSkincareToday()
  if (isLoading) return <Skeleton data-testid="skincare-skeleton" className="h-24 w-full" />

  const due = data?.due.length ?? 0

  return (
    <TiltCard className="block rounded-[var(--radius-lg)]">
      <Link
        href="/skincare"
        aria-label="Routine skincare du jour"
        className="block rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
      >
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          <span className="text-sm">Skincare</span>
        </div>
        <p className="mt-1 font-display text-2xl text-[var(--foreground)]">
          {due > 0 ? (
            <>
              <span className="tabular-nums">{due}</span> dû
            </>
          ) : (
            'à jour'
          )}
        </p>
      </Link>
    </TiltCard>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/SkincareModule.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/modules/SkincareModule.tsx frontend/__tests__/deck/SkincareModule.test.tsx
git commit -m "feat(deck): SkincareModule (produits dus du jour)"
```

---

### Task 12: `CorpsExperience` (composition)

**Files:**
- Create: `frontend/components/deck/experiences/CorpsExperience.tsx`
- Test: `frontend/__tests__/deck/CorpsExperience.test.tsx`

**Interfaces:**
- Consumes: `DeckSection`, `FadeUpItem` (Task 6) ; les 5 modules (Tasks 7–11). Tous les hooks sont mockés dans le test.
- Produces: `CorpsExperience({ index, sectionRef }): JSX.Element` — `DeckSection label="Corps"` avec mise en page éditoriale : titre serif + numéro `NN / 07`, héros `ScoreRingModule` à gauche, colonne de modules satellites à droite.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/CorpsExperience.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))

import { useScore, useWaterToday } from '@/lib/queries/sante'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { useSkincareToday } from '@/lib/queries/skincare'
import { CorpsExperience } from '@/components/deck/experiences/CorpsExperience'

beforeEach(() => {
  vi.mocked(useScore).mockReturnValue({
    data: { date: '2026-06-24', score: 78, composantes: { sommeil: 80, sport: 70, nutrition: 84 }, details: { sommeil_h: 7.5, sessions_7j: 4, kcal_consommees: 1840, kcal_cible: 2100 } },
    isLoading: false, isError: false,
  } as ReturnType<typeof useScore>)
  vi.mocked(useWaterToday).mockReturnValue({ data: { date: '2026-06-24', eau_ml: 1500, cible_ml: 2500, pct: 60 }, isLoading: false, isError: false } as ReturnType<typeof useWaterToday>)
  vi.mocked(useEntrainementToday).mockReturnValue({ data: { date: '2026-06-24', weekday: 2, jour_label: 'Push', programme_jour_id: 1, slots: [{ label: 'Développé couché' }], seance_en_cours: null, kcal_estimees: 0, poids_corps_kg: 70, mesocycle: null }, isLoading: false, isError: false } as ReturnType<typeof useEntrainementToday>)
  vi.mocked(useSkincareToday).mockReturnValue({ data: { date: '2026-06-24', AM: [], PM: [{}], due: [{}] }, isLoading: false, isError: false } as ReturnType<typeof useSkincareToday>)
})

describe('CorpsExperience', () => {
  it('compose le titre Corps et les 5 modules', () => {
    render(
      <MotionConfig reducedMotion="always">
        <CorpsExperience index={2} />
      </MotionConfig>,
    )
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Corps' })).toBeInTheDocument()
    expect(screen.getByText('78')).toBeInTheDocument()            // score héros
    expect(screen.getByText('Macros')).toBeInTheDocument()        // macros
    expect(screen.getByText('7 h 30')).toBeInTheDocument()        // sommeil
    expect(screen.getByText('Push')).toBeInTheDocument()          // séance
    expect(screen.getByText(/dû/)).toBeInTheDocument()            // skincare
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/CorpsExperience.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/experiences/CorpsExperience.tsx`:

```tsx
'use client'

/**
 * Expérience « Corps » (groupe Santé & Performance) — prototype de la nouvelle
 * norme : héros Score de forme + modules satellites (sommeil, macros, séance,
 * skincare), mise en page éditoriale asymétrique. Vitrine + drill-in.
 */

import { DeckSection, FadeUpItem } from '@/components/deck/DeckSection'
import { ScoreRingModule } from '@/components/deck/modules/ScoreRingModule'
import { MacrosModule } from '@/components/deck/modules/MacrosModule'
import { SleepModule } from '@/components/deck/modules/SleepModule'
import { NextWorkoutModule } from '@/components/deck/modules/NextWorkoutModule'
import { SkincareModule } from '@/components/deck/modules/SkincareModule'

export function CorpsExperience({
  index,
  sectionRef,
}: {
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  return (
    <DeckSection label="Corps" index={index} sectionRef={sectionRef}>
      <FadeUpItem>
        <p className="text-sm text-[var(--muted-foreground)]">
          {String(index + 1).padStart(2, '0')} / 07
        </p>
        <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
          Corps
        </h2>
      </FadeUpItem>

      <div className="mt-10 grid items-center gap-10 md:grid-cols-[auto_1fr]">
        <FadeUpItem className="flex justify-center md:justify-start">
          <ScoreRingModule />
        </FadeUpItem>

        <div className="grid gap-4 sm:grid-cols-2">
          <FadeUpItem><SleepModule /></FadeUpItem>
          <FadeUpItem><MacrosModule /></FadeUpItem>
          <FadeUpItem><NextWorkoutModule /></FadeUpItem>
          <FadeUpItem><SkincareModule /></FadeUpItem>
        </div>
      </div>
    </DeckSection>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/CorpsExperience.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/experiences/CorpsExperience.tsx frontend/__tests__/deck/CorpsExperience.test.tsx
git commit -m "feat(deck): CorpsExperience (composition héros + satellites)"
```

---

### Task 13: `GenericGroupExperience` (repli pour les autres groupes)

**Files:**
- Create: `frontend/components/deck/experiences/GenericGroupExperience.tsx`
- Test: `frontend/__tests__/deck/GenericGroupExperience.test.tsx`

**Interfaces:**
- Consumes: `DeckSection`, `FadeUpItem` (Task 6) ; type `ModuleGroup` item de `MODULE_GROUPS` (`@/lib/modules`) : `{ group: string; items: Module[] }`.
- Produces: `GenericGroupExperience({ group, index, sectionRef }): JSX.Element` — rend le titre du groupe + une rangée de cartes-liens (équivalent visuel de l'ancien Deck) pour tout groupe non encore migré.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/GenericGroupExperience.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'
import { Wallet } from 'lucide-react'
import { GenericGroupExperience } from '@/components/deck/experiences/GenericGroupExperience'

const group = {
  group: 'Finances & Ingénierie',
  items: [
    { slug: 'budget', label: 'Budget', description: 'Trésorerie', icon: Wallet, group: 'Finances & Ingénierie' as const, ready: true },
  ],
}

describe('GenericGroupExperience', () => {
  it('rend le groupe et ses cartes-liens', () => {
    render(
      <MotionConfig reducedMotion="always">
        <GenericGroupExperience group={group} index={1} />
      </MotionConfig>,
    )
    expect(screen.getByRole('region', { name: 'Finances & Ingénierie' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Budget/ })).toHaveAttribute('href', '/budget')
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/GenericGroupExperience.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/experiences/GenericGroupExperience.tsx`:

```tsx
'use client'

/**
 * Repli générique : tout groupe non encore migré en « expérience » dédiée garde
 * un rendu en rangée de cartes-liens (équivalent à l'ancien Deck), enveloppé
 * dans la nouvelle DeckSection pour bénéficier du snap + de l'entrée en stagger.
 */

import Link from 'next/link'
import { DeckSection, FadeUpItem } from '@/components/deck/DeckSection'
import type { MODULE_GROUPS } from '@/lib/modules'
import { cn } from '@/lib/utils'

type Group = (typeof MODULE_GROUPS)[number]

export function GenericGroupExperience({
  group,
  index,
  sectionRef,
}: {
  group: Group
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  return (
    <DeckSection label={group.group} index={index} sectionRef={sectionRef}>
      <FadeUpItem>
        <p className="text-sm text-[var(--muted-foreground)]">
          {String(index + 1).padStart(2, '0')} / 07
        </p>
        <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
          {group.group}
        </h2>
      </FadeUpItem>

      <div className="mt-6 flex flex-wrap gap-4" role="list">
        {group.items.map((m) => {
          const Icon = m.icon
          const disabled = m.ready === false
          const card = (
            <FadeUpItem
              className={cn(
                'group relative flex h-[220px] w-[280px] flex-col justify-between overflow-hidden rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-6 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]',
                disabled ? 'opacity-55' : 'hover:-translate-y-1.5',
              )}
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] text-[var(--foreground)]">
                <Icon className="h-6 w-6" aria-hidden="true" />
              </span>
              <div>
                <h3 className="font-display text-2xl text-[var(--foreground)]">{m.label}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">{m.description}</p>
              </div>
            </FadeUpItem>
          )
          return disabled ? (
            <div key={m.slug} role="listitem" aria-disabled>{card}</div>
          ) : (
            <Link
              key={m.slug}
              href={'/' + m.slug}
              role="listitem"
              aria-label={`${m.label} — ${m.description}`}
              className="rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
            >
              {card}
            </Link>
          )
        })}
      </div>
    </DeckSection>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/GenericGroupExperience.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/experiences/GenericGroupExperience.tsx frontend/__tests__/deck/GenericGroupExperience.test.tsx
git commit -m "feat(deck): GenericGroupExperience (repli en rangée de cartes)"
```

---

### Task 14: Navigation (`useDeckNavigation` + `DeckRail`)

**Files:**
- Create: `frontend/components/deck/useDeckNavigation.ts`
- Create: `frontend/components/deck/DeckRail.tsx`
- Test: `frontend/__tests__/deck/deckNavigation.test.tsx`

**Interfaces:**
- Produces:
  - `nextSectionIndex(current: number, key: string, total: number): number` — pure ; `ArrowDown`/`ArrowRight` → +1 borné, `ArrowUp`/`ArrowLeft` → −1 borné, autre → inchangé.
  - `useDeckNavigation(total: number): { active: number; sectionRefs: MutableRefObject<(HTMLElement | null)[]>; goTo: (i: number) => void }` — gère IntersectionObserver (section active) + clavier.
  - `DeckRail({ total, active, labels, onJump }): JSX.Element` — rail de points (`nav`), point actif `aria-current`.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/deckNavigation.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { nextSectionIndex } from '@/components/deck/useDeckNavigation'
import { DeckRail } from '@/components/deck/DeckRail'

describe('nextSectionIndex', () => {
  it('avance avec ArrowDown / ArrowRight (borné en haut)', () => {
    expect(nextSectionIndex(0, 'ArrowDown', 3)).toBe(1)
    expect(nextSectionIndex(2, 'ArrowRight', 3)).toBe(2) // borné
  })
  it('recule avec ArrowUp / ArrowLeft (borné à 0)', () => {
    expect(nextSectionIndex(1, 'ArrowUp', 3)).toBe(0)
    expect(nextSectionIndex(0, 'ArrowLeft', 3)).toBe(0) // borné
  })
  it('ignore les autres touches', () => {
    expect(nextSectionIndex(1, 'Enter', 3)).toBe(1)
  })
})

describe('DeckRail', () => {
  it('rend un point par section et marque l\'actif', () => {
    const onJump = vi.fn()
    render(<DeckRail total={3} active={1} labels={['A', 'B', 'C']} onJump={onJump} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
    expect(buttons[1]).toHaveAttribute('aria-current', 'true')
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/deckNavigation.test.tsx`
Expected: FAIL — modules introuvables.

- [ ] **Step 3: Implémenter les deux fichiers**

Create `frontend/components/deck/useDeckNavigation.ts`:

```ts
'use client'

/**
 * Navigation du Deck : section active (IntersectionObserver), saut programmé et
 * raccourcis clavier ↑↓←→. `nextSectionIndex` est pure et testée.
 */

import { useEffect, useRef, useState } from 'react'

export function nextSectionIndex(current: number, key: string, total: number): number {
  const fwd = key === 'ArrowDown' || key === 'ArrowRight'
  const back = key === 'ArrowUp' || key === 'ArrowLeft'
  if (fwd) return Math.min(current + 1, total - 1)
  if (back) return Math.max(current - 1, 0)
  return current
}

export function useDeckNavigation(total: number) {
  const sectionRefs = useRef<(HTMLElement | null)[]>([])
  const [active, setActive] = useState(0)

  const goTo = (i: number) => {
    const clamped = Math.max(0, Math.min(i, total - 1))
    sectionRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = sectionRefs.current.indexOf(e.target as HTMLElement)
            if (idx !== -1) setActive(idx)
          }
        })
      },
      { threshold: 0.5 },
    )
    sectionRefs.current.forEach((s) => s && io.observe(s))
    return () => io.disconnect()
  }, [total])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.closest('input, textarea, [contenteditable="true"]')) return
      const next = nextSectionIndex(active, e.key, total)
      if (next !== active) {
        e.preventDefault()
        goTo(next)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, total])

  return { active, sectionRefs, goTo }
}
```

Create `frontend/components/deck/DeckRail.tsx`:

```tsx
'use client'

/**
 * Rail de points latéral : indique la section courante et permet d'y sauter.
 * L'indicateur actif s'allonge (anim CSS via .springy déjà en place).
 */

import { cn } from '@/lib/utils'

export function DeckRail({
  total,
  active,
  labels,
  onJump,
}: {
  total: number
  active: number
  labels: string[]
  onJump: (i: number) => void
}) {
  return (
    <nav
      className="fixed right-4 top-1/2 z-[var(--z-sidebar)] hidden -translate-y-1/2 flex-col gap-2.5 md:flex"
      aria-label="Navigation des sections"
    >
      {Array.from({ length: total }).map((_, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onJump(i)}
          aria-current={i === active ? 'true' : undefined}
          aria-label={labels[i]}
          title={labels[i]}
          className={cn(
            'springy rounded-full',
            i === active
              ? 'h-6 w-2.5 bg-[var(--ring)]'
              : 'h-2.5 w-2.5 bg-[color-mix(in_srgb,var(--muted-foreground)_40%,transparent)] hover:bg-[var(--muted-foreground)]',
          )}
        />
      ))}
    </nav>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/deckNavigation.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/useDeckNavigation.ts frontend/components/deck/DeckRail.tsx frontend/__tests__/deck/deckNavigation.test.tsx
git commit -m "feat(deck): navigation (useDeckNavigation + DeckRail)"
```

---

### Task 15: `Deck` (coquille assemblée)

**Files:**
- Create: `frontend/components/deck/Deck.tsx`
- Test: `frontend/__tests__/deck/Deck.test.tsx`

**Interfaces:**
- Consumes: `MODULE_GROUPS`, `GROUP_ORDER` (`@/lib/modules`) ; `CorpsExperience` (Task 12) ; `GenericGroupExperience` (Task 13) ; `useDeckNavigation`, `DeckRail` (Task 14).
- Produces: `Deck({ intro? }): JSX.Element` — conteneur `.deck` (snap CSS), section intro optionnelle, une section par groupe (le groupe « Santé & Performance » → `CorpsExperience`, les autres → `GenericGroupExperience`), rail de points. Tous les hooks de données mockés dans le test.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/Deck.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(), useWaterToday: vi.fn() }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn() }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn() }))

import { useScore, useWaterToday } from '@/lib/queries/sante'
import { useEntrainementToday } from '@/lib/queries/entrainement'
import { useSkincareToday } from '@/lib/queries/skincare'
import { Deck } from '@/components/deck/Deck'
import { GROUP_ORDER } from '@/lib/modules'

beforeEach(() => {
  vi.mocked(useScore).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useScore>)
  vi.mocked(useWaterToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useWaterToday>)
  vi.mocked(useEntrainementToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useEntrainementToday>)
  vi.mocked(useSkincareToday).mockReturnValue({ data: undefined, isLoading: false, isError: true } as ReturnType<typeof useSkincareToday>)
})

describe('Deck', () => {
  it('rend une section par groupe + la section Corps', () => {
    render(
      <MotionConfig reducedMotion="always">
        <Deck />
      </MotionConfig>,
    )
    // Corps remplace l'intitulé du groupe Santé & Performance.
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
    // Les autres groupes apparaissent par leur intitulé.
    const others = GROUP_ORDER.filter((g) => g !== 'Santé & Performance')
    for (const g of others) {
      expect(screen.getByRole('region', { name: g })).toBeInTheDocument()
    }
  })

  it('affiche la section intro quand fournie', () => {
    render(
      <MotionConfig reducedMotion="always">
        <Deck intro={<p>Bonjour</p>} />
      </MotionConfig>,
    )
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/Deck.test.tsx`
Expected: FAIL — module introuvable.

- [ ] **Step 3: Implémenter**

Create `frontend/components/deck/Deck.tsx`:

```tsx
'use client'

/**
 * Le Deck (v2) — coquille d'accueil pilotée par Framer Motion. Le snap reste
 * CSS (.deck / .deck-section). Le groupe « Santé & Performance » est rendu par
 * CorpsExperience (prototype) ; les autres par GenericGroupExperience le temps
 * de leur migration. Rail de points + clavier via useDeckNavigation.
 */

import { type ReactNode } from 'react'
import { MODULE_GROUPS } from '@/lib/modules'
import { CorpsExperience } from '@/components/deck/experiences/CorpsExperience'
import { GenericGroupExperience } from '@/components/deck/experiences/GenericGroupExperience'
import { DeckRail } from '@/components/deck/DeckRail'
import { useDeckNavigation } from '@/components/deck/useDeckNavigation'

const CORPS_GROUP = 'Santé & Performance'

export function Deck({ intro }: { intro?: ReactNode }) {
  const introOffset = intro ? 1 : 0
  const total = MODULE_GROUPS.length + introOffset
  const { active, sectionRefs, goTo } = useDeckNavigation(total)

  const labels = [
    ...(intro ? ["Aujourd'hui"] : []),
    ...MODULE_GROUPS.map((g) => (g.group === CORPS_GROUP ? 'Corps' : g.group)),
  ]

  return (
    <div className="relative">
      <div className="deck no-scrollbar" aria-label="Accueil">
        {intro && (
          <section
            ref={(el) => { sectionRefs.current[0] = el }}
            className="deck-section"
            aria-label="Aujourd'hui"
          >
            <div className="mx-auto w-full max-w-[1280px] px-[max(24px,calc((100vw-1280px)/2+24px))]">
              {intro}
            </div>
          </section>
        )}

        {MODULE_GROUPS.map((group, gi) => {
          const index = gi + introOffset
          const setRef = (el: HTMLElement | null) => { sectionRefs.current[index] = el }
          return group.group === CORPS_GROUP ? (
            <CorpsExperience key={group.group} index={index} sectionRef={setRef} />
          ) : (
            <GenericGroupExperience key={group.group} group={group} index={index} sectionRef={setRef} />
          )
        })}
      </div>

      <DeckRail total={total} active={active} labels={labels} onJump={goTo} />
    </div>
  )
}
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/Deck.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/deck/Deck.tsx frontend/__tests__/deck/Deck.test.tsx
git commit -m "feat(deck): coquille Deck v2 (Corps + repli générique + rail)"
```

---

### Task 16: Bascule `page.tsx` + CSS

**Files:**
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/app/globals.css` (ajout perspective utilitaire si besoin — voir étape)
- Test: `frontend/__tests__/deck/homePage.test.tsx`

**Interfaces:**
- Consumes: `Deck` (Task 15, depuis `@/components/deck/Deck`).
- Produces: l'accueil rend le nouveau `Deck` avec l'intro `Greeting + HealthBadge + TodayPanel` inchangée.

- [ ] **Step 1: Écrire le test (échec)**

Create `frontend/__tests__/deck/homePage.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MotionConfig } from 'motion/react'

// Mocks data : on vérifie seulement que la page monte le nouveau Deck.
vi.mock('@/lib/queries/sante', () => ({ useScore: vi.fn(() => ({ isError: true })), useWaterToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/lib/queries/entrainement', () => ({ useEntrainementToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/lib/queries/skincare', () => ({ useSkincareToday: vi.fn(() => ({ isError: true })) }))
vi.mock('@/components/home/TodayPanel', () => ({ TodayPanel: () => <div>panel-aujourdhui</div> }))
vi.mock('@/components/Greeting', () => ({ Greeting: () => <div>greeting</div> }))
vi.mock('@/components/HealthBadge', () => ({ HealthBadge: () => <div>health</div> }))

import HomePage from '@/src/app/page'

describe('HomePage', () => {
  it('monte le nouveau Deck avec la section Corps et l\'intro', () => {
    render(
      <MotionConfig reducedMotion="always">
        <HomePage />
      </MotionConfig>,
    )
    expect(screen.getByText('panel-aujourdhui')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Corps' })).toBeInTheDocument()
  })
})
```

> Note : `import HomePage from '@/src/app/page'` fonctionne car l'alias `@/` pointe sur la racine `frontend/` (cf. `tsconfig.json`). Si l'import échoue, utiliser le chemin relatif `../../src/app/page`.

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/homePage.test.tsx`
Expected: FAIL — la page importe encore l'ancien `Deck` (pas de région « Corps »).

- [ ] **Step 3: Basculer `page.tsx`**

Replace `frontend/src/app/page.tsx` with:

```tsx
import { HealthBadge } from "@/components/HealthBadge";
import { Greeting } from "@/components/Greeting";
import { TodayPanel } from "@/components/home/TodayPanel";
import { Deck } from "@/components/deck/Deck";

export default function HomePage() {
  return (
    <Deck
      intro={
        <div>
          <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <Greeting />
            <HealthBadge />
          </header>
          <TodayPanel />
        </div>
      }
    />
  );
}
```

- [ ] **Step 4: Vérifier la perspective tilt (CSS)**

`TiltCard` gère sa propre perspective inline ; **aucune règle CSS supplémentaire n'est nécessaire**. Vérifier seulement que les classes `.deck`, `.deck-section` existent toujours dans `globals.css` (elles sont conservées). Aucune modification de `globals.css` si les classes sont présentes.

Run: `cd frontend && grep -nE '^\.deck(-section)? ?\{' src/app/globals.css`
Expected: les sélecteurs `.deck` et `.deck-section` sont listés. Si absent, ne pas inventer — s'arrêter et signaler (régression hors périmètre).

- [ ] **Step 5: Lancer le test (succès attendu)**

Run: `cd frontend && npx vitest run __tests__/deck/homePage.test.tsx`
Expected: PASS (1 test).

- [ ] **Step 6: Vérifier la suite + le typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: tous les tests PASS, aucune erreur TypeScript.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/page.tsx frontend/__tests__/deck/homePage.test.tsx
git commit -m "feat(deck): l'accueil monte le Deck v2 (prototype Corps actif)"
```

---

### Task 17: E2E Playwright (scroll-snap, rail, clavier, visuel Corps)

**Files:**
- Create: `frontend/e2e/deck-corps.spec.ts`

**Interfaces:**
- Consumes: l'app servie en local (backend optionnel — les modules dégradent proprement). Le test cible la coquille et la présence de la section Corps, pas les valeurs exactes.

- [ ] **Step 1: Écrire le test e2e**

Create `frontend/e2e/deck-corps.spec.ts`:

```ts
import { test, expect } from '@playwright/test'

test.describe('Deck v2 — expérience Corps', () => {
  test('la section Corps est présente et atteignable au clavier', async ({ page }) => {
    await page.goto('/')

    // Section Corps présente (région ARIA).
    const corps = page.getByRole('region', { name: 'Corps' })
    await expect(corps).toBeAttached()

    // Le rail de points existe (desktop).
    const rail = page.getByRole('navigation', { name: 'Navigation des sections' })
    await expect(rail).toBeVisible()

    // Navigation clavier : ArrowDown fait défiler vers la section suivante.
    await page.locator('body').press('ArrowDown')
    await page.waitForTimeout(600) // laisse le smooth-scroll se terminer

    // Le titre « Corps » est rendu.
    await expect(page.getByRole('heading', { name: 'Corps' })).toBeAttached()
  })

  test('capture visuelle de la section Corps', async ({ page }) => {
    await page.goto('/')
    const corps = page.getByRole('region', { name: 'Corps' })
    await corps.scrollIntoViewIfNeeded()
    await page.waitForTimeout(800) // entrées + count-up terminés
    await expect(corps).toHaveScreenshot('corps-section.png', { maxDiffPixelRatio: 0.02 })
  })
})
```

- [ ] **Step 2: Générer la capture de référence + lancer**

Run: `cd frontend && npx playwright test e2e/deck-corps.spec.ts --update-snapshots`
Expected: 1er run crée `corps-section.png` (référence) ; les deux tests PASS.

- [ ] **Step 3: Re-lancer pour confirmer la stabilité**

Run: `cd frontend && npx playwright test e2e/deck-corps.spec.ts`
Expected: les deux tests PASS (capture stable sous le seuil `maxDiffPixelRatio`).

> Si la capture est instable à cause des animations, relancer en ajoutant un état « repos » : la section est capturée après `waitForTimeout(800)` ; augmenter à 1200 ms si nécessaire. Ne pas désactiver le test.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/deck-corps.spec.ts frontend/e2e/deck-corps.spec.ts-snapshots
git commit -m "test(deck): e2e Corps (snap, rail, clavier, capture visuelle)"
```

---

## Self-Review

**1. Spec coverage :**
- Stack `motion` + frontière snap CSS → Task 1, 15, 16. ✓
- Count-up `tabular-nums` → Task 2, appliqué Tasks 7/8/9/11. ✓
- Variants stagger / entrée qui « fond » → Task 3, 6. ✓
- Parallax souris héros → Task 4, 7. ✓
- Tilt 3D ≤ ±4° + inertie spring → Task 5, appliqué satellites 8/9/10/11. ✓
- `DeckSection` orchestration → Task 6. ✓
- 5 modules Corps (Score héros, Sommeil, Macros+hydratation, Séance, Skincare) → Tasks 7–11. ✓
- `CorpsExperience` mise en page éditoriale → Task 12. ✓
- Migration progressive (repli autres groupes) → Task 13, 15. ✓
- Navigation rail + clavier → Task 14. ✓
- Coquille Deck → Task 15 ; bascule page → Task 16. ✓
- reduced-motion (fondus, pas de parallax/3D/count-up) → géré dans chaque hook/composant (`useReducedMotion`, `MotionConfig` en test) ; Tasks 2/4/5. ✓
- Aucun nouvel endpoint → tous les modules consomment des hooks existants. ✓
- Tests : Vitest unités + RTL + Playwright e2e/visuel → toutes les tasks + Task 17. ✓

**2. Placeholder scan :** aucun TBD/TODO ; chaque étape de code contient le code complet ; chaque étape de test contient le test complet. ✓

**3. Type consistency :**
- `springs.{soft,countUp,tilt}` définis Task 1, consommés Tasks 2/3/4/5. ✓
- `AnimatedNumber({ value, format?, className? })` Task 2, appelé Tasks 7/8. ✓
- `computeParallax(clientX, clientY, rect, strength)` / `useParallax(strength)` Task 4, appelé Task 7. ✓
- `computeTilt(...)` / `MAX_TILT_DEG` / `TiltCard({ children, className })` Task 5, appelé Tasks 8/9/10/11. ✓
- `DeckSection({ children, label, index, sectionRef })` + `FadeUpItem` Task 6, consommés Tasks 12/13. ✓
- `ScoreDay.details` champs (`kcal_consommees`, `kcal_cible`, `sommeil_h`) — conformes à `lib/sante.ts`. ✓
- `nextSectionIndex` / `useDeckNavigation` / `DeckRail({ total, active, labels, onJump })` Task 14, consommés Task 15. ✓
- `Deck({ intro? })` Task 15, consommé Task 16. ✓

Aucune incohérence détectée.

## Hors périmètre (rappel)

- Migration des 6 autres expériences de domaine (après validation du prototype).
- Suppression de l'ancien `components/layout/Deck.tsx` (à faire une fois toutes les expériences migrées).
- Nouveaux endpoints / changements backend.
