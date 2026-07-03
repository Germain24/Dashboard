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
