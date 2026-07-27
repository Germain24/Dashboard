/**
 * Régénère `lib/village/art.generated.ts` à partir de ce qui est réellement
 * dans `public/village/`.
 *
 * Pourquoi un manifeste plutôt qu'un `onError` sur l'image : `onError` ne se
 * déclenche pas au rendu serveur, si bien qu'un visuel manquant laisserait un
 * trou noir avant l'hydratation. Le composant doit savoir AVANT de rendre s'il
 * dispose d'une image ou s'il doit dessiner la façade procédurale.
 *
 * Usage : node scripts/village-art-manifest.mjs
 */

import { readdirSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = join(root, "public", "village");

const list = (kind) => {
  const dir = join(publicDir, kind);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".webp"))
    .map((f) => f.replace(/\.webp$/, ""))
    .sort();
};

const districts = list("districts");
const buildings = list("buildings");

const body = `/**
 * FICHIER GÉNÉRÉ — ne pas modifier à la main.
 * Régénérer avec : node scripts/village-art-manifest.mjs
 *
 * Inventaire des visuels présents dans public/village/. Tout ce qui n'y figure
 * pas rend la façade procédurale (cf. components/village/VillageArt.tsx).
 */

export const DISTRICT_ART: readonly string[] = [
${districts.map((s) => `  "${s}",`).join("\n")}
];

export const BUILDING_ART: readonly string[] = [
${buildings.map((s) => `  "${s}",`).join("\n")}
];
`;

writeFileSync(join(root, "lib", "village", "art.generated.ts"), body, "utf8");
console.log(
  `art.generated.ts : ${districts.length} quartiers, ${buildings.length} bâtiments`,
);
