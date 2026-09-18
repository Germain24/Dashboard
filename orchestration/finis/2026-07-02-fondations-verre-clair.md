# Fondations Verre Clair — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer les fondations « quiet luxury » du design system Verre Clair : grain papier, teinte d'accent par module, recettes de verre uniques, contraste AA testé, EmptyState éditorial, skeletons géométriques (spec : `orchestration/a-faire/2026-07-02-fondations-verre-clair-design.md`).

**Architecture:** Token-first — tout le CSS nouveau vit dans `frontend/src/app/globals.css` (tokens + recettes `.glass-*`), les primitives `components/ui/` consomment ces classes, et les invariants (contraste WCAG, unicité des recettes) sont des tests vitest. Les maths couleur sont des fonctions pures dans `lib/design/contrast.ts`.

**Tech Stack:** Next.js 15 + Tailwind v4 (`@theme inline`), vitest + @testing-library/react, TypeScript.

## Global Constraints

- Commandes depuis `frontend/` : `npx vitest run <chemins>`, `npx tsc --noEmit`.
- **Aucune couleur nouvelle** : palette DESIGN.md uniquement — marine `#04142c`, laiton `#C5A059`, vert anglais `#536252`, oxblood `#501312`, slate `#384762`, ocre `#8a6d1f`.
- Grain ≤ 3 % d'opacité ; teinte module ≤ 10 % (clair) / ≤ 12 % (sombre).
- API publiques inchangées : `EmptyState(icon?, title, description?, action?, className?)`, `Skeleton`/`SkeletonCard`/`SkeletonTable` existants conservés.
- Pas de nouvelle dépendance npm. Pas d'illustrations dans EmptyState.
- Les DEUX blocs sombres de globals.css (media query `prefers-color-scheme` et `[data-theme="dark"]`) doivent rester identiques — toute modif de token sombre se fait dans les deux.
- Stager UNIQUEMENT les fichiers de chaque tâche (jamais `git add -A`/`.`).

---

## Task 1: Maths couleur pures (`lib/design/contrast.ts`)

**Files:**
- Create: `frontend/lib/design/contrast.ts`
- Test: `frontend/__tests__/design/contrast-lib.test.ts`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `type Rgba = { r: number; g: number; b: number; a: number }` (canaux 0-255, alpha 0-1)
  - `parseCssColor(value: string): Rgba | null` (hex 3/6, `rgb(r g b / a)`, `rgb(r g b)`, `transparent`)
  - `composite(fg: Rgba, bg: Rgba): Rgba` (fg sur bg, résultat opaque)
  - `contrastRatio(a: Rgba, b: Rgba): number` (WCAG 2.x, couleurs supposées opaques)

- [ ] **Step 1: Write the failing test**

```ts
// frontend/__tests__/design/contrast-lib.test.ts
import { describe, it, expect } from "vitest";
import { parseCssColor, composite, contrastRatio } from "@/lib/design/contrast";

describe("parseCssColor", () => {
  it("parse hex 6", () => {
    expect(parseCssColor("#04142c")).toEqual({ r: 4, g: 20, b: 44, a: 1 });
  });
  it("parse hex 3", () => {
    expect(parseCssColor("#fff")).toEqual({ r: 255, g: 255, b: 255, a: 1 });
  });
  it("parse rgb moderne avec alpha", () => {
    expect(parseCssColor("rgb(255 255 255 / 0.72)")).toEqual({ r: 255, g: 255, b: 255, a: 0.72 });
  });
  it("parse rgb moderne sans alpha", () => {
    expect(parseCssColor("rgb(4 20 44)")).toEqual({ r: 4, g: 20, b: 44, a: 1 });
  });
  it("parse transparent", () => {
    expect(parseCssColor("transparent")).toEqual({ r: 0, g: 0, b: 0, a: 0 });
  });
  it("rejette l'invalide", () => {
    expect(parseCssColor("var(--foo)")).toBeNull();
  });
});

describe("composite", () => {
  it("alpha 1 = premier plan", () => {
    const fg = { r: 10, g: 20, b: 30, a: 1 };
    expect(composite(fg, { r: 255, g: 255, b: 255, a: 1 })).toEqual({ ...fg, a: 1 });
  });
  it("alpha 0.5 = moyenne", () => {
    const out = composite({ r: 0, g: 0, b: 0, a: 0.5 }, { r: 255, g: 255, b: 255, a: 1 });
    expect(out.r).toBeCloseTo(127.5, 0);
    expect(out.a).toBe(1);
  });
});

describe("contrastRatio", () => {
  it("noir sur blanc = 21", () => {
    const black = { r: 0, g: 0, b: 0, a: 1 };
    const white = { r: 255, g: 255, b: 255, a: 1 };
    expect(contrastRatio(black, white)).toBeCloseTo(21, 1);
  });
  it("symétrique", () => {
    const a = { r: 4, g: 20, b: 44, a: 1 };
    const b = { r: 250, g: 249, b: 245, a: 1 };
    expect(contrastRatio(a, b)).toBeCloseTo(contrastRatio(b, a), 6);
  });
  it("encre sur papier crème > 15", () => {
    // --foreground #1b1c1a sur --background #faf9f5
    const ink = { r: 27, g: 28, b: 26, a: 1 };
    const paper = { r: 250, g: 249, b: 245, a: 1 };
    expect(contrastRatio(ink, paper)).toBeGreaterThan(15);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (depuis `frontend/`): `npx vitest run __tests__/design/contrast-lib.test.ts`
Expected: FAIL — `Cannot find module '@/lib/design/contrast'`.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/lib/design/contrast.ts
/**
 * Maths couleur pures pour l'audit de contraste WCAG des tokens Verre Clair.
 * Formats supportés = ceux réellement présents dans globals.css :
 * hex 3/6, `rgb(r g b / a)` moderne, `transparent`.
 */

export type Rgba = { r: number; g: number; b: number; a: number };

export function parseCssColor(value: string): Rgba | null {
  const v = value.trim();
  if (v === "transparent") return { r: 0, g: 0, b: 0, a: 0 };

  const hex = v.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
      a: 1,
    };
  }

  const rgb = v.match(
    /^rgba?\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*([\d.]+%?)\s*)?\)$/i,
  );
  if (rgb) {
    let a = 1;
    if (rgb[4] !== undefined) {
      a = rgb[4].endsWith("%") ? parseFloat(rgb[4]) / 100 : parseFloat(rgb[4]);
    }
    return { r: +rgb[1], g: +rgb[2], b: +rgb[3], a };
  }
  return null;
}

export function composite(fg: Rgba, bg: Rgba): Rgba {
  const a = fg.a + bg.a * (1 - fg.a);
  const mix = (f: number, b: number) =>
    a === 0 ? 0 : (f * fg.a + b * bg.a * (1 - fg.a)) / a;
  return { r: mix(fg.r, bg.r), g: mix(fg.g, bg.g), b: mix(fg.b, bg.b), a };
}

function luminance(c: Rgba): number {
  const lin = (ch: number) => {
    const s = ch / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
}

export function contrastRatio(a: Rgba, b: Rgba): number {
  const l1 = luminance(a);
  const l2 = luminance(b);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/design/contrast-lib.test.ts`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/design/contrast.ts frontend/__tests__/design/contrast-lib.test.ts
