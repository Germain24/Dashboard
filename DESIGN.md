---
name: Mission Control
description: Verre Clair — l'almanach old money derrière du verre. Papier crème, encre marine, chrome translucide flouté. Adapté pour écrans tactiles Android et navigation Windows.
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
    fontFamily: "'Libre Caslon Text', Georgia, 'Times New Roman', serif"
    fontSize: "1.875rem"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'Public Sans', Roboto, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'Public Sans', Roboto, 'Segoe UI', sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "'Public Sans', Roboto, 'Segoe UI', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
---

# Design System: Mission Control

## 1. Overview

**Creative North Star: "The Old Money Almanac, Behind Clear Glass"**

Mission Control se tient comme un almanach patrimonial relié, lu derrière une vitre claire. Le design rejette explicitement le look SaaS générique ou l'esthétique fitness saturée. C'est un outil de pilotage de vie dense, pensé pour un seul lecteur, avec l'élégance sobre d'un streetwear japonais bien structuré : coupes franches, matériaux nobles, et espace généreux.

Le système est conçu pour exister en dehors de l'écosystème Apple. La rigueur de l'interface doit dompter les comportements par défaut de Windows et d'Android (OneUI), imposant le silence visuel là où les OS ajoutent du bruit.

## 2. Colors

Une palette restreinte ancrée sur le papier crème et l'encre marine. La couleur ne décore jamais ; elle porte l'état et l'action.

* **Academic Navy (#04142c) :** La voix interactive unique. Utilisée pour l'action primaire, l'anneau de focus et la navigation active.
* **Brass / Laiton (#C5A059) :** L'accent interactif du thème sombre.
* **Paper Cream (#faf9f5) :** Le fond principal de l'application.
* **Ink (#1b1c1a) :** Le texte principal. L'encre sur le papier.
* **English Green (#536252) :** Succès discret, utilisé en sourdine (ex: validation d'un macro de meal prep).
* **Muted Ink (#44474d) :** Texte secondaire et libellés.

## 3. Typography

Un appariement sur axe de contraste. Un serif littéraire pour la voix éditoriale, un sans-serif humaniste pour la donnée, et une police à chasse fixe rigoureuse pour les calculs quantitatifs et l'automatisation.

| Rôle | Police | Poids | Taille / Hauteur | Usage Exclusif |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | Libre Caslon Text | 400 | 30px / 1.15 | En-têtes (h1), wordmark, citations marquantes. |
| **Title** | Public Sans | 600 | 14px / 1.20 | Titres de cartes, onglets, en-têtes de sections. |
| **Body** | Public Sans | 400 | 15px / 1.60 | Corps de texte, notes d'économie, prose. |
| **Label** | Public Sans | 500 | 12px / 1.40 | Métadonnées, légendes, labels de champs. |
| **Mono** | JetBrains Mono | 400 | 14px / 1.50 | Scripts Python (API Spotify), ratios Sharpe/Omega. |

## 4. Elevation & Matière

La profondeur vient d'une approche lithographique. Les ombres ne sont pas des halos, mais des encrages précis.

* **Le Verre (`--card`) :** Translucide léger (`rgb(255 255 255 / 0.72)`) avec un flou net (`backdrop-filter: blur(18px) saturate(1.4)`).
* **Le Liseré (`--glass-highlight`) :** La tranche du verre est simulée par un encart lumineux très fin `inset 0 1px 0 rgba(255, 255, 255, 0.4)`.
* **Les Ombres :** Teintées de marine (`rgba(4, 20, 44, 0.05)`), nettes, à flou large. Jamais de gris ou de noir pur en mode clair. Au survol, la carte se soulève de 1px (`translateY(-1px)`).

## 5. Plateformes & Quincaillerie (Windows / Android)

* **The Seamless Scroll Rule :** Les barres de défilement natives de Windows sont bannies. Redessinées en CSS (`::-webkit-scrollbar`) : largeur de 6px, fond transparent, poignée arrondie en `rgba(68, 71, 77, 0.2)` qui passe à `0.4` au survol.
* **Oversize Structuré (Touch Targets) :** Sur l'écran Samsung, les boutons peuvent paraître visuellement fins (32px de haut), mais leur zone cliquable (padding ou pseudo-élément) doit atteindre au moins `44px` pour une navigation sans erreur.
* **Anti-Tap Highlights :** Interdiction des flashs bleus/gris d'Android lors d'un appui tactile (`-webkit-tap-highlight-color: transparent;`).

## 6. Cinématique et Navigation (Liquid Glass)

L'animation indique le poids, la matière et la provenance de l'information. Easing global : `cubic-bezier(0.22, 1, 0.36, 1)` ; les transforms tactiles (cartes, points, pastilles) suivent un ressort doux (`--spring`, léger dépassement « façon Apple »).

* **Le Deck (accueil, remplace la sidebar) :** navigation immersive à deux axes, façon stories. Scroll **vertical** = une section plein écran par catégorie (`scroll-snap-type: y mandatory`) ; scroll **horizontal** = les modules de la catégorie, en rangée de cartes de verre (`snap x`). Chaque section « pop » en entrant dans le viewport (scroll-driven animation `animation-timeline: view()`, dégradation propre si non supportée). Un rail de points à droite indique la section courante et permet d'y sauter. Premier écran : volet « Aujourd'hui ».
* **Le Dock (toutes pages) :** barre de verre flottante en bas-centre (`.glass-panel`, pastille `--radius-full`), façon dock macOS — accueil, recherche (⌘K), notifications, densité, thème. Remplace la sidebar ; persistant, jamais collé à un bord.
* **Lavis vivants :** trois nappes radiales (marine, laiton, vert) dérivent très lentement derrière le verre (`washDrift`, 70 s), donnant au translucide quelque chose à réfracter.
* **Palettes & dialogues :** `.glass-modal` (blur 36 px), voile flouté en fond, entrée en `scaleIn` à ressort.
* **Boutons Mécaniques :** au clic, `active:scale(0.98)` ; au survol, lift -1px + ombre montante.

## 7. Structure des Modules (Composants Pratiques)

* **Tableaux de Données (Finance & Gestion) :** Séparateurs *Border Grey* très fins. Les valeurs numériques alignées à droite en `tabular-nums` avec *JetBrains Mono* pour une lisibilité clinique.
* **Cartes de Contrôle (Audio & Routines) :** Espacement interne généreux (`p-5`). Les boutons de lancement d'automatisation utilisent le style *Secondary* (bordure fine, fond verre léger) pour ne pas polluer l'écran de couleurs.
* **Trackers (Musculation & GPA) :** Listes nettes. Pas d'anneaux de progression circulaires fluo. L'avancement est indiqué par des *Badges* tonaux (`success-muted`) ou par du texte clair en *Muted Ink*.

## 8. Do's and Don'ts

* **Do :** Maintenir la "One Voice Rule". La *Marine Académique* (#04142c) est le seul accent interactif en thème clair. Elle ne doit jamais servir de simple décoration.
* **Do :** Empiler les ombres en CSS pour appliquer la règle lithographique (ex: combiner une ombre courte et une ombre large pour un effet naturel).
* **Don't :** Laisser *Segoe UI* ou *Roboto* gérer des colonnes de chiffres financiers. Utiliser systématiquement la police *Mono* définie.
* **Don't :** Créer des tableaux de bord "SaaS" typiques avec des dégradés violet/crème et des titres en petites majuscules espacées. L'italique serif de *Libre Caslon* suffit pour l'élégance des libellés de groupes.