# Mission Control — Design System

> **Contrat de référence.** Toutes les CONV qui touchent le frontend (CONV 4, 6, 8-15)
> doivent respecter ce document. Ne pas dériver sans mettre ce fichier à jour.
>
> **Mood** : Minimal Mono + Blue accent (Notion/Bear/iA Writer)
> **Généré** : CONV DESIGN (2026-05-26)

---

## 1. Tokens CSS (`globals.css`)

Toutes les valeurs vivent dans `src/app/globals.css`.
Ne jamais coder une couleur en dur dans un composant : toujours utiliser les `var(--...)`.

### Backgrounds

| Token | Light | Dark |
|---|---|---|
| `--background` | `#ffffff` | `#0d0d0d` |
| `--background-subtle` | `#fafafa` | `#111111` |
| `--muted` | `#f5f5f5` | `#1a1a1a` |
| `--card` | `#ffffff` | `#111111` |

### Texte

| Token | Light | Dark |
|---|---|---|
| `--foreground` | `#111111` | `#e8e8e8` |
| `--muted-foreground` | `#737373` | `#a3a3a3` |
| `--card-foreground` | `#111111` | `#e8e8e8` |

### Bordures

| Token | Light | Dark |
|---|---|---|
| `--border` | `#e8e8e8` | `#262626` |

### Primaire (boutons actions principales)

| Token | Light | Dark |
|---|---|---|
| `--primary` | `#111111` | `#e8e8e8` |
| `--primary-foreground` | `#ffffff` | `#0d0d0d` |
| `--accent` | `#f5f5f5` | `#1a1a1a` |
| `--accent-foreground` | `#111111` | `#e8e8e8` |

### Accent interactif (bleu)

| Token | Light | Dark |
|---|---|---|
| `--ring` | `#2563eb` | `#3b82f6` |

Utilisé pour : tabs actifs, focus rings, liens, progress bars.

### Couleurs sémantiques

| Rôle | `--success` | `--warning` | `--destructive` | `--info` |
|---|---|---|---|---|
| Couleur | `#16a34a` / `#4ade80` | `#d97706` / `#fbbf24` | `#dc2626` / `#f87171` | `=ring` |
| `-muted` | fond doux | fond doux | fond doux | fond doux |
| `-foreground` | texte sur fond muted | texte sur fond muted | texte sur fond muted | texte sur fond muted |

### Rayons

```css
--radius-sm: 4px;   /* badges, inputs internes */
--radius:    6px;   /* boutons, inputs */
--radius-lg: 8px;   /* cartes, panels */
--radius-full: 9999px; /* pills */
```

---

## 2. Typographie

**Famille** : `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` (zero latence)
**Mono** : `ui-monospace, SFMono-Regular, Menlo, monospace`
**Taille de base** : `15px`, `line-height: 1.6`

### Échelle en usage

| Rôle | Classes Tailwind |
|---|---|
| Titre de module (h1) | `text-xl font-semibold tracking-tight` |
| Sous-titre / section (h2) | `text-base font-semibold` |
| Corps standard | `text-sm` (13-14px) |
| Métadonnée / label | `text-xs` (12px) |
| Label de champ | `text-xs font-medium text-[var(--muted-foreground)]` |

**Règle** : ne jamais utiliser `font-bold` dans les interfaces (trop lourd, écran sombre
ou clair). `font-semibold` est le maximum.

---

## 3. Espacement (densité : compact)

| Rôle | Valeur |
|---|---|
| Padding de page | `p-4 md:p-8` |
| Gap entre sections | `space-y-4` |
| Padding carte | `p-4` |
| Padding compact (rows, badges) | `px-2.5 py-1` |
| Gap d'icône + texte | `gap-2.5` |

---

## 4. Thème dark/light

**Stratégie** : CSS media query `(prefers-color-scheme: dark)` — suit l'OS.
Pas de toggle manuel (V1). Si besoin futur : ajouter `next-themes` et `ThemeProvider`.

**Règle** : tout composant doit être testé en light ET dark. Les valeurs hardcodées
(`bg-gray-100`, `text-blue-600`, etc.) sont **interdites**.

---

## 5. Primitives (`components/ui/`)

### Fichiers disponibles

| Fichier | Export principal | Usage |
|---|---|---|
| `button.tsx` | `<Button>` | Toutes les actions |
| `badge.tsx` | `<Badge>` | Labels, compteurs, statuts |
| `card.tsx` | `Card, CardHeader, CardContent…` | Panneaux de données |
| `input.tsx` | `<Input>` | Champs texte |
| `textarea.tsx` | `<Textarea>` | Champs multilignes |
| `select.tsx` | `<Select>` | Listes déroulantes |
| `tabs.tsx` | `Tabs, TabsList, TabsTrigger, TabsContent` | Onglets |
| `spinner.tsx` | `<Spinner>` | Chargement inline |
| `skeleton.tsx` | `Skeleton, ModuleSkeleton` | Placeholder squelette |
| `empty-state.tsx` | `<EmptyState>` | État vide |
| `chart-frame.tsx` | `<ChartFrame>` | Wrapper graphes SVG |
| `dialog.tsx` | `Dialog, DialogHeader…` | Modales / drawers |
| `index.ts` | Re-exports | `import { Button } from "@/components/ui"` |

### Button variants

