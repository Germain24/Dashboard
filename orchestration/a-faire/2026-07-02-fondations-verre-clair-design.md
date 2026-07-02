# Fondations Verre Clair — backgrounds, verre, AA, états vides, skeletons — Design

> Spec du chantier P1 §2 (tranche 1 : fondations + primitives) d'`orchestration/en-cours/improvements.md`
> (items 2.2, 2.3, 2.4, 2.5, 2.7). La passe de conformité module par module (2.1, 2.6)
> est un chantier séparé ultérieur, qui s'appuiera sur ces fondations.

## Objectif

Donner à l'app le rendu « quiet luxury » défini par DESIGN.md (« The Old Money
Almanac, Behind Clear Glass ») de façon **systémique** : tout part des tokens de
`frontend/src/app/globals.css`, les primitives consomment ces tokens, et les
invariants (contraste AA) deviennent des tests automatisés.

Décisions utilisateur (brainstorming 2026-07-02) :
- Périmètre = fondations + primitives ; PAS la passe des 29 modules (chantier suivant).
- Teinte d'accent **par module** (repère spatial subtil), pas de fond identique partout.
- Skeletons : sur mesure pour les modules denses + générique amélioré pour le reste.
- Approche token-first ; le contraste AA est vérifié par un test, pas à l'œil.

## Contraintes

