/**
 * La géographie du village — logique pure, sans React ni DOM.
 *
 * Tout vit sur UN SEUL plan de coordonnées fixes. C'est ce qui rend la caméra
 * possible : se déplacer d'un quartier à l'autre n'est plus un changement
 * d'écran mais un déplacement dans un espace continu, que le spectateur voit
 * traverser.
 *
 * Les dimensions ne sont pas arbitraires. Une unité de plan vaut un pixel à
 * zoom 1, et les visuels générés font 1200 px de large : un bâtiment large de
 * ~90 unités, vu à son zoom maximal (~13), occupe ~1170 px — soit sa
 * résolution native. Agrandir les emprises pixelliserait ; les réduire
 * gâcherait de la définition.
 */

import { MODULE_GROUPS } from "@/lib/modules";

export type Rect = { x: number; y: number; w: number; h: number };

/** Dimensions du plan. Ratio 3:2, celui des visuels. */
export const WORLD = { w: 1800, h: 1200 } as const;

export const DISTRICT_SIZE = { w: 380, h: 250 } as const;

/**
 * Les 7 quartiers : un au centre, six en couronne.
 *
 * Disposition volontairement irrégulière en apparence mais calculée sur une
 * ellipse — une grille régulière se lit comme un tableur vu de dessus, pas
 * comme un bourg. Le quartier « Exécution & Système » occupe le centre : c'est
 * la tour de contrôle, et le survol part naturellement de là.
 */
const RING_CENTER = { x: 900, y: 600 };
const RING_RADIUS = { x: 560, y: 380 };

/** Angles de la couronne, en degrés, dans l'ordre de `MODULE_GROUPS` moins le centre. */
const RING_ANGLES = [-30, 30, 90, 150, 210, 270];

/** Index du quartier placé au centre (le premier de `GROUP_ORDER`). */
const CENTER_INDEX = 0;

function centered(cx: number, cy: number): Rect {
  return {
    x: cx - DISTRICT_SIZE.w / 2,
    y: cy - DISTRICT_SIZE.h / 2,
    w: DISTRICT_SIZE.w,
    h: DISTRICT_SIZE.h,
  };
}

const DISTRICT_RECTS: Rect[] = MODULE_GROUPS.map((_, i) => {
  if (i === CENTER_INDEX) return centered(RING_CENTER.x, RING_CENTER.y);
  const angle = (RING_ANGLES[(i - 1) % RING_ANGLES.length] * Math.PI) / 180;
  return centered(
    RING_CENTER.x + RING_RADIUS.x * Math.cos(angle),
    RING_CENTER.y + RING_RADIUS.y * Math.sin(angle),
  );
});

/** Emprise d'un quartier sur le plan. Index hors bornes → le premier quartier. */
export function districtRect(districtIndex: number): Rect {
  return DISTRICT_RECTS[districtIndex] ?? DISTRICT_RECTS[0];
}

/** Marge intérieure d'un quartier : ses bâtiments ne touchent pas ses bords. */
const DISTRICT_PADDING = 40;
/** Au-delà, les bâtiments s'empilent sur une seconde rangée. */
const MAX_COLUMNS = 3;
/** Part de la cellule réellement occupée par la façade — le reste fait la rue. */
const BUILDING_FILL = 0.78;

/** Nombre de bâtiments d'un quartier. */
export function buildingCount(districtIndex: number): number {
  return MODULE_GROUPS[districtIndex]?.items.length ?? 0;
}

/**
 * Emprise d'un bâtiment DANS son quartier.
 *
 * Les façades gardent le ratio 3:2 des visuels : une cellule plus large que
 * haute laisse la marge sur les côtés, jamais l'inverse — sinon les images
 * seraient rognées ou déformées.
 */
export function buildingRect(districtIndex: number, buildingIndex: number): Rect {
  const district = districtRect(districtIndex);
  const n = Math.max(1, buildingCount(districtIndex));
  const cols = Math.min(MAX_COLUMNS, n);
  const rows = Math.ceil(n / cols);

  const inner = {
    x: district.x + DISTRICT_PADDING,
    y: district.y + DISTRICT_PADDING,
    w: district.w - DISTRICT_PADDING * 2,
    h: district.h - DISTRICT_PADDING * 2,
  };

  const cell = { w: inner.w / cols, h: inner.h / rows };

  // La façade tient dans la cellule en conservant 3:2.
  const w = Math.min(cell.w * BUILDING_FILL, cell.h * BUILDING_FILL * 1.5);
  const h = w / 1.5;

  const i = Math.max(0, Math.min(buildingIndex, n - 1));
  const col = i % cols;
  const row = Math.floor(i / cols);

  // La dernière rangée est recentrée si elle est incomplète — une rangée
  // orpheline collée à gauche trahit la grille sous-jacente.
  const inRow = row === rows - 1 ? n - row * cols : cols;
  const rowWidth = inRow * cell.w;
  const rowOffset = (inner.w - rowWidth) / 2;

  return {
    x: inner.x + rowOffset + col * cell.w + (cell.w - w) / 2,
    y: inner.y + row * cell.h + (cell.h - h) / 2,
    w,
    h,
  };
}

/**
 * Les salles vivent dans leur PROPRE espace, pas sur le plan du village.
 *
 * Une enfilade posée sur le plan déborderait sur les bâtiments voisins dès
 * qu'un module a six onglets. L'intérieur est donc une couche à part, ancrée
 * sur le bâtiment et rendue par-dessus lui : le monde continue d'exister
 * derrière, flouté, et la continuité visuelle est préservée sans que la
 * géographie ait à mentir.
 */
export const ROOM = { w: 100, h: 66, gap: 22 } as const;

/** Emprise d'une salle dans l'espace intérieur, la salle 0 centrée sur l'origine. */
export function roomRect(roomIndex: number): Rect {
  return {
    x: roomIndex * (ROOM.w + ROOM.gap) - ROOM.w / 2,
    y: -ROOM.h / 2,
    w: ROOM.w,
    h: ROOM.h,
  };
}

/** Largeur totale d'une enfilade de `count` salles. */
export function roomsWidth(count: number): number {
  return count <= 0 ? 0 : count * ROOM.w + (count - 1) * ROOM.gap;
}
