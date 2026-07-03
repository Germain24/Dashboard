# Passe de conformité Verre Clair — 29 modules, densité, stagger, chargement — Design

> Spec du chantier P1 §2 tranche 2 d'`orchestration/en-cours/improvements.md`
> (items 2.1 et 2.6, + restes du §1 qui touchent les mêmes fichiers : migration
> des usages CSS `.stagger` (1.3) et fin du cumul de fondus). Succède aux
> fondations livrées le 2026-07-03 (`orchestration/finis/2026-07-02-fondations-verre-clair-design.md`).

## Objectif

Appliquer le design system Verre Clair de façon ÉGALE sur les 29 segments de
route : palette par tokens, typographie disciplinée, fondus non cumulés,
cascades motion, chargement sans disparition de header, densité maîtrisée sur
les pages lourdes. Ce qui est mesurable devient une garde CI (même mécanique
que `glass-recipes.test.ts`).

Décisions utilisateur (brainstorming 2026-07-03) :
- Découpage **par lots de catégorie du Deck** (pas module par module), 1 commit par lot.
- Checklist codifiée + garde automatisée pour le mesurable ; le subjectif
  (typo, espacements) = passe manuelle revue par lot.
- 2.6 (sections repliables) limité à **finance et santé**.
- Exécution subagent-driven (Sonnet) enchaînée sans pause.

## État des lieux (greps 2026-07-03)

- 31 couleurs hardcodées (`-[#…]`, `rgb(…)`, hex) dans 19 fichiers de
  `components/` — surtout des charts (budget/charts.tsx, finance, deck ScoreRing).
- 8 fichiers utilisent encore la classe CSS dépréciée `.stagger` :
  garderobe/InventaireTab, finance/SuiviTab, budget/MoisTab, budget/EnveloppesTab,
  livres/BibliothequeTab, habitudes/AujourdhuiTab, sante/JourTab,
  entrainement/AujourdhuiTab.
