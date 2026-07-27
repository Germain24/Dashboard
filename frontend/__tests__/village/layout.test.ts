import { describe, expect, it } from "vitest";
import { MODULE_GROUPS } from "@/lib/modules";
import {
  DISTRICT_SIZE,
  ROOM,
  WORLD,
  buildingCount,
  buildingRect,
  districtRect,
  roomRect,
  roomsWidth,
  type Rect,
} from "@/lib/village/layout";
import {
  ZOOM_MAX,
  ZOOM_MIN,
  cameraFor,
  fitCamera,
  planeTransform,
} from "@/lib/village/camera";
import type { VillageState } from "@/lib/village/state";

const VIEWPORT = { vw: 1466, vh: 760 };
const at = (over: Partial<VillageState> = {}): VillageState => ({
  level: 0,
  groupIndex: 0,
  moduleIndex: 0,
  tabIndex: 0,
  ...over,
});

const overlaps = (a: Rect, b: Rect) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

const contains = (outer: Rect, inner: Rect) =>
  inner.x >= outer.x - 0.001 &&
  inner.y >= outer.y - 0.001 &&
  inner.x + inner.w <= outer.x + outer.w + 0.001 &&
  inner.y + inner.h <= outer.y + outer.h + 0.001;

describe("districtRect", () => {
  it("place un quartier par groupe", () => {
    for (let i = 0; i < MODULE_GROUPS.length; i++) {
      const r = districtRect(i);
      expect(r.w).toBe(DISTRICT_SIZE.w);
      expect(r.h).toBe(DISTRICT_SIZE.h);
    }
  });

  it("garde tous les quartiers dans les limites du plan", () => {
    for (let i = 0; i < MODULE_GROUPS.length; i++) {
      const r = districtRect(i);
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.y).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(WORLD.w);
      expect(r.y + r.h).toBeLessThanOrEqual(WORLD.h);
    }
  });

  it("ne fait se chevaucher aucun quartier", () => {
    for (let i = 0; i < MODULE_GROUPS.length; i++) {
      for (let j = i + 1; j < MODULE_GROUPS.length; j++) {
        expect(overlaps(districtRect(i), districtRect(j))).toBe(false);
      }
    }
  });

  it("dégrade proprement hors bornes", () => {
    expect(districtRect(99)).toEqual(districtRect(0));
    expect(districtRect(-1)).toEqual(districtRect(0));
  });
});

describe("buildingRect", () => {
  it("garde chaque bâtiment dans son quartier", () => {
    for (let d = 0; d < MODULE_GROUPS.length; d++) {
      const district = districtRect(d);
      for (let b = 0; b < buildingCount(d); b++) {
        expect(contains(district, buildingRect(d, b))).toBe(true);
      }
    }
  });

  it("ne fait se chevaucher aucun bâtiment d'un même quartier", () => {
    for (let d = 0; d < MODULE_GROUPS.length; d++) {
      const n = buildingCount(d);
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          expect(overlaps(buildingRect(d, i), buildingRect(d, j))).toBe(false);
        }
      }
    }
  });

  it("conserve le ratio 3:2 des visuels", () => {
    for (let d = 0; d < MODULE_GROUPS.length; d++) {
      for (let b = 0; b < buildingCount(d); b++) {
        const r = buildingRect(d, b);
        expect(r.w / r.h).toBeCloseTo(1.5, 5);
      }
    }
  });

  // Une façade est un WebP de 1200 px de large. C'est au niveau 2 — le hall,
  // où elle est nette et occupe l'écran — qu'elle ne doit pas être agrandie
  // au-delà de sa résolution native. Au niveau 3 elle passe derrière le
  // contenu, floutée : une légère sur-échelle y est sans conséquence, et
  // l'interdire forcerait à rapetisser les emprises, donc à gâcher de la
  // définition partout ailleurs.
  const NATIVE_PX = 1200;

  it("reste net dans le hall, là où la façade se voit vraiment", () => {
    for (let d = 0; d < MODULE_GROUPS.length; d++) {
      for (let b = 0; b < buildingCount(d); b++) {
        const cam = cameraFor(at({ level: 2, groupIndex: d, moduleIndex: b }), VIEWPORT);
        expect(buildingRect(d, b).w * cam.zoom).toBeLessThanOrEqual(NATIVE_PX * 1.05);
      }
    }
  });

  it("ne dérape pas non plus au niveau 3, où la façade est floutée", () => {
    for (let d = 0; d < MODULE_GROUPS.length; d++) {
      for (let b = 0; b < buildingCount(d); b++) {
        const cam = cameraFor(at({ level: 3, groupIndex: d, moduleIndex: b }), VIEWPORT);
        expect(buildingRect(d, b).w * cam.zoom).toBeLessThanOrEqual(NATIVE_PX * 1.35);
      }
    }
  });

  it("clampe un index de bâtiment hors bornes", () => {
    expect(buildingRect(0, 99)).toEqual(buildingRect(0, buildingCount(0) - 1));
  });
});

