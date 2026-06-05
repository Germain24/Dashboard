---
name: Mission Control
description: Heritage Editorial — papier crème, encre marine, pour un life OS personnel et dense.
colors:
  academic-navy: "#04142c"
  brass: "#C5A059"
  editorial-oxblood: "#501312"
  english-green: "#536252"
  ochre: "#8a6d1f"
  vermilion: "#ba1a1a"
  slate-info: "#384762"
  paper-cream: "#faf9f5"
  paper-subtle: "#f4f4f0"
  card-white: "#ffffff"
  ink: "#1b1c1a"
  muted-ink: "#44474d"
  muted-paper: "#efeeea"
  border-grey: "#c5c6ce"
  midnight-marine: "#0B121E"
typography:
  display:
    fontFamily: "Libre Caslon Text, Georgia, 'Times New Roman', serif"
    fontSize: "1.875rem"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "2px"
  md: "4px"
  lg: "8px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
components:
  button-primary:
    backgroundColor: "{colors.academic-navy}"
    textColor: "{colors.card-white}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted-ink}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  button-destructive:
    backgroundColor: "{colors.vermilion}"
    textColor: "{colors.card-white}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "0 12px"
  card:
    backgroundColor: "{colors.card-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "32px"
    padding: "4px 12px"
  badge-default:
    backgroundColor: "{colors.muted-paper}"
    textColor: "{colors.muted-ink}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
---

# Design System: Mission Control

## 1. Overview

**Creative North Star: "The Old Money Almanac"**

Mission Control se tient comme un almanach patrimonial relié : papier crème, encre
marine, des chiffres tenus avec la rigueur tranquille d'un grand livre. C'est un
outil de pilotage de vie pour un seul lecteur, dense et quotidien, où l'interface se
lit comme un document bien composé plutôt que comme un tableau de bord à la mode. La
personnalité tient en trois mots : posé, éditorial, durable. La voix est sobre, en
français (fr-CA), sans jargon.

La densité est assumée : tableaux, formulaires, séries de chiffres, seize modules qui
partagent le même vocabulaire d'écran à écran. La couleur ne décore jamais ; elle
porte l'état et l'action. Le serif (Libre Caslon Text) est réservé aux titres et au
wordmark ; tout le reste, la donnée comprise, reste en sans (Public Sans) pour la
lisibilité. Le thème suit le papier en clair et bascule sur une marine de minuit
rehaussée de laiton en sombre.

Ce système rejette explicitement : le dashboard « AI SaaS » générique (dégradés
crème-et-violet, grilles de cartes identiques, gabarit hero-metric, eyebrows en
petites majuscules trackées) ; et les kits Material/Bootstrap par défaut (composants
non travaillés, ombres lourdes, look « admin panel »).

**Key Characteristics:**
- Papier crème + encre marine ; une seule voix interactive (la marine académique).
- Serif éditorial pour les titres, sans institutionnel pour la donnée dense.
- Palette restreinte ; les couleurs sémantiques portées en couches tonales douces.
- Rayons courts (2–8 px), ombres lithographiques discrètes teintées marine.
- Clair = papier ; sombre = marine de minuit + laiton.

## 2. Colors

Une palette restreinte ancrée sur le papier crème et l'encre marine, où chaque couleur
saturée a un rôle d'état précis, jamais décoratif.

