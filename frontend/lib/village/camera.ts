/**
 * La caméra — logique pure, sans React ni DOM.
 *
 * Un état du village ne décrit plus « quel écran afficher » mais « où regarder ».
 * `cameraFor` traduit l'état en un cadrage `{x, y, zoom}` ; c'est l'animation de
 * ce triplet, et rien d'autre, qui produit le vol continu. Aucune transition
 * n'est écrite nulle part : elles émergent de l'interpolation entre deux
 * cadrages.
 */

import { buildingRect, districtRect, type Rect } from "@/lib/village/layout";
import type { VillageState } from "@/lib/village/state";

export type Camera = {
  /** Point du plan à amener au centre du viewport. */
  x: number;
  y: number;
  zoom: number;
};

export type Viewport = { vw: number; vh: number };

/**
 * Facteur d'aération par niveau : combien de fois l'emprise cadrée doit tenir
 * dans le viewport. Au-dessus de 1 on voit le voisinage, en dessous on entre
 * dedans.
 *
 * Le niveau 1 est volontairement large (1,9) : en arrivant sur un bâtiment on
 * doit voir ses voisins, sinon on ne comprend pas qu'on peut défiler vers eux.
 * Les niveaux 2 et 3 passent sous 1 — la façade déborde alors du cadre, ce qui
 * se lit comme « on est entré ».
 */
const PADDING: Record<number, number> = {
  0: 1.55,
  1: 1.9,
  2: 1.05,
  3: 0.78,
};

/** Bornes de sécurité : un zoom nul ou infini casserait le compositeur. */
export const ZOOM_MIN = 0.2;
export const ZOOM_MAX = 40;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));

/**
 * Cadre `rect` dans le viewport avec un facteur d'aération.
 *
 * Le zoom se DÉDUIT du viewport ; il n'est jamais constant par niveau. Un
 * quartier de cinq bâtiments et un quartier de deux n'ont pas la même emprise,
 * et une fenêtre étroite n'est pas une fenêtre large : un zoom codé en dur
 * cadrerait juste dans un cas et de travers dans tous les autres.
 */
export function fitCamera(rect: Rect, { vw, vh }: Viewport, padding: number): Camera {
  const safeW = Math.max(1, rect.w * padding);
  const safeH = Math.max(1, rect.h * padding);
  const zoom = clamp(Math.min(vw / safeW, vh / safeH), ZOOM_MIN, ZOOM_MAX);
  return { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2, zoom };
}

/** Cadrage cible pour un état donné. */
export function cameraFor(state: VillageState, viewport: Viewport): Camera {
  const padding = PADDING[state.level] ?? PADDING[0];

  // Niveau 0 : le quartier entier. Au-delà, c'est toujours le bâtiment qu'on
  // cadre — de plus en plus près. Les salles ne déplacent PAS la caméra : elles
  // vivent dans la couche intérieure, qui coulisse pour son propre compte.
  const rect =
    state.level === 0
      ? districtRect(state.groupIndex)
      : buildingRect(state.groupIndex, state.moduleIndex);

  return fitCamera(rect, viewport, padding);
}

/**
 * Décalage de l'enfilade de salles, en unités d'espace intérieur.
 *
 * Positif vers la droite : la couche intérieure est translatée de l'opposé pour
 * amener la salle voulue au centre.
 */
export function roomOffset(roomIndex: number, roomWidthWithGap: number): number {
  return roomIndex * roomWidthWithGap;
}

/**
 * Traduit un cadrage en translation CSS, en pixels d'écran.
 *
 * L'ordre compte : le plan est d'abord mis à l'échelle, puis translaté. On pose
 * donc `transform: translate(tx, ty) scale(zoom)` avec `transform-origin: 0 0`,
 * et `tx`/`ty` déjà exprimés en pixels écran — c'est la seule combinaison qui
 * garde le point `(x, y)` du plan au centre du viewport à tout zoom.
 */
export function planeTransform(cam: Camera, { vw, vh }: Viewport) {
  return {
    x: vw / 2 - cam.x * cam.zoom,
    y: vh / 2 - cam.y * cam.zoom,
    scale: cam.zoom,
  };
}
