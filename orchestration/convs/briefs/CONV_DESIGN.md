# CONV DESIGN — Passe design transverse & design system

> **Conversation transverse**, pas numérotée dans les phases. Peut tourner
> **en parallèle de CONV 6 (Études)** sans conflit tant que l'isolation
> de fichiers est respectée (voir Hors-scope).

## Objectif

Mission Control a maintenant 5 surfaces UI livrées (accueil + Garde-robe +
Santé + Entraînement + Agenda). Chacune a été construite dans sa propre
CONV, avec son propre Claude → la cohérence visuelle a probablement dérivé.

Cette conversation fait **trois choses** :
1. **Auditer** ce qui existe pour identifier les incohérences (tokens,
   spacing, typo, composants, états, mobile).
2. **Établir un design system** : tokens, primitives réutilisables, theme,
   patterns d'écran. Le tout documenté dans `DESIGN.md`.
3. **Migrer les écrans existants** vers ce design system, puis garantir que
   les 9 modules restants (CONV 4, 6, 8-11, 12-15) s'y conforment.

## Contexte

Voir `PLAN.md` à la racine de ce dossier pour la vision globale, la stack,
et les notes héritées des CONV précédentes.

**Stack frontend** (à respecter strictement) :
- Next.js 15.5 (App Router) + React 19.1 + TypeScript 5
- TailwindCSS 4 avec CSS variables (style "shadcn-like", composants maison)
- Pas de UI lib lourde (pas de Material UI, Chakra, Mantine, etc.)
- Composants par module dans `frontend/components/<module>/`
- Pages dans `frontend/src/app/<module>/page.tsx`
- Client API typé dans `frontend/lib/<module>.ts`

## État actuel — modules à auditer

Surfaces UI livrées à étudier :
- `frontend/src/app/page.tsx` + composants accueil
- `frontend/src/app/garderobe/` + `frontend/components/garderobe/` (CONV 2)
- `frontend/src/app/sante/` + `frontend/components/sante/` (CONV 3)
- `frontend/src/app/entrainement/` + `frontend/components/entrainement/` (CONV 7)
- `frontend/src/app/agenda/` + `frontend/components/agenda/` (CONV 5)
- `frontend/app/globals.css` (tokens, CSS variables existantes)
- `frontend/src/app/layout.tsx` (layout racine, navigation)

Pages stubs à ignorer pour l'instant : finance, etudes (CONV 6 en cours,
voir Hors-scope), entrainement variantes futures, budget, cuisine, habitudes,
livres, robot.

## Décisions à prendre au démarrage (à poser à Germain)

1. **Mood visuel général**. 4 options à proposer en preview :
   - **(A) Pro neutre** — type Linear / Vercel dashboard, gris bleus, très
     sobre, focus sur la lisibilité des données
   - **(B) Tech sombre** — type Raycast / Arc, fond presque noir, accent
     vif (cyan/violet), un peu plus de chaleur
   - **(C) Calme clair** — type Things 3 / Craft, palette pastel, beaucoup
     d'espace blanc, doux pour le quotidien
   - **(D) Minimal mono** — type Notion / Bear, presque noir et blanc,
     typographie qui porte tout, accents subtils
2. **Thème** : dark uniquement, light uniquement, ou les deux avec toggle
   (suit le système par défaut) ?
3. **Densité de l'information** : confortable (généreux), compact (pro),
   dense (consoles) ?
4. **Couleur d'accent** : Germain a une préférence (bleu, ambre, vert,
   violet, autre) ou "à toi de juger" ?
5. **Typographie** : Inter + Space Mono actuels (héritage Streamlit), ou
   tester une combo plus distinctive (Geist, Söhne-like, etc.) ?

## Livrable attendu

### 1. `DESIGN.md` à la racine de `frontend/`

Document de référence court (< 500 lignes) avec :
- Palette de tokens couleurs (CSS variables) : background levels, foreground
  levels, accent, success/warning/error, borders
- Typography scale : familles, tailles (xs → 4xl), poids, line-heights
- Spacing scale (1 → 32, doublé sur tablette+)
- Radii (sm / md / lg / full)
- Shadows (none / sm / md / lg)
- Theming dark/light si retenu
- Catalogue des primitives (Button, Card, Input, Select, Tabs, Dialog,
  Badge, Toast, EmptyState, Skeleton…)
- Patterns d'écran : structure d'un module type (header + tabs + content),
  vue dashboard, vue liste, vue détail, vue formulaire