### Primary
- **Academic Navy** (#04142c) : la voix interactive unique. Action primaire (boutons
  pleins), anneau de focus, item de nav actif, liens. En sombre, l'action primaire
  passe à un bleu glace (#c8d6f0) et l'accent interactif devient le laiton.

### Secondary
- **Brass / Laiton** (#C5A059) : accent interactif du thème sombre (focus, nav active,
  surlignages) — la contrepartie chaude de la marine quand le fond devient minuit.

### Tertiary
- **Editorial Oxblood** (#501312) : bordeaux éditorial pour états actifs, surlignages
  et puces (variante claire `#ffdad7` en lavis). Accent rare, jamais une surface.

### Neutral
- **Paper Cream** (#faf9f5) : fond principal (le papier).
- **Paper Subtle** (#f4f4f0) : sidebar et fonds légèrement distincts.
- **Card White** (#ffffff) : cartes, soulevées du papier crème.
- **Ink** (#1b1c1a) : texte principal.
- **Muted Ink** (#44474d) : texte secondaire, labels.
- **Muted Paper** (#efeeea) : surfaces hover / accent au repos.
- **Border Grey** (#c5c6ce) : bordures, filets, séparateurs.
- **Midnight Marine** (#0B121E) : fond du thème sombre.

Couleurs sémantiques (portées en couches tonales `*-muted` douces, jamais en aplat
saturé sur un état inactif) : **English Green** (#536252, succès), **Ochre** (#8a6d1f,
avertissement), **Vermilion** (#ba1a1a, destructif), **Slate** (#384762, info).

### Named Rules
**The One Voice Rule.** La marine académique est le *seul* accent interactif en clair
(laiton en sombre). Elle marque le focus, la nav active, les liens et l'action
primaire — rien d'autre. Sa rareté fait sa force ; ne jamais la dépenser en décor.

**The Ink-on-Paper Rule.** Le corps de texte est de l'encre (#1b1c1a) sur du papier,
pas du gris clair « pour l'élégance ». Le gris est réservé au texte secondaire
(#44474d), jamais au corps principal.

## 3. Typography

**Display Font:** Libre Caslon Text (repli Georgia, "Times New Roman", serif)
**Body / UI Font:** Public Sans (repli ui-sans-serif, system-ui, sans-serif)
**Mono Font:** ui-monospace (SFMono-Regular, Menlo)

**Character:** Un appariement sur axe de contraste — un serif de transition littéraire
pour la voix éditoriale des titres, un sans humaniste institutionnel pour la clarté de
la donnée dense. Le serif apporte l'héritage ; le sans tient la lisibilité.

### Hierarchy
- **Display** (Libre Caslon, 400, ~1.875rem/30px, line-height 1.15, letter-spacing
  -0.01em) : `h1` et wordmark uniquement. La seule présence du serif dans l'UI.
- **Title** (Public Sans, 600, 0.875rem/14px, tight) : titres de carte, en-têtes de
  section (`h2`/`h3`), labels d'onglet.
- **Body** (Public Sans, 400, 0.9375rem/15px, line-height 1.6) : corps et prose ;
  ligne de prose plafonnée à 65–75ch.
- **Label** (Public Sans, 500, 0.75rem/12px) : labels de champ, légendes, métadonnées
  ; teinte Muted Ink.
- **Mono** (ui-monospace, 0.875rem) : valeurs numériques alignées (`tabular-nums`) là
  où la colonne doit cadrer.

### Named Rules
**The Serif-for-Headlines-Only Rule.** Le serif (Libre Caslon) est interdit dans les
boutons, labels, champs et cellules de données. Il vit dans `h1` et le wordmark ;
partout ailleurs, Public Sans. Un serif dans une cellule de tableau est un bug.

## 4. Elevation

Lithographie légère. Les surfaces ne sont pas plates : elles portent une ombre
ambiante discrète — nette, à flou large, faible opacité, teintée marine en clair (et
noire en sombre) — qui soulève les cartes du papier sans jamais peser. La profondeur
est tonale autant qu'ombrée : papier crème → blanc carte → bordure fine.

### Shadow Vocabulary
- **shadow-sm** (`box-shadow: 0 1px 2px 0 rgb(26 41 66 / 0.04)`) : boutons pleins,
  badges soulevés.
- **shadow** (`box-shadow: 0 2px 8px 0 rgb(26 41 66 / 0.06)`) : cartes au repos.
- **shadow-md** (`box-shadow: 0 4px 16px -2px rgb(26 41 66 / 0.08)`) : popovers,
  éléments survolés (`.card-hover`).
- **shadow-lg** (`box-shadow: 0 4px 20px 0 rgb(26 41 66 / 0.10)`) : dialogues,
  surfaces flottantes (overlay/modal).

### Named Rules
**The Lithograph Rule.** Une ombre est nette, à flou large et à faible opacité,
teintée de la marine (`rgb(26 41 66 / …)`) en clair, noire en sombre. Jamais une ombre
dure et sombre type 2014, jamais un halo coloré. Au survol, la carte se soulève d'un
seul pixel (`translateY(-1px)`) et la bordure prend la teinte marine.

## 5. Components

Le feel d'ensemble est tactile et confiant : retours nets (l'appui enfonce le bouton
à `scale(0.97)`), hovers visibles, espacement mesuré. Vocabulaire identique d'écran à
écran ; aucun contrôle réinventé.

### Buttons
- **Shape:** coins doucement arrondis (4px, `--radius`).
- **Tailles:** sm 28px / md 32px / lg 40px de haut ; padding horizontal 10–16px ;
  texte 12–16px selon la taille.
- **Primary:** aplat marine académique (#04142c), texte blanc, `shadow-sm` ; hover =
  opacité 90 %.
- **Secondary / Outline:** bordure fine (#c5c6ce), fond transparent, texte encre ;
  hover = fond Muted Paper.
- **Ghost:** transparent, texte Muted Ink ; hover = fond Muted Paper + texte encre.
- **Destructive / Success:** aplat sémantique (vermillon / vert anglais), texte clair.
- **Link:** texte marine, soulignement au survol, pas de boîte.
- **Feedback:** `active:scale(0.97)`, transition 100ms, anneau de focus marine 2px.

### Chips / Badges
- **Shape:** rayon 2px (`--radius-sm`), padding 2×8px, texte 12px medium.
- **State:** fonds tonaux doux par rôle — Muted Paper (défaut), `success/warning/`
  `destructive/info-muted` pour les statuts, ou bordure fine pour la variante outline.

### Cards / Containers
- **Corner Style:** 8px (`--radius-lg`).
- **Background:** blanc carte (#ffffff) en clair, soulevé du papier crème.
- **Shadow Strategy:** `shadow` au repos ; `.card-hover` monte à `shadow-md` + lift
  -1px + bordure marine. Voir Elevation.
- **Border:** filet fin (#c5c6ce). Le footer de carte porte une bordure haute.
- **Internal Padding:** 16px (`p-4`), header `pb-2`, content `pt-2`.

### Inputs / Fields
- **Style:** hauteur 32px, rayon 4px, bordure fine, fond transparent (pas de gris de
  remplissage), texte encre, placeholder en Muted Ink à contraste suffisant.
- **Focus:** la bordure passe à la marine (`focus:border --ring`), pas d'outline
  doublé. Label au-dessus en Label/Muted Ink.
- **Error / Disabled:** bordure vermillon + message vermillon ; désactivé à 50 %.

### Navigation
- **Item actif:** trois indices cumulés et redondants — lavis marine plein (`ring` à
  12 %, indice non chromatique perceptible en daltonisme), teinte marine du texte et
  de l'icône (`--nav-active-fg`, assombrie en clair pour rester ≥ 4.5:1), et
  `aria-current` côté markup. Sidebar sur couche papier distincte (#f4f4f0), repli en
  rail d'icônes entre md et lg.

## 6. Do's and Don'ts

### Do:
- **Do** réserver la marine académique (#04142c) au focus, à la nav active, aux liens
  et à l'action primaire — la « One Voice Rule ». Laiton (#C5A059) en sombre.
- **Do** garder le corps de texte en encre (#1b1c1a) ; le gris (#44474d) est pour le
  secondaire, jamais pour le corps.
- **Do** réserver Libre Caslon aux `h1` et au wordmark ; toute la donnée et l'UI
  restent en Public Sans.
- **Do** porter les statuts en couches tonales `*-muted` douces, et coder l'état par au
  moins deux indices (couleur + label/icône), jamais la couleur seule.
- **Do** des ombres lithographiques (nettes, flou large, opacité ≤ 0.10, teintées
  marine) ; au survol, lift -1px + bordure marine.

### Don't:
- **Don't** virer au dashboard « AI SaaS » générique : pas de dégradés crème-et-violet,
  pas de grilles de cartes identiques, pas de gabarit hero-metric, pas d'eyebrows en
  petites majuscules trackées au-dessus de chaque section.
- **Don't** retomber sur un kit Material/Bootstrap par défaut : composants non
  travaillés, ombres dures et sombres, look « admin panel » générique.
- **Don't** mettre du serif (Libre Caslon) dans un bouton, un label, un champ ou une
  cellule de tableau.
- **Don't** utiliser un `border-left`/`border-right` coloré > 1px comme bandeau
  d'accent sur une carte ou une alerte ; bordure pleine ou fond teinté à la place.
- **Don't** remplir les champs d'un gris de fond « pour faire UI » ni écrire le corps
  en gris clair : c'est la première raison qu'une interface paraisse illisible.
- **Don't** dépenser la marine en décoration : si elle n'indique ni état ni action,
  elle est de trop.
