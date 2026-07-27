import { describe, expect, it } from "vitest";
import {
  AXIS_MIN_PX,
  IDLE_RESET_MS,
  LOCK_MS,
  SETTLED_PX,
  TRIGGER_PX,
  actionForKey,
  actionForSwipe,
  initialAccumulator,
  resolveGesture,
  type GestureAccumulator,
} from "@/lib/village/gestures";

const BOTH = { allowVertical: true, allowHorizontal: true };

/** Rejoue une rafale de deltas et renvoie l'accumulateur + les gestes produits. */
function burst(
  deltas: { dx: number; dy: number; at: number }[],
  opts = BOTH,
  from: GestureAccumulator = initialAccumulator,
) {
  let acc = from;
  const actions: (string | null)[] = [];
  for (const d of deltas) {
    const r = resolveGesture(acc, { ...d, ...opts });
    acc = r.acc;
    if (r.action) actions.push(r.action);
  }
  return { acc, actions };
}

describe("resolveGesture — seuil de déclenchement", () => {
  it("ne déclenche rien sous le seuil", () => {
    const { actions } = burst([{ dx: 0, dy: 20, at: 100 }]);
    expect(actions).toEqual([]);
  });

  it("déclenche `down` une fois le cumul atteint", () => {
    const { actions } = burst([
      { dx: 0, dy: 25, at: 100 },
      { dx: 0, dy: 25, at: 120 },
      { dx: 0, dy: 25, at: 140 },
    ]);
    expect(actions).toEqual(["down"]);
  });

  it("un cumul négatif donne `up`", () => {
    const { actions } = burst([{ dx: 0, dy: -TRIGGER_PX, at: 100 }]);
    expect(actions).toEqual(["up"]);
  });

  it("droite = `enter`, gauche = `back`", () => {
    expect(burst([{ dx: TRIGGER_PX, dy: 0, at: 100 }]).actions).toEqual(["enter"]);
    expect(burst([{ dx: -TRIGGER_PX, dy: 0, at: 100 }]).actions).toEqual(["back"]);
  });
});

describe("resolveGesture — verrou d'axe", () => {
  it("un scroll vertical bruité ne déclenche jamais l'horizontal", () => {
    // deltaX parasite constant, typique d'un trackpad.
    const { actions } = burst(
      Array.from({ length: 12 }, (_, i) => ({ dx: 9, dy: 20, at: 100 + i * 20 })),
    );
    expect(actions.every((a) => a === "down" || a === "up")).toBe(true);
    expect(actions).toContain("down");
  });

  it("l'horizontal doit être franchement dominant pour l'emporter", () => {
    // |dx| > |dy| mais pas au-delà du biais de 1.4 → reste vertical.
    const { acc } = burst([{ dx: 12, dy: 10, at: 100 }]);
    expect(acc.axis).toBe("y");
  });

  it("un horizontal net verrouille bien l'axe x", () => {
    const { acc } = burst([{ dx: 20, dy: 2, at: 100 }]);
    expect(acc.axis).toBe("x");
  });

  it("aucun axe n'est choisi tant que le mouvement est infime", () => {
    const { acc } = burst([{ dx: AXIS_MIN_PX - 6, dy: 1, at: 100 }]);
    expect(acc.axis).toBeNull();
  });
});

describe("resolveGesture — verrou temporel", () => {
  it("un seul lancer inertiel ne produit qu'une transition", () => {
    // 30 événements décroissants, comme une inertie macOS.
    const deltas = Array.from({ length: 30 }, (_, i) => ({
      dx: 0,
      dy: Math.max(6, 40 - i),
      at: 100 + i * 16,
    }));
    expect(burst(deltas).actions).toEqual(["down"]);
  });

  it("le verrou se lève une fois l'inertie retombée", () => {
    const first = burst([{ dx: 0, dy: TRIGGER_PX, at: 100 }]);
    expect(first.acc.lockedUntil).toBe(100 + LOCK_MS);

    // Traîne devenue négligeable → verrou levé par anticipation.
    const settled = resolveGesture(first.acc, {
      dx: 0,
      dy: SETTLED_PX - 1,
      at: 200,
      ...BOTH,
    });
    expect(settled.acc.lockedUntil).toBe(0);

    // Un nouveau geste franc passe immédiatement.
    const second = resolveGesture(settled.acc, { dx: 0, dy: TRIGGER_PX, at: 220, ...BOTH });
    expect(second.action).toBe("down");
  });

  it("un second geste franc passe après expiration du verrou", () => {
    const first = burst([{ dx: 0, dy: TRIGGER_PX, at: 100 }]);
    const second = resolveGesture(first.acc, {
      dx: 0,
      dy: TRIGGER_PX,
      at: 100 + LOCK_MS + 1,
      ...BOTH,
    });
    expect(second.action).toBe("down");
  });
});

describe("resolveGesture — rafales successives", () => {
  it("le temps mort repart d'un accumulateur vierge", () => {
    const { acc } = burst([{ dx: 0, dy: 30, at: 100 }]);
    const next = resolveGesture(acc, {
      dx: 0,
      dy: 30,
      at: 100 + IDLE_RESET_MS + 1,
      ...BOTH,
    });
    // Les 30 px de la rafale précédente ne comptent plus : pas de déclenchement.
    expect(next.action).toBeNull();
    expect(next.acc.ay).toBe(30);
  });
});

describe("resolveGesture — axes non captés (niveau 2)", () => {
  const level2 = { allowVertical: false, allowHorizontal: true };

  it("le vertical n'est pas capté : le contenu de la page scrolle", () => {
    const r = resolveGesture(initialAccumulator, { dx: 0, dy: 200, at: 100, ...level2 });
    expect(r.action).toBeNull();
    expect(r.consumed).toBe(false);
  });

  it("l'horizontal reste capté", () => {
    const r = resolveGesture(initialAccumulator, {
      dx: TRIGGER_PX,
      dy: 0,
      at: 100,
      ...level2,
    });
    expect(r.action).toBe("enter");
    expect(r.consumed).toBe(true);
  });

  it("un long scroll vertical ne bascule jamais en horizontal par dérive", () => {
    const { actions } = burst(
      Array.from({ length: 20 }, (_, i) => ({ dx: 5, dy: 40, at: 100 + i * 16 })),
      level2,
    );
    expect(actions).toEqual([]);
  });
});

describe("actionForKey", () => {
  it("mappe les touches de navigation", () => {
    expect(actionForKey("ArrowDown")).toBe("down");
    expect(actionForKey("PageUp")).toBe("up");
    expect(actionForKey("ArrowRight")).toBe("enter");
    expect(actionForKey("Escape")).toBe("back");
    expect(actionForKey("a")).toBeNull();
  });
});

describe("actionForSwipe", () => {
  it("ignore les micro-mouvements", () => {
    expect(actionForSwipe(10, 10)).toBeNull();
  });

  it("balayer vers la gauche fait entrer, vers la droite fait sortir", () => {
    expect(actionForSwipe(-120, 5)).toBe("enter");
    expect(actionForSwipe(120, 5)).toBe("back");
  });

  it("balayer vers le haut avance dans la liste", () => {
    expect(actionForSwipe(5, -120)).toBe("down");
    expect(actionForSwipe(5, 120)).toBe("up");
  });
});