- Règles de responsive (breakpoints, sidebar collapse, tab → drawer)
- Règles d'accessibilité de base (focus visibles, contrastes WCAG AA)
- À la fin : section "Pour les futures CONV" — comment respecter le système

### 2. `frontend/components/ui/` — primitives réutilisables

Fichiers < 200 lignes chacun (cf. PLAN note 9) :
- `button.tsx` — variants (primary, secondary, ghost, destructive), sizes
- `card.tsx` — avec header/body/footer compositables
- `input.tsx` + `textarea.tsx`
- `select.tsx`
- `tabs.tsx`
- `dialog.tsx` + `drawer.tsx`
- `badge.tsx`
- `empty-state.tsx`
- `skeleton.tsx`
- `toast.tsx` (ou intégration sonner / radix-toast)
- `chart-frame.tsx` (wrapper standard pour les graphes SVG existants)
- `theme-provider.tsx` + `theme-toggle.tsx` si dark/light

### 3. Migration des écrans existants

Réécrire chaque module pour utiliser les primitives :
- `frontend/src/app/page.tsx` (accueil — grille des 11 modules)
- `frontend/src/app/layout.tsx` (navigation, theme provider)
- `frontend/components/garderobe/*`
- `frontend/components/sante/*`
- `frontend/components/entrainement/*`
- `frontend/components/agenda/*`

**Aucune régression fonctionnelle.** Tous les boutons, formulaires et flows
doivent continuer à marcher exactement comme avant. Cette CONV ne touche
PAS aux endpoints ni à la logique métier.

### 4. Mobile-first explicit

Tester chaque écran à `375px` (iPhone SE), `768px` (tablette), `1280px`
(laptop) et `1920px`. Au minimum :
- La navigation doit être utilisable au pouce
- Les tableaux denses doivent défiler ou se simplifier
- Les modales doivent devenir drawers en mobile
- Aucun débordement horizontal

## Hors-scope

- **Ne PAS toucher** à `frontend/src/app/etudes/`, `frontend/components/etudes/`,
  ni `frontend/lib/etudes.ts` — CONV 6 est en cours en parallèle. Le merge
  se fera après. CONV 6 aura juste à suivre le `DESIGN.md` livré ici.
- **Ne PAS toucher** au backend (`backend/`), à aucun endpoint, à aucun modèle.
- **Ne PAS ajouter de nouvelles fonctionnalités** — uniquement refonte visuelle
  et structurelle des composants.
- **Ne PAS ajouter de dépendances lourdes** : on reste sur Tailwind + Radix
  primitives bas niveau (optionnel) + lucide-react pour les icônes (déjà
  présent ou à ajouter).
- Animations complexes (Framer Motion etc.) : V2, pas dans cette passe.
- i18n : on reste full français pour l'instant.

## Dépendances et impact sur les autres CONV

- **Prérequis** : 4 CONV UI livrées (✅ 2, 3, 5, 7).
- **CONV 6 (Études)** : en cours en parallèle. Les briefs des deux ne se
  marchent pas dessus tant que cette CONV évite le dossier `etudes/`.
  CONV 6 finira avec son design "v1" — un petit chantier de rattrapage
  sera nécessaire après (1-2h de travail, à ajouter au CONV6_DONE.md).
- **Toutes les CONV restantes (4, 8-15)** : leurs briefs doivent référencer
  `frontend/DESIGN.md` comme contrat strict. Je (orchestrateur) ajouterai
  une note dans `PLAN.md` "à respecter dans toutes les CONV suivantes".

## Suggestions techniques

- Garder `globals.css` comme source des CSS variables. Pas de styled-components
  ni d'emotion.
- Pour les primitives, s'inspirer de **shadcn/ui** sans installer le CLI :
  les patrons sont déjà bien établis. Copier-adapter, pas pull en dépendance.
