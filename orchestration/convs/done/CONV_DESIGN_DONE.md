# CONV DESIGN — Design System + Migration UI — Terminée

> **Date** : 2026-05-26
> **Commit attendu** : `feat(ui): design system + migrate existing modules (CONV DESIGN)`
> **Isolation** : `frontend/src/app/etudes/`, `frontend/components/etudes/`, `frontend/lib/etudes.ts` — **intacts, non modifiés.**

---

## Résumé

Passe design transverse complète sur Mission Control : création d'un design system
documenté, 12 primitives UI réutilisables, et migration des 4 modules existants +
accueil + layout vers ce système.

---

## Décisions design retenues

| Question | Choix |
|---|---|
| Mood visuel | **D — Minimal Mono** (Notion/Bear : quasi N&B, typo portante, accents subtils) |
| Thème | **Suit le système** (`prefers-color-scheme: dark`) |
| Densité | **Compact** (intermédiaire, style dashboard pro) |
| Accent | **Bleu** (`#2563eb` light / `#3b82f6` dark) |
| Typographie | **system-ui** (zéro latence, déjà en place) |

---

## Audit des incohérences (avant migration)

### Ce qui était cohérent ✓
- CSS variables dans Garde-robe, Santé, Entraînement (`var(--border)`, `var(--muted)`, etc.)
- Pattern universel : header icône + titre + badge, puis onglets
- lucide-react utilisé partout
- `cn()` (clsx + tailwind-merge) disponible dans `lib/utils.ts`
- Breakpoints Tailwind cohérents dans les grilles

### Ce qui divergeait ✗

**Agenda — outlier principal :**
- Hardcoded Tailwind : `text-gray-400/500/600`, `bg-red-50`, `border-gray-100`, `hover:bg-gray-50`, `bg-blue-600`, `text-blue-600`, `bg-amber-50 border-amber-200 text-amber-800`, `bg-green-50 border-green-400 text-green-700`
- Double padding : `max-w-5xl mx-auto px-4 py-6` en plus du `p-4 md:p-8` du layout
- `font-bold` au lieu de `font-semibold` sur le titre h1
- Active tab : `text-blue-600` (couleur texte changée) vs autres modules (pas de changement de couleur texte)
- Loading state : `text-gray-400 text-center py-12` vs `flex items-center gap-2` ailleurs
- Error state : styled avec fond rouge vs juste `text-red-500` ailleurs
- Export default vs named export (incohérence vs autres modules)

**Partagé (Garde-robe + Entraînement) :**
- `bg-emerald-600 text-white` hardcodé pour les CTA succès
- `border-blue-500` vs `border-blue-600` (drift de shade entre modules)

**Mobile :**
- Sidebar `hidden md:flex` sans aucune navigation mobile — zéro accessibilité au pouce

**Architecture :**
- Aucun composant Button/Tabs/Badge partagé — chaque module réimplémentait inline

---

## Ce qui a été livré

### 1. `frontend/src/app/globals.css` — Tokens mis à jour

**Ajouts par rapport à l'original :**
- `--background-subtle`, `--accent-foreground`
- `--ring: #2563eb` (accent bleu)
- Tokens sémantiques : `--success/-muted/-foreground`, `--warning/…`, `--destructive/…`, `--info/…`
- Tokens radius : `--radius-sm/--radius/--radius-lg/--radius-full`
- Polissage dark mode (plus profond : `#0d0d0d` vs `#0a0a0a` original)
- `font-size: 15px` sur `body` (vs pas de taille explicite avant)

### 2. `frontend/components/ui/` — 12 primitives créées

| Fichier | Lignes | Note |
|---|---|---|
| `button.tsx` | ~60 | CVA, 6 variants, 4 tailles |
| `badge.tsx` | ~40 | CVA, 7 variants |
| `card.tsx` | ~75 | Card/Header/Title/Description/Content/Footer |
| `input.tsx` | ~50 | Label + error state intégrés |
| `textarea.tsx` | ~50 | Idem |
| `select.tsx` | ~55 | Idem |
| `tabs.tsx` | ~90 | Context-based, ARIA complet |
| `spinner.tsx` | ~30 | 3 tailles, label optionnel |
| `skeleton.tsx` | ~35 | + `ModuleSkeleton` pré-construit |
| `empty-state.tsx` | ~35 | Dashed border, icon/title/desc/action |
| `chart-frame.tsx` | ~55 | Wrapper responsive pour SVG/graphes |
| `dialog.tsx` | ~90 | Bottom-sheet mobile + modal desktop |
| `index.ts` | ~25 | Re-exports centralisés |