```tsx
<Button variant="default">Action principale</Button>
<Button variant="secondary">Action secondaire</Button>
<Button variant="ghost">Action discrète</Button>
<Button variant="destructive">Supprimer</Button>
<Button variant="success">Valider / Porter</Button>
<Button size="sm|md|lg|icon" />
```

### Badge variants

```tsx
<Badge>Neutre</Badge>
<Badge variant="success">Actif</Badge>
<Badge variant="warning">Attention</Badge>
<Badge variant="destructive">Erreur</Badge>
<Badge variant="info">Info</Badge>
<Badge variant="outline">Contour</Badge>
```

### Tabs (pattern universel de tous les modules)

```tsx
const [tab, setTab] = useState<Tab>("jour");

<Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
  <TabsList>
    <TabsTrigger value="jour">📅 Aujourd'hui</TabsTrigger>
    <TabsTrigger value="semaine">🗓 Semaine</TabsTrigger>
  </TabsList>
  <TabsContent value="jour">…</TabsContent>
  <TabsContent value="semaine">…</TabsContent>
</Tabs>
```

---

## 6. Structure d'un module type

```tsx
// page.tsx (Server Component)
import { MonModule } from "@/components/mon-module/MonModule";
export default function Page() { return <MonModule />; }

// MonModule.tsx (Client Component — orchestrateur)
export function MonModule() {
  const [tab, setTab] = useState<Tab>("…");
  // loading → <Spinner label="…" />
  // error   → <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-3">
        <Icon className="h-5 w-5 shrink-0" />
        <h1 className="text-xl font-semibold tracking-tight">Titre</h1>
        <Badge className="ml-auto">Métadonnée clé</Badge>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList>…</TabsList>
        <TabsContent value="…">…</TabsContent>
      </Tabs>
    </div>
  );
}
```

---

## 7. Patterns responsive

### Breakpoints (Tailwind 4 defaults)

| Préfixe | Largeur | Contexte |
|---|---|---|
| *(base)* | 0–767px | Mobile (iPhone SE 375px, petits téléphones) |
| `md:` | 768px+ | Tablette, laptop |
| `lg:` | 1024px+ | Laptop large |
| `xl:` | 1280px+ | Desktop |

### Navigation

- **≥ md** : Sidebar fixe gauche `w-56`, toujours visible.
- **< md** : `MobileNav` — header fixe (hauteur `h-12`) + bouton hamburger → drawer overlay.
- **Règle** : `hidden md:flex` sur la Sidebar. `md:hidden` sur MobileNav.

### Tableaux et grilles denses

- Sur mobile, les tableaux doivent défiler horizontalement : entourer de
  `<div className="overflow-x-auto">`.
- Grilles de slots : `grid-cols-3 sm:grid-cols-6` (min 2 colonnes sur mobile).

### Modales

`Dialog` devient un bottom-sheet sur mobile (s'attache en bas) grâce à
`items-end sm:items-center` sur l'overlay.

---

## 8. Accessibilité (WCAG AA)

- **Focus visible** : `outline: 2px solid var(--ring)` appliqué globalement via `:focus-visible`.
- **Aria** : rôles `role="tablist"`, `role="tab"`, `aria-selected`, `aria-label` sur les boutons icon-only.
- **Contraste** : le bleu `#2563eb` sur blanc = ratio 5.9 : 1 ✓. Le gris `#737373` sur blanc = 4.6 : 1 ✓.
- **Taille min** : cibles tactiles ≥ 36px de hauteur.

---

## 9. Pour les futures CONV (4, 8-15)

### Checklist obligatoire

1. **Importer depuis `@/components/ui`** — ne pas réinventer Button, Tabs, Badge, etc.
2. **Utiliser `var(--...)` pour toutes les couleurs** — aucune classe Tailwind hardcodée
   (`text-blue-600`, `bg-gray-100`, `text-red-500`...).
3. **Structure module standard** : header + `<Tabs>` + `<TabsContent>`.
4. **État de chargement** : `<Spinner label="…" />` ou `<ModuleSkeleton />`.
5. **État vide** : `<EmptyState title="…" />`.
6. **Taille max par fichier TSX** : 200 lignes (cf. PLAN note 9).
7. **Pas de `max-w-*` wrapper** dans les composants modules — le layout global gère le padding.
8. **Mobile** : tester à 375px, pas de débordement horizontal, nav accessible.

### Modules à venir — notes spécifiques

- **Finance (CONV 4)** : les graphes Buffett utilisent `<ChartFrame>` pour le titre/légende.
  Progress bars → `bg-[var(--ring)]` sur `bg-[var(--muted)]`.
- **Budget (CONV 8)** : tableaux dépenses → `overflow-x-auto` obligatoire.
- **Habitudes (CONV 10)** : heat-map → inline SVG dans `<ChartFrame>`, couleurs sémantiques.
- **Études (CONV 6, rattrapage post-merge)** : voir `CONV_DESIGN_DONE.md` section
  "Recommandations pour CONV 6".

---

## 10. Ce qui N'EST PAS dans ce design system (V2+)

- Toggle dark/light manuel → ajouter `next-themes` + `ThemeProvider`
- Animations (`framer-motion`) → Framer Motion V2
- Toast notifications → sonner ou radix-toast V2
- i18n → full français pour l'instant
- Palette de couleurs par module (ex. violet pour Finance) → possible en V2
  via `data-module` CSS attribute sur le layout