- Pour les graphes (svg inline aujourd'hui dans santé et entraînement),
  introduire un composant `ChartFrame` qui gère titre, légende, tooltip
  hover et responsive — chaque module garde son rendu interne.
- Theme provider basé sur `next-themes` si dark/light retenu (très léger,
  ~3 ko).
- Tester les contrastes avec les outils Chrome DevTools (WCAG AA = ratio
  4.5 pour le texte normal, 3 pour le large).

## Critères de succès

- [ ] `frontend/DESIGN.md` existe et est complet (tokens, primitives, patterns)
- [ ] `frontend/components/ui/` contient les ~12 primitives, chacune < 200 lignes
- [ ] Les 4 modules existants (Garde-robe, Santé, Entraînement, Agenda) +
  accueil + layout sont migrés et utilisent les primitives
- [ ] Aucune régression fonctionnelle (parcours manuel rapide : créer un
  vêtement, logger un poids, logger une série, ajouter un événement)
- [ ] Responsive testé sur 375 / 768 / 1280 / 1920
- [ ] Theme dark/light fonctionne (si retenu)
- [ ] Le dossier `etudes/` est intact (vérifier avec `git diff`)
- [ ] Tests frontend existants (s'il y en a) passent ; sinon vérifier au
  moins que le build Next.js compile sans erreur

## Action utilisateur finale

Commit unique scopé `feat(ui): design system + migrate existing modules
(CONV DESIGN)`. Livrer `CONV_DESIGN_DONE.md` sur le modèle des autres récaps
de clôture, avec en plus :
- Captures avant/après de chaque module
- Tableau des "breakings" (rien ne devrait casser, mais lister les
  équivalences quand un composant a été restructuré)
- Recommandations pour CONV 6 (Études) pour la mise à niveau post-merge

---

## Prompt d'amorce (à copier en début de nouvelle conversation)

```
Je veux faire une passe design transverse sur Mission Control. 4 modules UI
sont déjà livrés (Garde-robe, Santé, Entraînement, Agenda) + un dashboard
d'accueil. Avant que les 9 modules restants s'ajoutent, je veux poser un
vrai design system, faire l'audit des incohérences actuelles, et migrer
les écrans existants pour qu'ils soient cohérents.

ATTENTION CRITIQUE : une autre conversation Claude est en cours en parallèle
sur CONV 6 (module Études). Tu ne dois PAS toucher à :
- frontend/src/app/etudes/
- frontend/components/etudes/
- frontend/lib/etudes.ts
Vérifier avec git diff à la fin que ces fichiers sont intacts.

Lis d'abord ces fichiers pour le contexte complet :

1. C:\Users\germa\Documents\GitHub\mission-control\orchestration\PLAN.md
   (sections "Notes héritées" — notamment notes 9 et 12 critiques pour
    cette passe)
2. C:\Users\germa\Documents\GitHub\mission-control\orchestration\CONV_DESIGN.md
   (le brief complet : objectif, livrable, hors-scope, critères de succès,
    décisions à prendre)
3. CONV1_DONE.md + CONV3_DONE.md + CONV5_DONE.md + CONV7_DONE.md
   (état actuel, conventions)

Puis explore les surfaces UI existantes :
- frontend/src/app/page.tsx + layout.tsx
- frontend/components/garderobe/ + frontend/src/app/garderobe/
- frontend/components/sante/ + frontend/src/app/sante/
- frontend/components/entrainement/ + frontend/src/app/entrainement/
- frontend/components/agenda/ + frontend/src/app/agenda/
- frontend/app/globals.css

Stack à respecter strictement :
- Next.js 15.5 + React 19.1 + TypeScript 5
- TailwindCSS 4 + CSS variables (style shadcn-like, composants maison)
- Pas de UI lib lourde, juste des primitives bas niveau si besoin
  (Radix UI primitives OK, lucide-react pour les icônes)
- Files Python/TSX < 200 lignes chacun (cf. PLAN note 9)
- Sandbox FUSE désynchronisé : écriture finale via `cat << EOF` pour les
  fichiers critiques côté sandbox (cf. PLAN note 12)

Après lecture, pose-moi les 5 questions de "Décisions à prendre au démarrage"
du brief. Pour la question du mood visuel, montre-moi des références
concrètes (sites/screenshots) pour que je puisse trancher avec contexte.

Une fois mes réponses :
1. Produis d'abord un audit court (< 1 page) : ce qui est cohérent, ce qui
   diverge, ce qui pose problème en mobile, etc.
2. Rédige `frontend/DESIGN.md` (la spec).
3. Crée `frontend/components/ui/` avec les ~12 primitives.
4. Migre les 4 modules + accueil + layout.
5. Vérifie mobile (375/768/1280/1920) et que le build Next.js passe.
6. Vérifie que le dossier etudes/ est intact.

À la fin : `CONV_DESIGN_DONE.md` avec captures avant/après, breakings,
recommandations pour CONV 6. Commit unique :
`feat(ui): design system + migrate existing modules (CONV DESIGN)`.
```
