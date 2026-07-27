/**
 * Détourage du fond + encodage WebP pour les visuels du village.
 *
 * Le fond blanc est retiré par remplissage par diffusion DEPUIS LES BORDS, et
 * non par seuil global : la surface des îlots est en crème #faf9f5, à trois
 * points du blanc pur. Un seuil global la mangerait ; un remplissage
 * connecté aux bords ne touche que ce qui communique avec l'extérieur.
 *
 * Le masque d'alpha est ensuite légèrement flouté, sinon la découpe est
 * crénelée sur les diagonales — et un diorama isométrique n'a que des
 * diagonales.
 *
 * Usage : node scripts/village-art.mjs <entree.png> <sortie.webp> [largeur]
 */

import sharp from "sharp";

const [, , input, output, widthArg] = process.argv;
const TARGET_WIDTH = Number(widthArg) || 1200;

/**
 * Seuil du remplissage depuis les bords. Le réglage est plus délicat qu'il
 * n'y paraît : trop haut, il reste un large croissant d'ombre qui flotte dans
 * le vide sur thème sombre ; trop bas (essayé à 215), la diffusion FRANCHIT le
 * rebord de l'îlot là où le crème en pleine lumière touche la silhouette, et
 * elle creuse de grands trous en plein décor. 238 laisse juste une frange de
 * contact, qui se lit comme une ombre portée.
 */
const FILL_LUMA = 238;

/**
 * Le fond enclavé — celui qu'on voit à travers un auvent ou une arcade — n'est
 * relié à aucun bord, le remplissage ne l'atteint jamais. On l'attrape sur sa
 * signature propre : blanc pur ET sans couleur. Le crème #faf9f5 de l'argile
 * a beau être clair (luma ~249), il tire sur le jaune (écart de 5 entre ses
 * canaux) et passe donc à travers ce filtre.
 */
const WHITE_LUMA = 250;
const WHITE_CHROMA = 3;

/** Adoucit la découpe (en pixels) : un diorama isométrique n'a que des diagonales. */
const EDGE_BLUR = 0.8;

// Les dimensions viennent du buffer lui-même, jamais de `metadata()` : celui-ci
// décrit le fichier d'origine, alors que `raw()` a pu le réorienter.
const { data: raw, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });
const { width, height, channels } = info;
if (channels !== 4) {
  console.error(`ECHEC ${input} : ${channels} canaux au lieu de 4`);
  process.exit(2);
}

const luma = new Uint8Array(width * height);
const isWhite = new Uint8Array(width * height);
for (let i = 0, p = 0; i < luma.length; i++, p += 4) {
  const r = raw[p];
  const g = raw[p + 1];
  const b = raw[p + 2];
  luma[i] = (r * 299 + g * 587 + b * 114) / 1000;
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  if (luma[i] >= WHITE_LUMA && chroma <= WHITE_CHROMA) isWhite[i] = 1;
}

const isBackground = new Uint8Array(width * height);

/**
 * Diffusion depuis une liste de graines. Pile explicite : une récursion
 * déborderait sur 1,5 million de pixels.
 */
function flood(seeds) {
  const stack = [];
  const claimed = [];
  const push = (i) => {
    if (!isBackground[i] && luma[i] >= FILL_LUMA) {
      isBackground[i] = 1;
      stack.push(i);
      claimed.push(i);
    }
  };
  seeds.forEach(push);
  while (stack.length) {
    const i = stack.pop();
    const x = i % width;
    const y = (i / width) | 0;
    if (x > 0) push(i - 1);
    if (x < width - 1) push(i + 1);
    if (y > 0) push(i - width);
    if (y < height - 1) push(i + width);
  }
  return claimed;
}

// 1. Le fond principal : tout ce qui communique avec les bords du cadre.
const border = [];
for (let x = 0; x < width; x++) border.push(x, (height - 1) * width + x);
for (let y = 0; y < height; y++) border.push(y * width, y * width + width - 1);
flood(border);

/**
 * On s'arrête là, délibérément. Le fond ENCLAVÉ — celui qu'on apercevrait à
 * travers un auvent — n'est atteint par aucune diffusion depuis les bords, et
 * il est TENTANT de rattraper le coup en marquant tout blanc pur et neutre.
 * Ça ne marche pas : l'argile crème surexposée est elle aussi blanche et
 * neutre, et la règle perce de larges trous en plein îlot (essayé, constaté —
 * filtrer par taille ne sépare pas les deux, ces aplats sont vastes).
 *
 * Le problème se traite donc à la source : les prompts demandent des volumes
 * fermés, sans ouverture traversante. Ce qui passe malgré tout reste une
 * petite zone claire à l'intérieur du modèle, pas un défaut de découpe.
 */
const enclosedWhite = isWhite.reduce(
  (n, w, i) => n + (w && !isBackground[i] ? 1 : 0),
  0,
);
if (enclosedWhite > width * height * 0.01) {
  console.warn(
    `  attention ${input} : ${((enclosedWhite / (width * height)) * 100).toFixed(1)} % de blanc enclavé (ouverture traversante ?)`,
  );
}

const removed = isBackground.reduce((a, b) => a + b, 0);
const ratio = removed / (width * height);
// Garde-fou : un remplissage qui fuit à travers l'îlot mangerait presque tout ;
// un fond non détecté n'enlèverait presque rien. Les deux doivent hurler.
if (ratio < 0.15 || ratio > 0.92) {
  console.error(`ECHEC ${input} : ${(ratio * 100).toFixed(1)} % du cadre retiré — fuite ou fond non détecté`);
  process.exit(2);
}

const mask = Buffer.alloc(width * height);
for (let i = 0; i < mask.length; i++) mask[i] = isBackground[i] ? 0 : 255;

// `toColourspace('b-w')` n'est pas cosmétique : sans lui sharp rend le masque
// flouté en 3 canaux (conversion sRGB), le buffer fait trois fois la taille
// attendue, et la réinjection décale l'alpha d'un tiers de ligne à chaque
// ligne — l'image sort déchirée en bandes horizontales.
const { data: alpha, info: alphaInfo } = await sharp(mask, {
  raw: { width, height, channels: 1 },
})
  .blur(EDGE_BLUR)
  .toColourspace("b-w")
  .raw()
  .toBuffer({ resolveWithObject: true });

if (
  alphaInfo.channels !== 1 ||
  alphaInfo.width !== width ||
  alphaInfo.height !== height
) {
  console.error(
    `ECHEC ${input} : masque ${alphaInfo.width}x${alphaInfo.height}x${alphaInfo.channels}, attendu ${width}x${height}x1`,
  );
  process.exit(2);
}

for (let i = 0, p = 3; i < alpha.length; i++, p += 4) raw[p] = alpha[i];

await sharp(raw, { raw: { width, height, channels: 4 } })
  .resize({ width: TARGET_WIDTH, withoutEnlargement: true })
  .webp({ quality: 82, effort: 6 })
  .toFile(output);

console.log(`OK ${output} — ${(ratio * 100).toFixed(1)} % de fond retiré`);