- `animate-fade-in`/`animate-fade-in-up` posés en racine de page dans ~10 pages
  (cumul avec PageTransition qui anime déjà l'entrée de module).
- `Sante.tsx` et `Garderobe.tsx` remplacent TOUT leur render (ModuleHeader
  compris) pendant leurs queries → flash du header sur cache froid.

## Contraintes

- Palette DESIGN.md uniquement (marine #04142c, laiton #C5A059, vert #536252,
  oxblood #501312, slate #384762, ocre #8a6d1f, vermilion #ba1a1a) ; les hex ne
  vivent QUE dans `frontend/lib/design/colors.ts` (et globals.css/DESIGN.md).
- Aucun changement d'API des composants ui/ ; aucune nouvelle dépendance npm.
- `prefers-reduced-motion` respecté par toute nouvelle animation (`useReducedMotion`
  ou tokens motion existants).
- Frontend : `npx vitest run`, `npx tsc --noEmit` depuis `frontend/`.
- Le rendu des données ne change pas — c'est une passe de FORME (couleurs,
  typo, espacements, animations, états de chargement).

## 1. La checklist de conformité (appliquée à chaque module d'un lot)

1. **Couleurs → tokens.** Aucun hex/`rgb()`/`-[#…]` dans les .tsx : états
   sémantiques → `var(--success|warning|destructive|info|tertiary)` ; charts →
   imports depuis `lib/design/colors.ts` (§2). Les couleurs de DONNÉES
   (catégories budget, secteurs ETF…) passent par `CHART_SERIES`.
2. **Typographie.** Display (Libre Caslon) réservé aux h1/`font-display` ;
   titres de cartes = Title (`text-sm font-semibold`) ; labels = 12 px
   `font-medium` ; chiffres financiers en `font-mono tabular-nums`. Pas de
   `text-2xl/3xl font-bold` hors valeur display assumée (`font-display`).
3. **Fondus non cumulés.** Le wrapper RACINE d'une page module ne porte plus
   `animate-fade-in` (PageTransition anime déjà l'entrée). `animate-fade-in-up`
   reste légitime pour le contenu d'un CHANGEMENT D'ONGLET (keyé, intra-module)
   et dans les loading.tsx.
4. **Cascades.** Les grilles/listes qui utilisaient `.stagger` passent à
   `StaggerGroup`/`StaggerItem` (lib/motion) — 8 fichiers connus.
5. **Chargement.** Le ModuleHeader ne disparaît jamais : pattern « header
   toujours rendu, fallback = skeleton/spinner du CONTENU seulement ».
   Correctif ciblé sur `Sante.tsx` et `Garderobe.tsx` ; les autres modules sont
   vérifiés au passage du lot.
6. **Espacements.** Rythme du gabarit : contenu `p-6`, grilles `gap-3`/`gap-4`,
   sections `space-y-6` — corriger les écarts flagrants, sans pixel-perfect.

## 2. `lib/design/colors.ts` — palette centralisée pour les charts

```ts
export const INK = { navy: "#04142c", brass: "#C5A059", green: "#536252",
  oxblood: "#501312", slate: "#384762", ochre: "#8a6d1f", vermilion: "#ba1a1a" };
// Série catégorielle pour les charts (ordre = contraste maximal entre voisins)
export const CHART_SERIES = [INK.navy, INK.brass, INK.green, INK.oxblood,
  INK.slate, INK.ochre, INK.vermilion];
```

Les composants charts (recharts/SVG inline) importent `CHART_SERIES`/`INK` au
lieu de littéraux. Pour les surfaces/textes non-chart, on utilise les
custom properties CSS — jamais `INK` (qui ne suit pas le thème sombre).

## 3. Garde automatisée — `__tests__/design/conformity.test.ts`

Même mécanique git-grep que `glass-recipes.test.ts` :
- **Interdit** `#[0-9a-fA-F]{6}` dans `components/**.tsx` et `src/**.tsx`,
  MOINS une **whitelist nominative** (les 19 fichiers du constat, listée dans le
  test) qui se vide au fil des lots — le lot final l'asserte VIDE.
- **Interdit** la classe `.stagger` (`className="...stagger..."`) partout, dès
  le lot qui migre le dernier usage.
- Le test échoue avec la liste des fichiers fautifs (message actionnable).

## 4. `CollapsibleSection` (ui/) — densité 2.6

`frontend/components/ui/collapsible-section.tsx` :
- Props : `{ title: string; defaultOpen?: boolean; children; className? }`.
- En-tête bouton (Title 14 px semibold, chevron qui tourne en `--spring`),
  zone qui s'ouvre/ferme en hauteur animée (motion, `useReducedMotion` → pas
  d'animation), `aria-expanded`/`aria-controls` corrects.
- Appliquée UNIQUEMENT aux pages denses : finance (sections secondaires de
  SuiviTab/PatrimoineTab) et santé (sections secondaires du JourTab) — les
  sections primaires restent ouvertes par défaut (`defaultOpen`).

## 5. Pattern chargement sans flash (Sante, Garderobe)

Le early-return global `if (xQ.isLoading) return <fallback plein écran>` est
remplacé par : ModuleHeader TOUJOURS rendu ; le fallback (blocs skeleton de la
tranche 1) ne couvre que la zone contenu. Aucune modification des queries.

## 6. Les lots (ordre d'exécution)

| Lot | Modules (segments) |
|---|---|
| 0 | Primitives + gardes : `colors.ts`, `CollapsibleSection`, `conformity.test.ts` (whitelist pleine) |
| 1 Finance | finance, patrimoine, budget (+ 2.6 finance) |
| 2 Corps | sante, entrainement, score, skincare, garderobe (+ 2.6 santé, + fix flash ×2) |
| 3 Quotidien | cuisine, routines, agenda, habitudes |
| 4 Savoir | etudes, travail, jobs, langues, documents, livres |
| 5 Loisirs + transverse | musique, film, series, gaming, voyage, journal + vue-360, bilan, snapshot, objectifs, parametres, donnees + composants partagés (deck, CommandPalette) |
| 6 Clôture | suppression du bloc CSS `.stagger` (globals.css), whitelist vidée assertée, marquage improvements.md (2.1, 2.6, 1.3 complet, cumul de fondus), docs → finis/ |

Chaque lot : appliquer la checklist §1 à chaque module du lot, vider la
whitelist des fichiers du lot, tests + tsc verts, 1 commit.

## Architecture & tests

- Nouveaux fichiers : `lib/design/colors.ts`, `components/ui/collapsible-section.tsx`,
  `__tests__/design/conformity.test.ts`, `__tests__/components/collapsible-section.test.tsx`.
- Tests composant : CollapsibleSection (ouvert/fermé, aria, defaultOpen).
- La garde conformity est le critère d'acceptation mesurable ; le subjectif est
  contrôlé par la revue de chaque lot + un QA visuel final (2 thèmes).

## Hors périmètre

- §4 performances, 3.2/3.3 rangement, 1.2 View Transitions, 1.7 Dock layoutId,
  1.8 transitions de données, toasts sonner (1.6 restant) → chantiers suivants.
- Aucun changement de logique métier, de queries ou d'API backend.