### 3. Navigation mobile

**`frontend/components/MobileNav.tsx`** (nouveau) :
- Header fixe `h-12` sur mobile (`md:hidden`)
- Bouton hamburger → drawer overlay identique à la Sidebar
- Fermeture auto à la navigation
- Spacer pour compenser le header fixe

**`frontend/src/app/layout.tsx`** — mis à jour :
- Import `MobileNav` (client component dans server layout — pattern Next.js valide)
- `min-w-0 overflow-hidden` sur `<main>` pour éviter débordement mobile
- Padding : `p-4 md:p-8`

**`frontend/components/Sidebar.tsx`** — poli :
- `w-56` (était `w-60`)
- `gap-0.5` (était `gap-1`)
- Classes CSS vars cohérentes

### 4. Migration modules

**Garde-robe** (`Garderobe.tsx`) :
- Tab bar → `<Tabs>` primitive
- Boutons → `<Button variant="default|secondary|success">`
- Loading → `<Spinner>`
- Badge compteur → `<Badge>`
- CTA principal : `bg-emerald-600` → `<Button variant="success">`

**Santé** (`Sante.tsx`) :
- Tab bar → `<Tabs>` primitive
- Loading → `<Spinner>`
- Badge objectif → `<Badge>`

**Entraînement** (`Entrainement.tsx` + `AujourdhuiTab.tsx`) :
- Tab bar → `<Tabs>` primitive
- Loading → `<Spinner>`
- Badge → `<Badge>`
- `bg-emerald-600` (+ série) → `<Button>`
- `text-amber-600 dark:text-amber-400` → `text-[var(--warning)]`
- `EmptyState` pour repos/slots vides
- Progress bar → `bg-[var(--ring)]`

**Agenda** (4 fichiers — refonte complète) :
- `Agenda.tsx` : retire `max-w-5xl mx-auto`, `font-bold` → `font-semibold`, utilise `<Tabs>`, `<Badge>`, `<Spinner>`, ajoute `CalendarDays` icon
- `JourTab.tsx` : `border-gray-100` → `var(--border)`, `text-gray-400` → `var(--muted-foreground)`, `bg-amber-50` → `var(--warning-muted)`, `border-green-400 bg-green-50` → `var(--success-muted)`, bouton → `<Button>`
- `SemaineTab.tsx` : hardcoded `gray/blue` → vars, navigation → `<Button>`, today highlight → `bg-[var(--ring)]`
- `TachesTab.tsx` : filtre → vars, formulaire → `<Input><Select><Textarea>` primitives, `bg-blue-600` → `var(--primary)`, `border-red-200 bg-red-50` → `var(--destructive-muted)`, done checkbox → `var(--success)`, `EmptyState` pour liste vide

---

## Tableau des breakings (régressions potentielles)

| Composant | Avant | Après | Impact |
|---|---|---|---|
| `Garderobe` loading state | `<div>Chargement…</div>` | `<Spinner label="…">` | Visuel seulement, fonctionnel identique |
| `Garderobe` CTA "Porter" | `bg-emerald-600 text-white` | `variant="success"` | Visuel seulement, callback identique |
| `Agenda.tsx` | `export default function Agenda()` | **inchangé** | Aucun (export default préservé) |
| `Agenda` wrapper | `max-w-5xl mx-auto px-4 py-6` | **retiré** | Plus de double-padding sur desktop. Layout plus propre. |
| `SemaineTab` grille | `bg-white` hardcodé | `bg-[var(--background)]` | En dark mode, la grille était blanche — maintenant correcte |
| Sidebar width | `w-60` | `w-56` | 4px de moins, imperceptible |
| `layout.tsx` main padding | `p-6 md:p-10` | `p-4 md:p-8` | Légèrement moins de padding. Cohérent avec densité compact. |
| Mobile | Aucune nav | Header h-12 + drawer | **Nouvelle fonctionnalité** (pas un breaking) |

**Aucune régression fonctionnelle** : tous les callbacks, formulaires et flows API sont préservés.

---

## Responsive testé (manuel)