git commit -m "feat(design): maths couleur pures pour l'audit de contraste WCAG"
```

---

## Task 2: Audit de contraste AA des tokens (test + corrections)

**Files:**
- Create: `frontend/__tests__/design/contrast-tokens.test.ts`
- Modify: `frontend/src/app/globals.css` (uniquement si des paires échouent)

**Interfaces:**
- Consumes: `parseCssColor`, `composite`, `contrastRatio` (Task 1).
- Produces: invariant CI — toutes les paires AA passent dans les deux thèmes ; les deux blocs sombres de globals.css sont identiques.

- [ ] **Step 1: Write the test**

```ts
// frontend/__tests__/design/contrast-tokens.test.ts
/**
 * Contraste AA des tokens Verre Clair (les deux thèmes).
 * Le CSS est parsé depuis globals.css : le design system est testé
 * à la source, pas via un rendu.
 */
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { parseCssColor, composite, contrastRatio, type Rgba } from "@/lib/design/contrast";

const css = fs.readFileSync(
  path.resolve(__dirname, "../../src/app/globals.css"),
  "utf8",
);

/** Extrait les déclarations `--x: valeur;` du bloc qui suit `selector {`. */
function tokensOf(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start === -1) throw new Error(`bloc introuvable: ${selector}`);
  const open = css.indexOf("{", start);
  let depth = 1;
  let i = open + 1;
  while (depth > 0 && i < css.length) {
    if (css[i] === "{") depth++;
    if (css[i] === "}") depth--;
    i++;
  }
  const body = css.slice(open + 1, i - 1);
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

const light = tokensOf(":root {");
const darkExplicit = tokensOf(':root[data-theme="dark"]');
const darkAuto = tokensOf(':root:not([data-theme="light"])');

function color(tokens: Record<string, string>, name: string): Rgba {
  const raw = tokens[name] ?? light[name]; // le sombre hérite du clair s'il ne surcharge pas
  const c = raw ? parseCssColor(raw) : null;
  if (!c) throw new Error(`token non couleur: ${name} = ${raw}`);
  return c;
}

/** Compose une couleur (éventuellement alpha) sur le fond du thème. */
function onBg(tokens: Record<string, string>, name: string): Rgba {
  return composite(color(tokens, name), color(tokens, "--background"));
}

const themes: Array<[string, Record<string, string>]> = [
  ["clair", light],
  ["sombre", darkExplicit],
];

describe("les deux blocs sombres sont identiques", () => {
  it("media query dark === data-theme dark", () => {
    expect(darkAuto).toEqual(darkExplicit);
  });
});

describe.each(themes)("thème %s — texte >= 4.5:1", (_name, t) => {
  const bg = color(t, "--background");
  const card = onBg(t, "--card");

  it("foreground / background", () => {
    expect(contrastRatio(color(t, "--foreground"), bg)).toBeGreaterThanOrEqual(4.5);
  });
  it("foreground / card composité", () => {
    expect(contrastRatio(color(t, "--foreground"), card)).toBeGreaterThanOrEqual(4.5);
  });
  it("muted-foreground / background", () => {
    expect(contrastRatio(color(t, "--muted-foreground"), bg)).toBeGreaterThanOrEqual(4.5);
  });
  it("muted-foreground / card composité", () => {
    expect(contrastRatio(color(t, "--muted-foreground"), card)).toBeGreaterThanOrEqual(4.5);
  });
  it("primary-foreground / primary", () => {
    expect(
      contrastRatio(color(t, "--primary-foreground"), composite(color(t, "--primary"), bg)),
    ).toBeGreaterThanOrEqual(4.5);
  });
  it.each(["success", "warning", "destructive", "info", "tertiary"])(
    "%s-foreground / %s-muted composité",
    (sem) => {
      const fg = color(t, `--${sem}-foreground`);
      const surface = composite(color(t, `--${sem}-muted`), bg);
      expect(contrastRatio(fg, surface)).toBeGreaterThanOrEqual(4.5);
    },
  );
  it("nav-active-fg / lavis nav composité (ring 10% sur background)", () => {
    const ring = color(t, "--ring");
    const wash = composite({ ...ring, a: 0.1 }, bg);
    expect(contrastRatio(color(t, "--nav-active-fg"), wash)).toBeGreaterThanOrEqual(4.5);
  });
});

