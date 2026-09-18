/**
 * Palette DESIGN.md pour les CHARTS (recharts/SVG exigent des couleurs
 * concrètes). Pour le texte et les surfaces UI : tokens CSS uniquement
 * (ces hex ne suivent pas le thème sombre).
 */
export const INK = {
  navy: "#04142c",
  brass: "#C5A059",
  green: "#536252",
  oxblood: "#501312",
  slate: "#384762",
  ochre: "#8a6d1f",
  vermilion: "#ba1a1a",
} as const;

/** Série catégorielle (ordre = contraste maximal entre voisins). */
export const CHART_SERIES: string[] = [
  INK.navy, INK.brass, INK.green, INK.oxblood, INK.slate, INK.ochre, INK.vermilion,
];

export const SPATIAL_ACCENTS = {
  finance: "#72c7e7",
  projets: "#e8bd6e",
  sante: "#70d4a0",
  vie: "#bd9cf4",
} as const;

/**
 * Sentinelle "Sans catégorie" envoyée telle quelle par le backend
 * (backend/app/services/budget/analytics.py: UNCATEGORISED_COLOR) et comparée
 * par égalité aux couleurs de catégorie — pas un token thème, mais centralisée
 * ici plutôt qu'en dur dans le composant.
 */
export const UNCATEGORISED_COLOR = "#9aa3b0";

/**
 * Valeur initiale du sélecteur `<input type="color">` (habitudes/GestionTab.tsx) :
 * l'élément natif exige un littéral hex, pas un token CSS — centralisé ici
 * plutôt qu'en dur dans le composant.
 */
export const HABIT_COLOR_DEFAULT = "#6366f1";

/**
 * Fond sombre « midnight marine » du design system, utilisé comme
 * `viewport.themeColor` (src/app/layout.tsx) : la metadata Next.js exige un
 * littéral hex statique (pas de token CSS résolu à l'exécution) — centralisé
 * ici plutôt qu'en dur dans le composant.
 */
export const MIDNIGHT = "#0B121E";
