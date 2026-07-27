/**
 * Décor du village : couleurs par quartier et résolution des visuels.
 *
 * Les images isométriques arrivent après la navigation (elles se génèrent une
 * par une). Tout ici doit donc dégrader proprement : sans fichier, `VillageArt`
 * rend une façade procédurale bâtie sur l'accent du quartier et l'icône du
 * module. Le manifeste `AVAILABLE_ART` est explicite — `onError` ne fonctionne
 * pas au rendu serveur, et une image 404 laisserait un trou noir à l'écran.
 */

import { INK } from "@/lib/design/colors";
import { GROUP_SLUGS, type ModuleGroup } from "@/lib/modules";

/** Un accent par quartier, pris dans la palette d'encres du design system. */
export const DISTRICT_ACCENT: Record<ModuleGroup, string> = {
  "Exécution & Système": INK.navy,
  "Finances & Ingénierie": INK.slate,
  "Santé & Performance": INK.green,
  "Carrière & Études": INK.oxblood,
  "Culture & Loisirs": INK.ochre,
  "Style & Horizons": INK.brass,
  Configuration: INK.vermilion,
};

/**
 * Visuels déjà présents dans `public/village/`. À compléter au fur et à mesure
 * de la génération ; tout ce qui n'y figure pas rend la façade procédurale.
 */
export const AVAILABLE_ART = {
  districts: new Set<string>(),
  buildings: new Set<string>(),
};

export function districtArt(group: ModuleGroup): string | null {
  const slug = GROUP_SLUGS[group];
  return AVAILABLE_ART.districts.has(slug) ? `/village/districts/${slug}.webp` : null;
}

export function buildingArt(moduleSlug: string): string | null {
  return AVAILABLE_ART.buildings.has(moduleSlug)
    ? `/village/buildings/${moduleSlug}.webp`
    : null;
}