describe.each(themes)("thème %s — UI >= 3:1", (_name, t) => {
  const bg = color(t, "--background");
  it("ring / background", () => {
    expect(contrastRatio(color(t, "--ring"), bg)).toBeGreaterThanOrEqual(3.0);
  });
});
```

- [ ] **Step 2: Run the test — inventorier les échecs**

Run: `npx vitest run __tests__/design/contrast-tokens.test.ts`
Expected: le test des blocs sombres identiques PASSE (ils le sont aujourd'hui, à l'espace près — si échec, aligner les blocs AVANT toute autre correction). Certaines paires sémantiques peuvent échouer (candidats connus : `--warning-foreground`/`--warning-muted`, `--tertiary-foreground`/`--tertiary-muted` en sombre). Noter chaque paire en échec avec son ratio.

- [ ] **Step 3: Corriger les tokens en écart (teinte conservée)**

Pour CHAQUE paire en échec, appliquer cette procédure déterministe dans `globals.css` :
1. Ne toucher que le token `*-foreground` de la paire (le fond `*-muted` définit l'ambiance, le texte porte la lisibilité).
2. En thème clair : assombrir le foreground par pas de ~8 % (multiplier chaque canal RGB par 0.92, arrondi) jusqu'à ratio ≥ 4.5. En sombre : éclaircir par pas de ~8 % (canal + (255-canal)×0.08).
3. Reporter la valeur À L'IDENTIQUE dans les DEUX blocs sombres si c'est un token sombre.
4. Re-run le test après chaque correction.

Si aucune paire n'échoue : ne rien modifier, passer au Step 4.

- [ ] **Step 4: Run full verification**

Run: `npx vitest run __tests__/design/`
Expected: PASS (lib + tokens).
Run: `npx vitest run` puis `npx tsc --noEmit`
Expected: suite complète verte, 0 erreur TS.

- [ ] **Step 5: Commit**

```bash
git add frontend/__tests__/design/contrast-tokens.test.ts frontend/src/app/globals.css
git commit -m "feat(design): contraste AA des tokens verifie par test (2 themes) + corrections"
```

(Si globals.css n'a pas changé, ne stager que le test.)

---

## Task 3: Grain papier (globals.css)

**Files:**
- Modify: `frontend/src/app/globals.css`

**Interfaces:**
- Consumes: blocs de tokens existants.
- Produces: token `--grain-opacity` (les 3 blocs), `body::after` grain.

- [ ] **Step 1: Ajouter le token dans les trois blocs**

Dans `:root {` (bloc clair), après la ligne `--background-subtle: #f4f4f0;` :

```css
  /* ── Grain papier (texture SVG inline, statique) ───────── */
  --grain-opacity: 0.025;
```

Dans le bloc `@media (prefers-color-scheme: dark)` → `:root:not([data-theme="light"])`, après `--background-subtle: #111a2a;` :

```css
    --grain-opacity: 0.02;
```

Dans le bloc `:root[data-theme="dark"]`, après `--background-subtle: #111a2a;` :

```css
  --grain-opacity: 0.02;
```

- [ ] **Step 2: Ajouter le grain `body::after`**

Dans globals.css, juste après le bloc `@keyframes washDrift { ... }` :

```css
/* Grain papier : bruit SVG inline (feTurbulence), statique, au-dessus des
   lavis mais sous le contenu. La matière de l'almanach — jamais > 3 %. */
body::after {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  opacity: var(--grain-opacity);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-repeat: repeat;
}
```

- [ ] **Step 3: Verify**

Run: `npx vitest run __tests__/design/` — Expected: PASS (le grain n'affecte pas les tokens couleur ; le test « blocs sombres identiques » confirme que `--grain-opacity: 0.02` est bien dans les DEUX blocs sombres).
Run (garde d'unicité) : `grep -c "body::after" frontend/src/app/globals.css` — Expected: `1`.
Contrôle visuel (si l'app tourne) : texture perceptible en s'approchant, invisible de loin, dans les deux thèmes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(design): grain papier SVG statique (--grain-opacity, body::after)"
```

---

## Task 4: Teinte d'accent par module

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/components/layout/MainShell.tsx`
- Test: `frontend/__tests__/components/main-shell-module.test.tsx` (créer)

**Interfaces:**
- Consumes: `usePathname` (déjà utilisé par MainShell).
- Produces: `body[data-module="<segment>"]` posé à chaque navigation ; tokens `--tint-finance|corps|quotidien|savoir|loisirs` ; 4ᵉ lavis `var(--wash-module)`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/components/main-shell-module.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { MainShell } from "@/components/layout/MainShell";

const usePathname = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => usePathname() }));

afterEach(() => {
  cleanup();
  delete document.body.dataset.module;
});

describe("MainShell — data-module sur <body>", () => {
  it("pose le premier segment du pathname", () => {
    usePathname.mockReturnValue("/finance/positions");
    render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBe("finance");
  });

  it("retire l'attribut sur l'accueil", () => {
    usePathname.mockReturnValue("/garderobe");
    const { unmount } = render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBe("garderobe");
    unmount();
    usePathname.mockReturnValue("/");
    render(<MainShell>x</MainShell>);
    expect(document.body.dataset.module).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/components/main-shell-module.test.tsx`
Expected: FAIL — `data-module` jamais posé (`expected undefined to be 'finance'`).

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/components/layout/MainShell.tsx`, remplacer le contenu par :

```tsx
'use client'

/**
 * Enveloppe du contenu principal (desktop).
 *
 * - Accueil (le Deck) : plein écran, scroll interne, aucun padding.
 * - Pages module : on réserve un espace en bas pour que le Dock flottant ne
 *   masque jamais la dernière ligne de contenu.
 * - Pose `data-module` sur <body> : le lavis d'accent du module (globals.css)
 *   vit sur body::before, hors de portée d'un sélecteur depuis <main>.
 */

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

export function MainShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const onHome = pathname === '/'

  useEffect(() => {
    const segment = pathname.split('/')[1] ?? ''
    if (segment) document.body.dataset.module = segment
    else delete document.body.dataset.module
  }, [pathname])

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className={cn('flex-1 min-w-0 focus:outline-none', !onHome && 'pb-24 md:pb-28')}
    >
      {children}
    </main>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/components/main-shell-module.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 5: CSS — tokens de teinte + 4ᵉ lavis + table des modules**

Dans `frontend/src/app/globals.css` :

(a) Dans `:root {` (clair), après le bloc des lavis (`--wash-3: ...;`) :

```css
  /* Lavis d'accent par module (catégories du Deck) — repère spatial subtil. */
  --wash-module: transparent;
  --tint-finance: rgb(4 20 44 / 0.08);
  --tint-corps: rgb(83 98 82 / 0.07);
  --tint-quotidien: rgb(138 109 31 / 0.07);
  --tint-savoir: rgb(80 19 18 / 0.06);
  --tint-loisirs: rgb(56 71 98 / 0.08);
```

(b) Dans les DEUX blocs sombres, après leurs `--wash-3: ...;` respectifs (mêmes valeurs dans les deux) :

```css
    --tint-finance: rgb(56 71 98 / 0.12);
    --tint-corps: rgb(83 98 82 / 0.10);
    --tint-quotidien: rgb(197 160 89 / 0.09);
    --tint-savoir: rgb(80 19 18 / 0.10);
    --tint-loisirs: rgb(56 71 98 / 0.12);
```

(c) Dans `body::before`, ajouter un 4ᵉ gradient À LA FIN de la liste `background:` (après le 3ᵉ `radial-gradient(...)`, séparé par une virgule) :

```css
    radial-gradient(900px 600px at 50% -10%, var(--wash-module), transparent 60%)
```

(d) Après le bloc `@keyframes washDrift` (et le `body::after` du grain, Task 3), la table de mapping :

```css
/* Catégorie -> teinte. Les segments hors table gardent les lavis de base. */
body[data-module="finance"],
body[data-module="patrimoine"],
body[data-module="budget"] { --wash-module: var(--tint-finance); }

body[data-module="sante"],
body[data-module="entrainement"],
body[data-module="score"],
body[data-module="skincare"],
body[data-module="garderobe"] { --wash-module: var(--tint-corps); }

body[data-module="cuisine"],
body[data-module="routines"],
body[data-module="agenda"],
body[data-module="habitudes"] { --wash-module: var(--tint-quotidien); }

body[data-module="etudes"],
body[data-module="travail"],
body[data-module="jobs"],
body[data-module="langues"],
body[data-module="documents"],
body[data-module="livres"] { --wash-module: var(--tint-savoir); }

body[data-module="musique"],
body[data-module="film"],
body[data-module="series"],
body[data-module="gaming"],
body[data-module="voyage"],
body[data-module="journal"] { --wash-module: var(--tint-loisirs); }
```

- [ ] **Step 6: Full verification**

Run: `npx vitest run __tests__/design/ __tests__/components/main-shell-module.test.tsx`
Expected: PASS — dont « blocs sombres identiques » (les `--tint-*` sombres doivent être copiés à l'identique dans les deux blocs).
Run: `npx tsc --noEmit` — Expected: 0 erreur.
Contrôle visuel : naviguer finance → garderobe → cuisine, le lavis haut-centre change de nuance discrètement.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/globals.css frontend/components/layout/MainShell.tsx frontend/__tests__/components/main-shell-module.test.tsx
git commit -m "feat(design): lavis d'accent par module (data-module + --wash-module)"
```

---

## Task 5: Recettes de verre + migration des primitives ui/

**Files:**
- Modify: `frontend/src/app/globals.css` (recettes `.glass-card`, `.glass-veil`, `.glass-inset`)
- Modify: `frontend/components/ui/card.tsx`, `stat-card.tsx`, `chart-frame.tsx`, `tabs.tsx`, `dialog.tsx`

**Interfaces:**
- Consumes: tokens verre existants (`--card`, `--glass-border`, `--glass-highlight`, `--glass-blur`, `--field`, `--shadow`).
- Produces: classes globales `.glass-card`, `.glass-veil`, `.glass-inset` (utilisées aussi par Task 6).

- [ ] **Step 1: Ajouter les recettes dans globals.css**

Juste après le bloc `.glass-modal { ... }` :

```css
.glass-card {
  background: var(--card);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(1.4);
  backdrop-filter: blur(var(--glass-blur)) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: inset 0 1px 0 0 var(--glass-highlight), var(--shadow);
}
/* Voile d'overlay (dialogs, palette, menus) — le fond reste deviné. */
.glass-veil {
  background: rgb(0 0 0 / 0.3);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}
/* Surface encastrée (rail d'onglets, champs) : le creux, pas le relief. */
.glass-inset {
  background: var(--field);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(1.4);
  backdrop-filter: blur(var(--glass-blur)) saturate(1.4);
}
```

- [ ] **Step 2: Migrer les 5 primitives**

`components/ui/card.tsx` — remplacer les trois lignes de classes du `<div>` de `Card` :

```tsx
      // Verre clair : recette .glass-card (globals.css) — fond translucide,
      // blur, liseré supérieur lumineux, ombre lithographique.
      "glass-card rounded-[var(--radius-lg)] text-[var(--card-foreground)]",
```

(supprimer les lignes `"rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] text-[var(--card-foreground)]"`, `"backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4]"` et `"shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]"`).

`components/ui/stat-card.tsx:42` — remplacer :

```tsx
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] p-5 card-hover space-y-1">
```

par :

```tsx
    <div className="glass-card rounded-[var(--radius-lg)] p-5 card-hover space-y-1">
```

`components/ui/chart-frame.tsx` — remplacer les trois lignes de classes :

```tsx
        "glass-card rounded-[var(--radius-lg)] p-5",
```

`components/ui/tabs.tsx` (TabsList) — remplacer les trois lignes du rail :

```tsx
        // Contrôle segmenté en verre : rail encastré (.glass-inset),
        // l'actif est une pastille soulevée.
        "flex w-fit max-w-full gap-1 overflow-x-auto rounded-[var(--radius-full)]",
        "glass-inset border border-[var(--glass-border)] p-1",
```

`components/ui/dialog.tsx` — le backdrop `motion.div` : remplacer `className="absolute inset-0 bg-black/30 backdrop-blur-[6px]"` par `className="glass-veil absolute inset-0"`.

- [ ] **Step 3: Verify**

Run: `npx vitest run` — Expected: suite verte (les tests existants de badge/dialog/tabs ne testent pas ces classes ; si un snapshot de classes casse, le mettre à jour — le rendu visé est identique).
Run: `npx tsc --noEmit` — Expected: 0 erreur.
Run: `grep -rn "backdrop-blur\|backdrop-saturate" frontend/components/ui/ --include="*.tsx"` — Expected: 0 résultat.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css frontend/components/ui/card.tsx frontend/components/ui/stat-card.tsx frontend/components/ui/chart-frame.tsx frontend/components/ui/tabs.tsx frontend/components/ui/dialog.tsx
git commit -m "feat(design): recettes .glass-card/.glass-veil/.glass-inset + migration des primitives ui"
```

---

## Task 6: Migration verre — reste de l'app + garde anti-régression

**Files:**
- Modify: `frontend/components/CommandPalette.tsx:233`, `frontend/components/MobileNav.tsx:83`, `frontend/components/documents/DocumentsTab.tsx:47`, `frontend/src/app/routines/page.tsx:97,397`, `frontend/components/deck/experiences/GenericGroupExperience.tsx:43`, `frontend/components/deck/modules/MacrosModule.tsx:36`, `NextWorkoutModule.tsx:26`, `SkincareModule.tsx:24`, `SleepModule.tsx:31`, `frontend/components/layout/Deck.tsx:105`
- Test: `frontend/__tests__/design/glass-recipes.test.ts` (créer)

**Interfaces:**
- Consumes: `.glass-card`, `.glass-veil`, `.glass-panel` (Task 5 / existant).
- Produces: invariant CI — aucun `backdrop-blur`/`backdrop-filter` ad hoc dans les .tsx.

- [ ] **Step 1: Write the failing test (la garde)**

```ts
// frontend/__tests__/design/glass-recipes.test.ts
/**
 * Garde : la matière verre passe par les recettes .glass-* de globals.css.
 * Aucun backdrop-filter ad hoc dans les composants.
 */
import { describe, it, expect } from "vitest";
import { execSync } from "node:child_process";
import path from "node:path";

const frontendRoot = path.resolve(__dirname, "../..");

it("aucun backdrop-blur/saturate ad hoc dans les .tsx", () => {
  let out = "";
  try {
    out = execSync(
      'git grep -n "backdrop-blur\\|backdrop-saturate\\|backdrop-filter" -- "components/**/*.tsx" "src/**/*.tsx"',
      { cwd: frontendRoot, encoding: "utf8" },
    );
  } catch {
    out = ""; // git grep sort en code 1 quand zéro correspondance : c'est le succès
  }
  expect(out.trim(), `verre ad hoc trouvé:\n${out}`).toBe("");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/design/glass-recipes.test.ts`
Expected: FAIL — liste les ~10 fichiers restants.

- [ ] **Step 3: Migrer chaque usage**

Voiles (remplacements de classes, le reste de la ligne inchangé) :
- `CommandPalette.tsx:233` : `bg-black/30 backdrop-blur-[6px]` → `glass-veil`
- `MobileNav.tsx:83` : `bg-black/50 backdrop-blur-sm` → `glass-veil`
- `DocumentsTab.tsx:47` : `bg-black/40 backdrop-blur-sm` → `glass-veil`
- `routines/page.tsx:97` : `bg-black/40 ... backdrop-blur-sm` → `glass-veil ...` (retirer les deux fragments, ajouter `glass-veil`)

Cartes (la chaîne `border border-[var(--glass-border)] bg-[var(--card)] ... backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]` → `glass-card`, en CONSERVANT les classes de layout — rounded, padding, flex, h/w, focus-visible…) :
- `GenericGroupExperience.tsx:43`
- `MacrosModule.tsx:36`, `NextWorkoutModule.tsx:26`, `SkincareModule.tsx:24`, `SleepModule.tsx:31`
- `routines/page.tsx:397` : `border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)]` → `glass-card` (attention : c'est la branche d'un ternaire — garder la structure du ternaire)

Chrome :
- `layout/Deck.tsx:105` : `'backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.8]',` → `'glass-panel',` — si la ligne voisine pose déjà un `bg-[var(--glass)]`, la retirer (le fond est dans la recette).

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run __tests__/design/glass-recipes.test.ts`
Expected: PASS.
Run: `npx vitest run` puis `npx tsc --noEmit` — Expected: tout vert.
Contrôle visuel : dialogs, palette ⌘K, deck — même matière qu'avant (recette équivalente).

- [ ] **Step 5: Commit**

```bash
git add frontend/__tests__/design/glass-recipes.test.ts frontend/components/CommandPalette.tsx frontend/components/MobileNav.tsx frontend/components/documents/DocumentsTab.tsx frontend/src/app/routines/page.tsx frontend/components/deck/experiences/GenericGroupExperience.tsx frontend/components/deck/modules/MacrosModule.tsx frontend/components/deck/modules/NextWorkoutModule.tsx frontend/components/deck/modules/SkincareModule.tsx frontend/components/deck/modules/SleepModule.tsx frontend/components/layout/Deck.tsx
git commit -m "refactor(design): tout le verre passe par les recettes .glass-* (garde CI)"
```

---

## Task 7: EmptyState éditorial

**Files:**
- Modify: `frontend/components/ui/empty-state.tsx`
- Test: `frontend/__tests__/components/empty-state.test.tsx` (créer)

**Interfaces:**
- Consumes: `--warning` (laiton/ocre), `font-display` (globals.css).
- Produces: même API `EmptyState({ icon?, title, description?, action?, className? })` — 19 usages existants intacts.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/components/empty-state.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState éditorial", () => {
  it("titre en serif italique (voix de l'almanach)", () => {
    render(<EmptyState title="Aucune tenue" />);
    const title = screen.getByText("Aucune tenue");
    expect(title.className).toContain("font-display");
    expect(title.className).toContain("italic");
  });

  it("ornement laiton entre titre et description", () => {
    render(<EmptyState title="Vide" description="Ajoute une pièce." />);
    expect(screen.getByTestId("empty-ornament")).toBeInTheDocument();
    expect(screen.getByText("Ajoute une pièce.")).toBeInTheDocument();
  });

  it("action et icône rendues", () => {
    render(
      <EmptyState title="Vide" icon={<svg data-testid="ic" />} action={<button>Créer</button>} />,
    );
    expect(screen.getByTestId("ic")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/components/empty-state.test.tsx`
Expected: FAIL — `font-display` absent du titre, `empty-ornament` introuvable.

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `frontend/components/ui/empty-state.tsx` par :

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * État vide éditorial : la typographie de l'almanach (serif italique) et un
 * fin ornement laiton — pas d'illustration. Un état vide premium est ce qui
 * distingue une app finie.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-[var(--radius-lg)]",
        "border border-dashed border-[var(--border)] bg-[var(--field)] px-6 py-16 text-center",
        className,
      )}
    >
      {icon && (
        <span className="text-[var(--muted-foreground)] opacity-40">{icon}</span>
      )}
      <p className="font-display italic text-lg text-[var(--foreground)] [text-wrap:balance]">
        {title}
      </p>
      <span
        data-testid="empty-ornament"
        aria-hidden
        className="h-px w-10 bg-[var(--warning)] opacity-60"
      />
      {description && (
        <p className="text-[15px] leading-relaxed text-[var(--muted-foreground)] max-w-xs">
          {description}
        </p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run __tests__/components/empty-state.test.tsx`
Expected: PASS (3 passed).
Run: `npx vitest run` puis `npx tsc --noEmit` — Expected: tout vert (API inchangée, 19 usages intacts).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/empty-state.tsx frontend/__tests__/components/empty-state.test.tsx
git commit -m "feat(design): EmptyState editorial (serif italique + ornement laiton)"
```

---

## Task 8: Blocs skeleton composables + PageSkeleton géométrique

**Files:**
- Modify: `frontend/components/ui/skeleton.tsx` (ajouts — `Skeleton`, `SkeletonCard`, `SkeletonTable` existants conservés)
- Modify: `frontend/components/PageSkeleton.tsx`
- Test: `frontend/__tests__/components/skeleton-blocks.test.tsx` (créer)

**Interfaces:**
- Consumes: `Skeleton` existant, `.skeleton-shimmer` (globals.css).
- Produces:
  - `SkeletonHeader()` — géométrie ModuleHeader (titre serif + sous-titre)
  - `SkeletonStatRow({ count = 3 })` — rangée de stat-cards
  - `SkeletonCardGrid({ count = 6, cols = 3 })` — grille de cartes (cols ∈ 2|3|4)
  - `SkeletonList({ rows = 5 })` — lignes hautes (agenda, listes)
  - Ces exports sont consommés par les `loading.tsx` de Task 9.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/__tests__/components/skeleton-blocks.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import {
  SkeletonHeader,
  SkeletonStatRow,
  SkeletonCardGrid,
  SkeletonList,
} from "@/components/ui/skeleton";
import PageSkeleton from "@/components/PageSkeleton";

describe("blocs skeleton", () => {
  it("SkeletonStatRow rend n cartes", () => {
    const { container } = render(<SkeletonStatRow count={4} />);
    expect(container.querySelectorAll("[data-skeleton='stat']")).toHaveLength(4);
  });

  it("SkeletonCardGrid rend n cartes", () => {
    const { container } = render(<SkeletonCardGrid count={8} cols={4} />);
    expect(container.querySelectorAll("[data-skeleton='card']")).toHaveLength(8);
  });

  it("SkeletonList rend n lignes", () => {
    const { container } = render(<SkeletonList rows={6} />);
    expect(container.querySelectorAll("[data-skeleton='row']")).toHaveLength(6);
  });

  it("SkeletonHeader rend titre + sous-titre", () => {
    const { container } = render(<SkeletonHeader />);
    expect(container.querySelectorAll(".skeleton-shimmer").length).toBeGreaterThanOrEqual(2);
  });

  it("PageSkeleton = header + stats + grille", () => {
    const { container } = render(<PageSkeleton />);
    expect(container.querySelectorAll("[data-skeleton='stat']")).toHaveLength(3);
    expect(container.querySelectorAll("[data-skeleton='card']")).toHaveLength(6);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run __tests__/components/skeleton-blocks.test.tsx`
Expected: FAIL — `SkeletonHeader` (et les autres) non exportés.

- [ ] **Step 3: Write minimal implementation**

Ajouter À LA FIN de `frontend/components/ui/skeleton.tsx` (sans toucher à l'existant) :

```tsx
/** Géométrie du ModuleHeader : titre display + sous-titre. */
export function SkeletonHeader() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-72" />
    </div>
  )
}

/** Rangée de stat-cards (géométrie StatCard : ~96px de haut). */
export function SkeletonStatRow({ count = 3 }: { count?: number }) {
  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          data-skeleton="stat"
          className="h-24 rounded-[var(--radius-lg)] border border-[var(--border)] skeleton-shimmer"
        />
      ))}
    </div>
  )
}

/** Grille de cartes de contenu (géométrie Card : ~160px). */
export function SkeletonCardGrid({ count = 6, cols = 3 }: { count?: number; cols?: 2 | 3 | 4 }) {
  const colClass = { 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3', 4: 'sm:grid-cols-4' }[cols]
  return (
    <div className={cn('grid gap-3', colClass)}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          data-skeleton="card"
          className="h-40 rounded-[var(--radius-lg)] border border-[var(--border)] skeleton-shimmer"
        />
      ))}
    </div>
  )
}

/** Lignes hautes (agenda, listes d'items). */
export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          data-skeleton="row"
          className="h-16 rounded-[var(--radius-lg)] border border-[var(--border)] skeleton-shimmer"
        />
      ))}
    </div>
  )
}
```

Remplacer le contenu de `frontend/components/PageSkeleton.tsx` par :

```tsx
import {
  SkeletonHeader,
  SkeletonStatRow,
  SkeletonCardGrid,
} from "@/components/ui/skeleton";

/**
 * Skeleton générique des pages module : calqué sur le gabarit commun
 * (ModuleHeader + rangée de stats + grille de cartes). Les modules denses
 * ont leur propre loading.tsx sur mesure.
 */
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <SkeletonStatRow count={3} />
      <SkeletonCardGrid count={6} cols={3} />
    </div>
  );
}

export default PageSkeleton;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run __tests__/components/skeleton-blocks.test.tsx`
Expected: PASS (5 passed).
Run: `npx vitest run` puis `npx tsc --noEmit` — Expected: tout vert.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/skeleton.tsx frontend/components/PageSkeleton.tsx frontend/__tests__/components/skeleton-blocks.test.tsx
git commit -m "feat(design): blocs skeleton composables + PageSkeleton geometrique"
```

---

## Task 9: loading.tsx sur mesure (6 modules denses)

**Files:**
- Modify: `frontend/src/app/finance/loading.tsx`, `sante/loading.tsx`, `garderobe/loading.tsx`, `agenda/loading.tsx`, `cuisine/loading.tsx`
- Create: `frontend/src/app/patrimoine/loading.tsx` (n'existe pas)

**Interfaces:**
- Consumes: `SkeletonHeader`, `SkeletonStatRow`, `SkeletonCardGrid`, `SkeletonList`, `SkeletonTable`, `Skeleton` (Task 8).
- Produces: rien (feuilles App Router).

- [ ] **Step 1: Écrire les 6 fichiers**

AVANT d'écrire chaque fichier, ouvrir le composant principal du module (`components/finance/Finance.tsx`, `components/finance/PatrimoineTab.tsx`, `components/sante/Sante.tsx`, `components/garderobe/Garderobe.tsx`, `components/agenda/Agenda.tsx`, `src/app/cuisine/page.tsx`) et ajuster comptes/colonnes ci-dessous pour coller au PREMIER écran réel (nombre de stat-cards, tabs, table vs grille). Gabarits de départ :

```tsx
// frontend/src/app/finance/loading.tsx
import { SkeletonHeader, SkeletonStatRow, SkeletonTable, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <Skeleton className="h-9 w-72 rounded-[var(--radius-full)]" /> {/* rail d'onglets */}
      <SkeletonStatRow count={4} />
      <SkeletonTable rows={8} />
    </div>
  );
}
```

```tsx
// frontend/src/app/patrimoine/loading.tsx
import { SkeletonHeader, SkeletonStatRow, SkeletonCardGrid } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <SkeletonStatRow count={3} />
      <SkeletonCardGrid count={4} cols={2} />
    </div>
  );
}
```

```tsx
// frontend/src/app/sante/loading.tsx
import { SkeletonHeader, SkeletonStatRow, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <Skeleton className="h-9 w-72 rounded-[var(--radius-full)]" />
      <SkeletonStatRow count={3} />
      <SkeletonCardGrid count={4} cols={2} />
    </div>
  );
}
```

```tsx
// frontend/src/app/garderobe/loading.tsx
import { SkeletonHeader, SkeletonStatRow, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <Skeleton className="h-9 w-96 rounded-[var(--radius-full)]" /> {/* onglets nombreux */}
      <SkeletonStatRow count={3} />
      <SkeletonCardGrid count={8} cols={4} /> {/* grille de pièces (vignettes) */}
    </div>
  );
}
```

```tsx
// frontend/src/app/agenda/loading.tsx
import { SkeletonHeader, SkeletonList, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <Skeleton className="h-9 w-72 rounded-[var(--radius-full)]" />
      <SkeletonList rows={6} />
    </div>
  );
}
```

```tsx
// frontend/src/app/cuisine/loading.tsx
import { SkeletonHeader, SkeletonCardGrid, Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <SkeletonHeader />
      <Skeleton className="h-9 w-80 rounded-[var(--radius-full)]" />
      <SkeletonCardGrid count={6} cols={3} />
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `npx tsc --noEmit` — Expected: 0 erreur.
Run: `npx vitest run` — Expected: suite verte.
Contrôle visuel (app lancée, réseau throttlé « Slow 3G » dans DevTools) : sur les 6 modules, la page chargée remplace le skeleton SANS saut de mise en page majeur ; ajuster comptes/hauteurs si un décalage saute aux yeux.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/finance/loading.tsx frontend/src/app/patrimoine/loading.tsx frontend/src/app/sante/loading.tsx frontend/src/app/garderobe/loading.tsx frontend/src/app/agenda/loading.tsx frontend/src/app/cuisine/loading.tsx
git commit -m "feat(design): skeletons sur mesure des 6 modules denses (+ patrimoine/loading)"
```

---

## Task 10: Clôture documentaire

**Files:**
- Modify: `orchestration/en-cours/improvements.md`
- Move: `orchestration/a-faire/2026-07-02-fondations-verre-clair-design.md` → `orchestration/finis/`
- Move: `orchestration/a-faire/2026-07-02-fondations-verre-clair.md` → `orchestration/finis/`

- [ ] **Step 1: Marquer les items livrés dans improvements.md**

Ajouter en fin de ligne (même format que les marquages existants « ← FINIS ✓ (date) ») :
- `2.2` : `← FINIS ✓ (<date du jour>) grain SVG + lavis d'accent par module (--wash-module)`
- `2.3` : `← FINIS ✓ (<date du jour>) recettes .glass-card/.glass-veil/.glass-inset + garde CI`
- `2.4` : `← FINIS ✓ (<date du jour>) contraste AA testé (contrast-tokens.test.ts, 2 thèmes)`
- `2.5` : `← FINIS ✓ (<date du jour>) EmptyState serif italique + ornement laiton`
- `2.7` : `← FINIS ✓ (<date du jour>) blocs composables + 6 loading.tsx sur mesure`

- [ ] **Step 2: Déplacer spec + plan vers finis/**

```bash
git mv orchestration/a-faire/2026-07-02-fondations-verre-clair-design.md orchestration/finis/
git mv orchestration/a-faire/2026-07-02-fondations-verre-clair.md orchestration/finis/
```

- [ ] **Step 3: Commit**

```bash
git add orchestration/en-cours/improvements.md
git commit -m "docs: marque 2.2-2.5 et 2.7 livres (fondations Verre Clair) + docs vers finis/"
```

---

## Self-Review

**1. Spec coverage**
- Grain papier (spec §1) → Task 3 (token 3 blocs + body::after). ✓
- Teinte par module (spec §2) : data-module via MainShell, 4ᵉ lavis, table par catégorie, teintes palette DESIGN.md, indirection `--tint-*` DANS les blocs de tokens (compatible garde d'égalité des blocs sombres) → Task 4. ✓
- Verre unifié (spec §3, 5 recettes) → Tasks 5 (recettes + ui/) et 6 (reste + garde CI git grep). ✓
- AA testé (spec §4) : parse des 3 blocs, composite alpha, paires texte 4.5 / UI 3.0, égalité des blocs sombres, procédure de correction déterministe → Tasks 1-2. ✓
- EmptyState éditorial (spec §5, API inchangée) → Task 7. ✓
- Skeletons (spec §6) : blocs composables + PageSkeleton + 6 modules (patrimoine créé) → Tasks 8-9. ✓
- Clôture (marquage improvements + cycle a-faire→finis) → Task 10. ✓

**2. Placeholder scan** : aucun TBD ; les gabarits de Task 9 sont du code complet, avec l'instruction explicite de vérifier la géométrie sur le composant réel avant écriture (critère spec = « pas de saut », vérifié visuellement). La correction de tokens (Task 2 Step 3) est une procédure déterministe (pas un « ajuster au besoin »).

**3. Type consistency**
- `Rgba`/`parseCssColor`/`composite`/`contrastRatio` : signatures identiques Task 1 (def) et Task 2 (imports). ✓
- `SkeletonHeader()/SkeletonStatRow({count})/SkeletonCardGrid({count,cols})/SkeletonList({rows})` : définis Task 8, consommés Task 9 avec les mêmes props. `cn` est déjà importé en tête de skeleton.tsx (fichier existant). ✓
- `.glass-card/.glass-veil/.glass-inset` définies Task 5 Step 1, consommées Tasks 5-6. ✓
- `data-module` posé par MainShell (Task 4 Step 3) = sélecteurs `body[data-module="…"]` (Step 5) — segments identiques aux dossiers `src/app/`. ✓
- Le test d'égalité des blocs sombres (Task 2) impose que Tasks 3-4 copient leurs tokens dans les DEUX blocs — rappelé dans chaque task. ✓
