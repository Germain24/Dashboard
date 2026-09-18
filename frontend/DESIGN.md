# Mission Control — Design System

> **Contrat de référence.** Toutes les CONV qui touchent le frontend (CONV 4, 6, 8-15)
> doivent respecter ce document. Ne pas dériver sans mettre ce fichier à jour.
>
> **Mood** : **Heritage Editorial** — « Paper & Ink » (Old Money / City Boy).
> Crème + encre marine, accents bordeaux & vert anglais, hairlines plutôt qu'ombres.
> Titres serif **Libre Caslon Text**, corps **Public Sans**. Clair = papier ;
> sombre = marine minuit + laiton.
> **Généré** : CONV DESIGN (2026-05-26)
> **Mis à jour** : 2026-06-04 — reskin **Heritage Editorial** (réf. StyleVoulu) :
> palette crème/marine, polices Libre Caslon + Public Sans, rayons 4/8, ombres
> lithograph. Historique : Savile Row, accueil tableau de bord, planificateur, cuisine.

---

## 1. Tokens CSS (`globals.css`)

Toutes les valeurs vivent dans `src/app/globals.css`.
Ne jamais coder une couleur en dur dans un composant : toujours utiliser les `var(--...)`.

### Backgrounds (crème papier / marine minuit)

| Token | Light | Dark |
|---|---|---|
| `--background` | `#faf9f5` | `#0B121E` |
| `--background-subtle` | `#f4f4f0` | `#111a2a` |
| `--muted` | `#efeeea` | `#18222f` |
| `--card` | `#ffffff` | `#111a2a` |

### Texte (encre / crème)

| Token | Light | Dark |
|---|---|---|
| `--foreground` | `#1b1c1a` | `#f2f1ed` |
| `--muted-foreground` | `#44474d` | `#9aa3b0` |
| `--card-foreground` | `#1b1c1a` | `#f2f1ed` |

### Bordures (hairlines)

| Token | Light | Dark |
|---|---|---|
| `--border` | `#c5c6ce` | `#243042` |

### Primaire (marine académique)

| Token | Light | Dark |
|---|---|---|
| `--primary` | `#04142c` | `#c8d6f0` |
| `--primary-foreground` | `#ffffff` | `#0b1b34` |
| `--accent` | `#efeeea` | `#18222f` |
| `--accent-foreground` | `#1b1c1a` | `#f2f1ed` |

### Accent interactif (marine clair / laiton sombre)

| Token | Light | Dark |
|---|---|---|
| `--ring` | `#04142c` | `#C5A059` |
| `--nav-active-fg` | `#04142c` | `#d8be8a` |
| `--tertiary` (bordeaux éditorial) | `#501312` | `#d17771` |

`--ring` : focus, nav active, liens, lavis d'état actif (marine en clair, laiton
en sombre). `--tertiary` : bordeaux pour surlignages/puces éditoriales.

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

**Corps & UI** : **Public Sans** (clarté institutionnelle), auto-hébergée via
`next/font/google`, exposée par `var(--font-public-sans)` → `--font-sans`.
**Titres** : **Libre Caslon Text** (voix éditoriale littéraire), `var(--font-serif)`,
appliqué aux `h1` et au wordmark via `.font-display`. **Labels** : Public Sans en
**majuscules** avec letter-spacing (indexation archivistique). Les labels de section
et les données denses restent en sans pour la lisibilité.
**Mono** : `ui-monospace, SFMono-Regular, Menlo, monospace`
**Taille de base** : `15px`, `line-height: 1.6` (réduite à `14px` en densité compacte)

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

## 4. Thème dark/light + densité

**Thème** : trois états — `système` (suit `prefers-color-scheme`), `clair`, `sombre`.
Le toggle (`ThemeToggle`, pied de sidebar) écrit `data-theme` sur `<html>` et
persiste dans `localStorage` (`mc-theme`). Le CSS : `@media (prefers-color-scheme: dark)`
pour le mode système, surchargé par `[data-theme="dark"]` / `[data-theme="light"]`.

**Densité** : `confort` (défaut) / `compact`. `DensityToggle` écrit `data-density`
(persisté `mc-density`) ; `[data-density="compact"]` réduit la taille racine à 14px.

**Anti-flash** : un script inline dans `layout.tsx` applique thème + densité avant
le premier paint (pas de flash de thème incorrect).

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

**Source unique** : `lib/modules.ts` (slug, label, icône, groupe). La sidebar
desktop, le drawer mobile et la palette de commandes en dérivent tous — un module
ajouté là apparaît partout, dans le même ordre, avec la même icône. Ne jamais
redéclarer une liste de modules ailleurs.

- **≥ md** : Sidebar fixe gauche `md:w-56 lg:w-60`, libellés toujours visibles,
  groupée (Vie quotidienne / Santé & Sport / Organisation / Finances / Outils).
- **< md** : `MobileNav` — header fixe (`h-12`) + hamburger → drawer (mêmes groupes).
- **Règle** : `hidden md:flex` sur la Sidebar. `md:hidden` sur MobileNav.
- **État actif** (« vous êtes ici ») : classe `.nav-active` = lavis bleu 12 % +
  texte/icône `var(--nav-active-fg)` (bleu assombri AA) + `aria-current="page"`.
  Jamais de barre latérale (side-stripe) : fond plein + teinte.
- **Accès** : lien d'évitement (skip link) en tête de `<body>` → `#main-content` ;
  palette de commandes `⌘K`/`Ctrl K` (`CommandTrigger` visible + `CommandPalette`) ;
  aide raccourcis `?` (`ShortcutsHelp`).

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

- Animations avancées (`framer-motion`) → V2. (Les transitions actuelles passent
  par CSS + keyframes maison dans `globals.css`.)
- i18n → full français pour l'instant
- Palette de couleurs par module (ex. violet pour Finance) → possible en V2
  via `data-module` CSS attribute sur le layout

**Déjà livrés** (n'étaient pas dans la V1 d'origine) : toggle thème clair/sombre/système
manuel + densité, toasts (`sonner`, montés dans `QueryProvider`), palette de commandes
`⌘K`, aide raccourcis `?`, et l'accueil en **tableau de bord** (`TodayPanel` +
`DaySignals`) plutôt qu'une grille de lancement.
