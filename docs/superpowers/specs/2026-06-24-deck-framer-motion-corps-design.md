# Refonte Deck Framer Motion + expérience prototype « Corps »

**Date :** 2026-06-24
**Statut :** Design validé (en attente de relecture finale avant plan d'implémentation)

## Contexte

L'accueil (`frontend/src/app/page.tsx` → `components/layout/Deck.tsx`) implémente déjà
une navigation scroll-first : sections plein écran à `scroll-snap-type: y mandatory`,
rangées horizontales de modules par groupe, glassmorphism, polices éditoriales
(Libre Caslon / Public Sans), Dock flottant, transitions de page, animations
scroll-driven CSS (`animation-timeline: view()`), respect de `prefers-reduced-motion`.

La fondation « organique » existe donc déjà. Le véritable manque :

1. **Les sections de domaine sont des rangées de tuiles cliquables identiques** — des
   « cases », pas des « modules d'information ». Aucune donnée vivante n'y est montrée.
2. **L'orchestration d'animation est en CSS natif** — performant mais support partiel
   et orchestration limitée (pas de stagger fin, d'exit, de parallax souris).

## Décisions validées (brainstorming)

| Décision | Choix |
|---|---|
| Cadrage | **Refaire la coquille en Framer Motion** + transformer les sections en modules de données |
| Domaine prototype | **Corps** = groupe *Santé & Performance* (entraînement, cuisine, santé, skincare) |
| Niveau d'interaction | **Vitrine + drill-in** : la section montre l'état vivant, l'action reste sur les pages dédiées |
| Dosage de mouvement | **Expressif & vivant** : parallax multi-couches, tilt 3D, count-up — mais subtil |
| Typographie | Conserver le contraste Libre Caslon (titres) / Public Sans (UI). **`tabular-nums` obligatoire** sur tout chiffre animé |
| Hover modules | **Inertie spring** + tilt 3D **très subtil (quelques degrés max)** |
| Accessibilité | `prefers-reduced-motion` → **toujours des fondus fluides**, mais **zéro parallax / rotation 3D** |

## Principe de stack

- **Bibliothèque : `motion`** (successeur de `framer-motion`, import `motion/react`),
  compatible React 19 / Next 15. Une seule dépendance ajoutée.
- **Le snap reste en CSS** (`scroll-snap-type`). Framer Motion ne fournit pas de snap ;
  un snap JS serait saccadé. Framer Motion pilote **tout le reste** (entrées, sorties,
  parallax, tilt, count-up, transitions). Cette frontière est volontaire.
- **Aucun nouvel endpoint backend.** 100 % des données via hooks existants.

## Architecture des composants

```
components/deck/
  Deck.tsx              ← coquille motion (remplace, à terme, layout/Deck.tsx)
  DeckSection.tsx       ← wrapper générique : orchestration d'entrée (useInView +
                          variants stagger), contexte parallax, exit
  DeckRail.tsx          ← rail de points (indicateur motion qui glisse)
  useDeckNavigation.ts  ← clavier ↑↓←→, scroll-to-section, section active
  experiences/
    CorpsExperience.tsx       ← section prototype (Santé & Performance)
    GenericGroupExperience.tsx ← repli : rangée de cartes (les 6 autres groupes)
  modules/                     ← « modules d'information » (vitrine + drill-in)
    ScoreRingModule.tsx   ← HÉROS : anneau de score, count-up, parallax souris
    MacrosModule.tsx      ← macros du jour (réutilise la logique de MacroBar)
    SleepModule.tsx       ← dernière nuit
    NextWorkoutModule.tsx ← séance du jour / prochaine
    SkincareModule.tsx    ← routine du jour

lib/motion/
  tokens.ts             ← easings, springs, durées (source unique, mappée sur --ease-*)
  variants.ts           ← variants réutilisables (fadeUp, staggerContainer, tilt)
  useParallax.ts        ← position souris normalisée → transform via useSpring
  useCountUp.ts         ← animation de chiffres via useSpring (respecte reduced-motion)
```

### Responsabilités (isolation)

- **`Deck`** : possède le conteneur de scroll + snap, instancie une `DeckSection` par
  groupe, monte le `DeckRail`, branche `useDeckNavigation`. Ne connaît pas le contenu
  des sections.
- **`DeckSection`** : reçoit `children` + un index ; gère l'orchestration d'entrée
  (variants stagger via `useInView({ once: true })`), expose le contexte parallax,
  l'exit. Réutilisable par toutes les expériences.
- **`CorpsExperience`** : compose les 5 modules dans la mise en page éditoriale ;
  ne contient aucune logique d'animation bas-niveau (déléguée aux modules + tokens).
- **Chaque module** : aperçu **lecture seule** d'un hook React Query → rend un `Link`
  drill-in vers sa page. Un module = un fichier focalisé, testable seul.
- **`lib/motion/*`** : primitives sans dépendance au domaine, testables en isolation.

## Mise en page « Corps »

Plein écran, asymétrique, éditoriale (pas une grille) : héros dominant + modules
satellites, beaucoup de vide, titre serif géant.

```
┌───────────────────────────────────────────────────────────┐
│  03 / 07                                                    │
│  Corps                          ← titre serif Libre Caslon  │
│  ─────────                                                  │
│                                                             │
│     ╭───────────╮         Sommeil      7 h 40   ▸          │
│     │   ⬤ 78    │         ────────────────────             │
│     │  score    │         Macros    1 840 / 2 100 kcal  ▸  │
│     ╰───────────╯         ▓▓▓▓▓▓▓░░░                        │
│   anneau héros            Séance du jour  Push · 18 h   ▸   │
│   (parallax souris,       ────────────────────             │
│    count-up)              Skincare    routine soir · 3  ▸   │
└───────────────────────────────────────────────────────────┘
```

## Chorégraphie du mouvement

- **Entrée au scroll** (`useInView`, `once: true`) : stagger — titre slide-up, puis
  anneau (scale + fade), puis modules en cascade (~70 ms d'écart), springs doux.
- **Anneau héros** : count-up du score (0 → valeur) en `tabular-nums` ; arc SVG qui se
  remplit (`pathLength`) ; **parallax souris** (anneau + halo décalés de quelques px en
  sens inverse de la souris, via `useSpring`).
- **Modules satellites** : **tilt 3D au survol, très subtil (≈ ±4° max)**, suivant la
  position de la souris ; **inertie spring** sur le retour (pas de snap brutal) ; ombre
  douce qui réagit. Chiffres en count-up `tabular-nums` à l'entrée.
- **Parallax multi-couches au scroll** : titre serif et halo se déplacent à vitesses
  différentes via `useScroll` + `useTransform`.
- **Sortie** : léger fade + slide quand la section quitte le viewport.

## Typographie

- Titres de section : `font-display` (Libre Caslon) — inchangé.
- UI / libellés : Public Sans — inchangé.
- **Tout chiffre animé** (score, compteurs, macros) : classe `tabular-nums` pour des
  largeurs de glyphes fixes → aucun « saut » horizontal pendant le count-up.

## Accessibilité — `prefers-reduced-motion`

Via `useReducedMotion()` (Framer Motion), quand l'utilisateur a activé la réduction :

- **Conservé** : fondus fluides à l'entrée/sortie (les éléments « fondent » toujours).
- **Désactivé** : parallax souris, parallax scroll, tilt 3D, count-up (les chiffres
  s'affichent à leur valeur finale immédiatement).

Parité avec le `@media (prefers-reduced-motion: reduce)` CSS déjà en place ; le snap
passe en `proximity` comme aujourd'hui.

## Données

100 % via hooks React Query existants — aucun nouvel endpoint :

| Module | Source |
|---|---|
| ScoreRing | `useScore()` → `/sante/score` (`ScoreDay`: score + sous-scores sommeil/sport/nutrition) |
| Sleep | `lib/queries/sante` / `lib/sante.ts` (données sommeil de la nuit) |
| Macros | logique de `components/sante/MacroBar` + hook macros du jour |
| NextWorkout | `lib/queries` / `lib/entrainement.ts` (séance du jour) |
| Skincare | `/api/skincare/today` (déjà consommé par `DaySignals`) |

États de chaque module : **skeleton** au chargement ; **dégradation propre** si un
endpoint tombe (l'aperçu se réduit / disparaît sans casser la section), sur le modèle
de `DaySignals`.

## Tests

- **TDD primitives** (`lib/motion/`) — Vitest, logique pure :
  - `useCountUp` : clamp, valeur finale, `reduced-motion` → valeur immédiate.
  - `useParallax` : normalisation souris → transform borné ; désactivé si reduced-motion.
  - `variants` : structure stagger correcte.
- **Modules** — Testing Library : états loading / ready / erreur, présence du `Link`
  drill-in, libellés a11y, `tabular-nums` sur les chiffres.
- **E2E Playwright** : navigation scroll-snap, rail actif, clavier ↑↓←→, **capture
  visuelle** de la section Corps (garde-fou anti-régression).

## Migration progressive

On construit `components/deck/` **à côté** de `components/layout/Deck.tsx` (pas de
remplacement destructif). Bascule de `page.tsx` vers le nouveau `Deck` une fois Corps
validé. Les 6 autres groupes utilisent `GenericGroupExperience` (rendu « rangée de
cartes » équivalent à l'actuel) puis sont migrés un par un. **Aucune page cassée à
aucune étape.** L'ancien `layout/Deck.tsx` n'est supprimé qu'après migration complète.

## Hors périmètre (YAGNI)

- Migration des 6 autres expériences de domaine (faite après validation du prototype).
- Tout nouvel endpoint ou changement backend.
- Refonte du Dock, de la nav mobile, de la palette de commandes.
- Snap piloté en JavaScript.
