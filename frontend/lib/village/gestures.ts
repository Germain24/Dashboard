/**
 * Reconnaissance de gestes du village — logique pure, sans DOM.
 *
 * Le problème : un trackpad n'envoie pas « un geste », il envoie une rafale de
 * dizaines d'événements `wheel` suivie d'une traîne inertielle qui décroît
 * lentement. Sans filtrage, un seul coup de doigt traverse quatre quartiers.
 *
 * Trois mécanismes, dans cet ordre :
 *   1. un accumulateur remis à zéro après un temps mort (une rafale = un geste) ;
 *   2. un verrou d'axe posé au premier delta franc (un geste est vertical OU
 *      horizontal, jamais les deux — les trackpads produisent du deltaX
 *      parasite pendant un scroll vertical, d'où le biais vers le vertical) ;
 *   3. un verrou temporel après déclenchement, levé plus tôt si l'inertie est
 *      retombée, pour qu'un seul lancer ne produise qu'une seule transition.
 */

import type { VillageAction } from "@/lib/village/state";

/** Temps mort au-delà duquel une nouvelle rafale commence. */
export const IDLE_RESET_MS = 180;
/** Delta minimal avant de décider de l'axe. */
export const AXIS_MIN_PX = 8;
/** Biais vers le vertical : l'horizontal doit être franchement dominant. */
export const AXIS_BIAS = 1.4;
/** Distance cumulée qui déclenche une transition. */
export const TRIGGER_PX = 60;
/** Durée du verrou après déclenchement (≈ durée du ressort d'animation). */
export const LOCK_MS = 550;
/** En dessous, l'inertie est considérée retombée : le verrou peut sauter. */
export const SETTLED_PX = 4;

export type GestureAxis = "x" | "y" | null;

export type GestureAccumulator = {
  ax: number;
  ay: number;
  axis: GestureAxis;
  /** Horodatage du dernier delta vu. */
  lastAt: number;
  /** Aucun déclenchement avant cette date. */
  lockedUntil: number;
};

export const initialAccumulator: GestureAccumulator = {
  ax: 0,
  ay: 0,
  axis: null,
  lastAt: 0,
  lockedUntil: 0,
};

export type GestureInput = {
  dx: number;
  dy: number;
  at: number;
  /** Le niveau courant capte-t-il l'axe vertical ? Faux au niveau 2. */
  allowVertical: boolean;
  /** Le niveau courant capte-t-il l'axe horizontal ? */
  allowHorizontal: boolean;
};

export type GestureResult = {
  acc: GestureAccumulator;
  /** Le geste à jouer, ou `null` si le seuil n'est pas atteint. */
  action: VillageAction | null;
  /**
   * Le village s'approprie-t-il cet axe ? Détermine le `preventDefault` :
   * quand c'est faux, l'événement doit continuer vers le navigateur pour que
   * le contenu de la page scrolle normalement.
   */
  consumed: boolean;
};

const rest = (acc: GestureAccumulator, at: number): GestureAccumulator => ({
  ...acc,
  ax: 0,
  ay: 0,
  axis: null,
  lastAt: at,
});

/**
 * Fait avancer l'accumulateur d'un delta et dit s'il en sort un geste.
 *
 * Pure et totale : mêmes entrées, même sortie ; aucun état caché.
 */
export function resolveGesture(
  acc: GestureAccumulator,
  { dx, dy, at, allowVertical, allowHorizontal }: GestureInput,
): GestureResult {
  // Nouvelle rafale après un temps mort.
  let next = at - acc.lastAt > IDLE_RESET_MS ? rest(acc, at) : { ...acc, lastAt: at };

  // Sous verrou : on absorbe la traîne inertielle. Un delta redevenu minuscule
  // signe la fin du lancer et lève le verrou par anticipation.
  if (at < next.lockedUntil) {
    const settled = Math.abs(dx) < SETTLED_PX && Math.abs(dy) < SETTLED_PX;
    next = rest(next, at);
    if (settled) next.lockedUntil = 0;
    return { acc: next, action: null, consumed: true };
  }

  next.ax += dx;
  next.ay += dy;

  // Verrou d'axe, posé une seule fois par rafale.
  if (next.axis === null) {
    const { ax, ay } = next;
    if (Math.max(Math.abs(ax), Math.abs(ay)) >= AXIS_MIN_PX) {
      next.axis = Math.abs(ax) > Math.abs(ay) * AXIS_BIAS ? "x" : "y";
    } else {
      return { acc: next, action: null, consumed: false };
    }
  }

  const consumed = next.axis === "y" ? allowVertical : allowHorizontal;

  // Axe non capté à ce niveau : on laisse la main au navigateur, mais l'axe
  // reste verrouillé pour que le bruit de l'autre axe ne déclenche rien.
  if (!consumed) return { acc: next, action: null, consumed: false };

  if (next.axis === "y" && Math.abs(next.ay) >= TRIGGER_PX) {
    const action: VillageAction = next.ay > 0 ? "down" : "up";
    next = rest(next, at);
    next.lockedUntil = at + LOCK_MS;
    return { acc: next, action, consumed: true };
  }

  if (next.axis === "x" && Math.abs(next.ax) >= TRIGGER_PX) {
    // Vers la droite = entrer ; vers la gauche = ressortir.
    const action: VillageAction = next.ax > 0 ? "enter" : "back";
    next = rest(next, at);
    next.lockedUntil = at + LOCK_MS;
    return { acc: next, action, consumed: true };
  }

  return { acc: next, action: null, consumed: true };
}

/** Traduit une touche en geste. `null` si la touche n'appartient pas au village. */
export function actionForKey(key: string): VillageAction | null {
  switch (key) {
    case "ArrowUp":
    case "PageUp":
      return "up";
    case "ArrowDown":
    case "PageDown":
      return "down";
    case "ArrowRight":
    case "Enter":
      return "enter";
    case "ArrowLeft":
    case "Escape":
    case "Backspace":
      return "back";
    default:
      return null;
  }
}

/** Direction dominante d'un swipe tactile, au-delà d'un seuil de 50 px. */
export const SWIPE_PX = 50;

export function actionForSwipe(dx: number, dy: number): VillageAction | null {
  if (Math.abs(dx) < SWIPE_PX && Math.abs(dy) < SWIPE_PX) return null;
  if (Math.abs(dx) > Math.abs(dy)) return dx < 0 ? "enter" : "back";
  return dy < 0 ? "down" : "up";
}
