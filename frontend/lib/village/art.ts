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
import { BUILDING_ART, DISTRICT_ART } from "@/lib/village/art.generated";

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
 * Visuels réellement présents dans `public/village/`, inventoriés à la
 * génération (`node scripts/village-art-manifest.mjs`). Tout ce qui n'y figure
 * pas rend la façade procédurale — un module ajouté demain s'affiche donc
 * correctement sans qu'on ait à penser à son image.
 */
const districts = new Set(DISTRICT_ART);
const buildings = new Set(BUILDING_ART);

export function districtArt(group: ModuleGroup): string | null {
  const slug = GROUP_SLUGS[group];
  return districts.has(slug) ? `/village/districts/${slug}.webp` : null;
}

export function buildingArt(moduleSlug: string): string | null {
  return buildings.has(moduleSlug) ? `/village/buildings/${moduleSlug}.webp` : null;
}