- **Aucune couleur nouvelle** : uniquement la palette DESIGN.md (marine #04142c,
  laiton #C5A059, vert anglais #536252, oxblood #501312, slate #384762, ocre #8a6d1f).
- Grain et lavis : sobres — grain ≤ 3 % d'opacité, teinte module ≤ 10 % en clair
  et ≤ 12 % en sombre (le fond marine minuit avale davantage la couleur).
- `prefers-reduced-motion` déjà respecté globalement ; le grain est statique.
- API publiques des primitives inchangées (19 usages d'`EmptyState`, loading.tsx existants).
- Pas de nouvelle dépendance npm.
- Frontend : `npx vitest run`, `npx tsc --noEmit` depuis `frontend/`.

## 1. Grain papier (improvements 2.2a)

`body::after` fixe, au-dessus des lavis, sous le contenu :
- SVG `feTurbulence` (fractalNoise) inline en data-URI dans globals.css, < 2 Ko, zéro requête réseau.
- Opacité via token : `--grain-opacity: 0.025` (clair) / `0.02` (sombre, les deux blocs dark).
- `position: fixed; inset: 0; pointer-events: none; z-index: -1` (après `body::before`,
  donc rendu par-dessus les lavis).
- Statique (pas d'animation) — aucun coût GPU, indifférent à reduced-motion.

## 2. Teinte d'accent par module (improvements 2.2b)

- `MainShell.tsx` (lit déjà `usePathname()`) : un `useEffect` pose
  `document.body.dataset.module = <premier segment du pathname>` (vide sur `/`),
  nettoyé/actualisé à chaque navigation.
- globals.css : token `--wash-module: transparent` par défaut ; `body::before`
  gagne un **4ᵉ** gradient radial `radial-gradient(...  var(--wash-module), transparent ...)`
  positionné haut-centre, qui complète les 3 lavis existants.
- Table de correspondance par **catégorie du Deck** (sélecteurs groupés, pas 29 règles) :

| Catégorie (segments) | Teinte claire | Teinte sombre |
|---|---|---|
| Finance : `finance`, `patrimoine`, `budget` | marine ≤ 8 % | slate 12 % |
| Corps : `sante`, `entrainement`, `score`, `skincare`, `garderobe` | vert anglais 7 % | vert anglais 10 % |
| Quotidien : `cuisine`, `routines`, `agenda`, `habitudes` | ocre 7 % | laiton 9 % |
| Savoir : `etudes`, `travail`, `jobs`, `langues`, `documents`, `livres` | oxblood 6 % | oxblood 10 % |
| Loisirs : `musique`, `film`, `series`, `gaming`, `voyage`, `journal` | slate 8 % | slate 12 % |
| Reste (`/`, autres segments) | transparent (lavis de base seuls) | idem |

Les pourcentages sont des opacités du `rgb(... / x)` de la couleur DESIGN.md,
ajustables à l'implémentation dans la limite ≤ 10 % clair / ≤ 12 % sombre.

## 3. Recette de verre unique (improvements 2.3)

Quatre recettes officielles dans globals.css — et plus aucun backdrop-filter ad hoc :

- `.glass-panel` (existe) : chrome — dock, headers sticky, drawers.
- `.glass-modal` (existe) : surfaces flottantes — dialogs, palette.
- **`.glass-card`** (nouvelle) : la surface de carte standard —
  `background: var(--card)`, `backdrop-filter: blur(var(--glass-blur)) saturate(1.4)`,
  `border: 1px solid var(--glass-border)`,
  `box-shadow: inset 0 1px 0 0 var(--glass-highlight), var(--shadow)`.
- **`.glass-veil`** (nouvelle) : le voile d'overlay —
  `background: rgb(0 0 0 / 0.3)` + `backdrop-filter: blur(6px)`
  (le `bg-black/40 backdrop-blur-sm` et variantes actuels sont unifiés dessus).

Migration des usages recensés (2026-07-02) : `components/ui/card.tsx`,
`stat-card.tsx`, `chart-frame.tsx`, `tabs.tsx`, `dialog.tsx` (voile),
`CommandPalette.tsx` (voile), `MobileNav.tsx` (voile),
`documents/DocumentsTab.tsx` (voile), `src/app/routines/page.tsx` (voile + carte),
`deck/experiences/GenericGroupExperience.tsx`, `deck/modules/{Macros,NextWorkout,Skincare,Sleep}Module.tsx`.
`layout/Deck.tsx` utilise saturate 1.8 (chrome) → `.glass-panel`.
Résultat attendu : `grep backdrop-blur` hors globals.css ⇒ 0 occurrence dans les .tsx
(hors classes `.glass-*`).

## 4. Contraste AA vérifié par test (improvements 2.4)

- `frontend/__tests__/design/contrast.test.ts` :
  - parse `src/app/globals.css` : extrait les custom properties du bloc `:root`
    (clair) et du bloc `[data-theme="dark"]` (sombre) ;
  - résout `rgb(... / a)` et hex ; **composite les couleurs alpha sur leur fond**
    (ex. `--card` sur `--background`) avant calcul ;
  - calcule le ratio WCAG 2.x et vérifie :
    - texte (≥ 4.5) : `foreground`/`background`, `foreground`/card composité,
      `muted-foreground`/`background`, `muted-foreground`/card composité,
      `primary-foreground`/`primary`, chaque `X-foreground`/`X-muted`
      (success, warning, destructive, info, tertiary), `nav-active-fg` sur
      lavis nav composité (ring 10 % sur background) ;
    - UI (≥ 3.0) : `border` (composité)/`background`, `ring`/`background`.
- Les tokens en écart sont corrigés **en conservant la teinte** (on ajuste
  luminosité/opacité). Les deux blocs sombres (media query + `[data-theme="dark"]`)
  restent identiques — le test parse le bloc explicite, un grep de garde vérifie
  que les deux blocs ont le même contenu.
- Contrôle visuel final des 15 primitives `components/ui/` dans les deux thèmes
  (via le run de l'app), corrections ponctuelles si un composant contourne les tokens.

## 5. EmptyState éditorial (improvements 2.5)

API strictement inchangée (`icon?, title, description?, action?, className?`) :
- Titre en **Libre Caslon italique** (`font-display italic`), taille légèrement
  supérieure (base → lg), `text-wrap: balance`.
- Ornement laiton entre titre et description : un fin filet horizontal
  `1px × 40px` en `--warning`/laiton à opacité douce (pas d'emoji, pas d'illustration).
- Respiration accrue (`py-16`, gap 4), description en Body 15px `muted-foreground`.
- L'icône (slot existant) passe en opacité 40 % taille modérée — présente mais silencieuse.
- Test composant : rendu titre/description/action + snapshot de classes typographiques.

## 6. Skeletons géométriques (improvements 2.7)

- `components/ui/skeleton.tsx` : blocs composables exportés —
  `SkeletonHeader` (géométrie ModuleHeader : titre serif + sous-titre),
  `SkeletonStatRow` (n stat-cards), `SkeletonCardGrid` (n×m cartes),
  `SkeletonTable` (en-tête + n lignes), `SkeletonList` (n lignes hautes).
  Tous sur `.skeleton-shimmer` existant (déjà neutralisé par reduced-motion).
- `components/PageSkeleton.tsx` reconstruit avec ces blocs : header + rangée de
  3 stats + grille — géométrie du gabarit commun des modules.
- `loading.tsx` sur mesure (composition des blocs, calqués sur le premier écran
  réel) pour : **finance, patrimoine, sante, garderobe, agenda, cuisine**.
  Les autres segments gardent le PageSkeleton générique amélioré.
  (`patrimoine` n'a pas de loading.tsx aujourd'hui : le créer.)
- Critère : à froid, la mise en page ne « saute » pas quand les données arrivent
  sur les 6 modules ciblés (vérification visuelle, throttling réseau).

## Architecture & tests

- Tout le CSS nouveau vit dans `globals.css` (tokens + recettes) — pas de CSS modules.
- Composants touchés : `MainShell.tsx`, `ui/{card,stat-card,chart-frame,tabs,dialog,
  empty-state,skeleton}.tsx`, `PageSkeleton.tsx`, 6 `loading.tsx`, les fichiers
  listés §3 pour la migration verre.
- Tests : contraste (§4), composants (EmptyState, skeleton blocks, PageSkeleton),
  `npx vitest run` + `npx tsc --noEmit` verts.
- Workflow : TDD, un commit par item, marquage daté dans improvements.md à la fin.

## Hors périmètre

- Passe de conformité typo/palette/espacements des 29 modules (2.1) et sections
  repliables des pages denses (2.6) → chantier suivant.
- Toasts sonner, Dock layoutId, transitions de données (reste du §1) → chantier dédié.
- Performances (§4 d'improvements.md) → chantier P1 séparé.