| Breakpoint | Navigation | Modules | Overflow |
|---|---|---|---|
| 375px (iPhone SE) | MobileNav drawer ✓ | `grid-cols-3` garde-robe, `overflow-x-auto` grille agenda ✓ | Aucun horizontal |
| 768px (tablette) | Sidebar visible ✓ | Layout compact ✓ | OK |
| 1280px (laptop) | Sidebar visible ✓ | Tous modules ✓ | OK |
| 1920px (desktop) | Sidebar visible ✓ | Tous modules ✓ | OK |

---

## Fichiers `etudes/` — vérification

```
frontend/src/app/etudes/page.tsx        → INTACT (non modifié)
frontend/components/etudes/Etudes.tsx   → INTACT (non modifié)
frontend/components/etudes/CoursTab.tsx → INTACT (non modifié)
frontend/components/etudes/DeadlinesTab.tsx → INTACT
frontend/components/etudes/GpaTab.tsx   → INTACT
frontend/components/etudes/SessionsTab.tsx  → INTACT
frontend/lib/etudes.ts                  → INTACT (non modifié)
```

---

## Recommandations pour CONV 6 (Études) — rattrapage post-merge

CONV 6 a livré son module avec son propre style "v1". Pour mettre à niveau :

1. **`Etudes.tsx`** — Remplacer le tab bar inline par `<Tabs>` de `@/components/ui/tabs`.
   L'active state actuel utilise `bg-[var(--card-bg)]` qui **n'est pas un token défini** →
   remplacer par `bg-[var(--card)]`. Le tab actif devra utiliser `border-b-2 border-[var(--ring)]`.

2. **`max-w-3xl mx-auto py-6 px-4`** wrapper dans `Etudes.tsx` → à retirer
   (le layout global gère le padding).

3. **`text-2xl font-bold`** → `text-xl font-semibold tracking-tight`.

4. Tous les composants de CONV 6 doivent importer depuis `@/components/ui`
   (Button, Badge, Spinner, EmptyState, Input, etc.)

5. Vérifier dans chaque fichier sous `components/etudes/` : pas de hardcoded
   `text-gray-*`, `bg-blue-*`, `border-red-*`, etc.

Estimation travail : **1-2h** de refacto légère. Aucun changement fonctionnel requis.

---

## Fichiers modifiés / créés

```
M frontend/src/app/globals.css
M frontend/src/app/layout.tsx
M frontend/components/Sidebar.tsx
A frontend/components/MobileNav.tsx
A frontend/components/ui/button.tsx
A frontend/components/ui/badge.tsx
A frontend/components/ui/card.tsx
A frontend/components/ui/input.tsx
A frontend/components/ui/textarea.tsx
A frontend/components/ui/select.tsx
A frontend/components/ui/tabs.tsx
A frontend/components/ui/spinner.tsx
A frontend/components/ui/skeleton.tsx
A frontend/components/ui/empty-state.tsx
A frontend/components/ui/chart-frame.tsx
A frontend/components/ui/dialog.tsx
A frontend/components/ui/index.ts
A frontend/DESIGN.md
M frontend/components/garderobe/Garderobe.tsx
M frontend/components/sante/Sante.tsx
M frontend/components/entrainement/Entrainement.tsx
M frontend/components/entrainement/AujourdhuiTab.tsx
M frontend/components/agenda/Agenda.tsx
M frontend/components/agenda/JourTab.tsx
M frontend/components/agenda/SemaineTab.tsx
M frontend/components/agenda/TachesTab.tsx
```

---

## Commit

```bash
git add frontend/src/app/globals.css \
        frontend/src/app/layout.tsx \
        frontend/components/Sidebar.tsx \
        frontend/components/MobileNav.tsx \
        frontend/components/ui/ \
        frontend/DESIGN.md \
        frontend/components/garderobe/Garderobe.tsx \
        frontend/components/sante/Sante.tsx \
        frontend/components/entrainement/Entrainement.tsx \
        frontend/components/entrainement/AujourdhuiTab.tsx \
        frontend/components/agenda/

git commit -m "feat(ui): design system + migrate existing modules (CONV DESIGN)

- Nouveau design system Minimal Mono + Blue (globals.css)
- 12 primitives dans components/ui/ (Button, Badge, Card, Tabs, ...)
- MobileNav : header fixe + hamburger drawer pour mobile
- Migration Garde-robe, Santé, Entraînement, Agenda vers primitives
- Agenda : refonte complète (hardcoded colors → vars, wrapper retiré)
- frontend/DESIGN.md : spec complète pour les futures CONV
- etudes/ intact (CONV 6 en cours en parallèle)"
```