describe("fitCamera", () => {
  const rect: Rect = { x: 100, y: 200, w: 400, h: 200 };

  it("centre la caméra sur l'emprise", () => {
    const cam = fitCamera(rect, VIEWPORT, 1);
    expect(cam.x).toBe(300);
    expect(cam.y).toBe(300);
  });

  it("déduit le zoom du viewport, pas d'une constante", () => {
    const large = fitCamera(rect, { vw: 2000, vh: 1200 }, 1);
    const petit = fitCamera(rect, { vw: 800, vh: 600 }, 1);
    expect(large.zoom).toBeGreaterThan(petit.zoom);
  });

  it("cadre selon l'axe le plus contraint", () => {
    // 760/200 = 3.8 est plus petit que 1466/400 = 3.66... donc c'est la largeur
    // qui contraint ici.
    const cam = fitCamera(rect, VIEWPORT, 1);
    expect(cam.zoom).toBeCloseTo(Math.min(1466 / 400, 760 / 200), 5);
  });

  it("une aération plus grande éloigne la caméra", () => {
    expect(fitCamera(rect, VIEWPORT, 2).zoom).toBeLessThan(
      fitCamera(rect, VIEWPORT, 1).zoom,
    );
  });

  it("borne le zoom", () => {
    expect(fitCamera({ x: 0, y: 0, w: 1e9, h: 1e9 }, VIEWPORT, 1).zoom).toBe(ZOOM_MIN);
    expect(fitCamera({ x: 0, y: 0, w: 0, h: 0 }, VIEWPORT, 1).zoom).toBe(ZOOM_MAX);
  });
});

describe("cameraFor", () => {
  it("zoome de plus en plus fort à mesure qu'on entre", () => {
    const zooms = [0, 1, 2, 3].map(
      (level) => cameraFor(at({ level: level as 0 | 1 | 2 | 3 }), VIEWPORT).zoom,
    );
    for (let i = 1; i < zooms.length; i++) {
      expect(zooms[i]).toBeGreaterThan(zooms[i - 1]);
    }
  });

  it("cadre le quartier au niveau 0 et le bâtiment ensuite", () => {
    const district = districtRect(2);
    const cam0 = cameraFor(at({ level: 0, groupIndex: 2 }), VIEWPORT);
    expect(cam0.x).toBeCloseTo(district.x + district.w / 2, 5);

    const building = buildingRect(2, 1);
    const cam1 = cameraFor(at({ level: 1, groupIndex: 2, moduleIndex: 1 }), VIEWPORT);
    expect(cam1.x).toBeCloseTo(building.x + building.w / 2, 5);
  });

  it("les salles ne déplacent pas la caméra", () => {
    const a = cameraFor(at({ level: 3, groupIndex: 1, moduleIndex: 1, tabIndex: 0 }), VIEWPORT);
    const b = cameraFor(at({ level: 3, groupIndex: 1, moduleIndex: 1, tabIndex: 4 }), VIEWPORT);
    expect(a).toEqual(b);
  });

  it("change de cadrage quand on change de quartier", () => {
    const a = cameraFor(at({ groupIndex: 0 }), VIEWPORT);
    const b = cameraFor(at({ groupIndex: 3 }), VIEWPORT);
    expect(a.x === b.x && a.y === b.y).toBe(false);
  });
});

describe("planeTransform", () => {
  it("amène le point visé au centre du viewport", () => {
    const cam = { x: 500, y: 400, zoom: 2 };
    const t = planeTransform(cam, VIEWPORT);
    // Le point (500,400) du plan, une fois mis a l'echelle puis translate,
    // doit tomber au centre de l'ecran.
    expect(t.x + cam.x * t.scale).toBeCloseTo(VIEWPORT.vw / 2, 5);
    expect(t.y + cam.y * t.scale).toBeCloseTo(VIEWPORT.vh / 2, 5);
  });

  it("reporte le zoom tel quel", () => {
    expect(planeTransform({ x: 0, y: 0, zoom: 3.5 }, VIEWPORT).scale).toBe(3.5);
  });
});

describe("salles", () => {
  it("aligne les salles en enfilade sans chevauchement", () => {
    for (let i = 0; i < 6; i++) {
      const a = roomRect(i);
      const b = roomRect(i + 1);
      expect(b.x).toBeGreaterThan(a.x + a.w);
      expect(b.x - (a.x + a.w)).toBeCloseTo(ROOM.gap, 5);
    }
  });

  it("centre la première salle sur l'origine", () => {
    const r = roomRect(0);
    expect(r.x + r.w / 2).toBeCloseTo(0, 5);
    expect(r.y + r.h / 2).toBeCloseTo(0, 5);
  });

  it("mesure la largeur totale d'une enfilade", () => {
    expect(roomsWidth(0)).toBe(0);
    expect(roomsWidth(1)).toBe(ROOM.w);
    expect(roomsWidth(3)).toBe(3 * ROOM.w + 2 * ROOM.gap);
  });
});
