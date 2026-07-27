import { describe, expect, it } from "vitest";
import { GROUP_SLUGS, MODULE_GROUPS } from "@/lib/modules";
import {
  ORPHAN_HOST,
  deriveVillageState,
  historyModeFor,
  modulesInGroup,
  sameState,
  segmentOf,
  urlForState,
  villageReducer,
  type VillageState,
} from "@/lib/village/state";

const LAST_GROUP = MODULE_GROUPS.length - 1;
const at = (over: Partial<VillageState> = {}): VillageState => ({
  level: 0,
  groupIndex: 0,
  moduleIndex: 0,
  tabIndex: 0,
  ...over,
});

/** Indices de `finance` dans la grille, sans les coder en dur. */
const FINANCE = (() => {
  for (let g = 0; g < MODULE_GROUPS.length; g++) {
    const m = MODULE_GROUPS[g].items.findIndex((i) => i.slug === "finance");
    if (m !== -1) return { groupIndex: g, moduleIndex: m };
  }
  throw new Error("module `finance` introuvable");
})();

describe("segmentOf", () => {
  it("extrait le premier segment", () => {
    expect(segmentOf("/")).toBe("");
    expect(segmentOf("/finance")).toBe("finance");
    expect(segmentOf("/finance/detail")).toBe("finance");
  });
});

describe("deriveVillageState — niveaux 0 et 1", () => {
  it("sans query param : premier quartier, niveau 0", () => {
    expect(deriveVillageState("/", {})).toEqual(at());
  });

  it("`?q=` sélectionne le quartier", () => {
    const slug = GROUP_SLUGS[MODULE_GROUPS[2].group];
    expect(deriveVillageState("/", { q: slug })).toEqual(at({ groupIndex: 2 }));
  });

  it("un quartier inconnu retombe sur le premier plutôt que de planter", () => {
    expect(deriveVillageState("/", { q: "atlantide" })).toEqual(at());
  });

  it("`?q=&b=` passe au niveau 1", () => {
    const group = MODULE_GROUPS[1];
    const target = group.items[1];
    expect(
      deriveVillageState("/", { q: GROUP_SLUGS[group.group], b: target.slug }),
    ).toEqual(at({ level: 1, groupIndex: 1, moduleIndex: 1 }));
  });

  it("un bâtiment absent du quartier demandé reste au niveau 0", () => {
    const group = MODULE_GROUPS[0];
    // `finance` n'appartient pas au premier quartier.
    expect(
      deriveVillageState("/", { q: GROUP_SLUGS[group.group], b: "finance" }),
    ).toEqual(at());
  });
});

describe("deriveVillageState — niveau 2", () => {
  it("un deep link module atterrit directement dans le bâtiment", () => {
    expect(deriveVillageState("/finance", {})).toEqual(at({ level: 2, ...FINANCE }));
  });

  it("prend l'onglet actif publié par la page, pas l'URL", () => {
    expect(deriveVillageState("/finance", {}, 2)).toEqual(
      at({ level: 2, ...FINANCE, tabIndex: 2 }),
    );
  });

  it("sans onglet publié, retombe sur le premier", () => {
    expect(deriveVillageState("/finance", {})).toEqual(
      at({ level: 2, ...FINANCE, tabIndex: 0 }),
    );
    expect(deriveVillageState("/finance", {}, -1)).toEqual(
      at({ level: 2, ...FINANCE, tabIndex: 0 }),
    );
  });

  it("les routes annexes s'ancrent sur leur bâtiment hôte", () => {
    const host = deriveVillageState("/score", {});
    for (const orphan of Object.keys(ORPHAN_HOST)) {
      expect(deriveVillageState(`/${orphan}`, {})).toEqual(host);
    }
  });

  it("une route hors village renvoie null", () => {
    expect(deriveVillageState("/route-inexistante", {})).toBeNull();
  });
});

describe("villageReducer — niveau 0", () => {
  it("descend et remonte entre quartiers", () => {
    expect(villageReducer(at(), "down").groupIndex).toBe(1);
    expect(villageReducer(at({ groupIndex: 1 }), "up").groupIndex).toBe(0);
  });

  it("clampe aux deux extrémités", () => {
    expect(villageReducer(at(), "up")).toEqual(at());
    const last = at({ groupIndex: LAST_GROUP });
    expect(villageReducer(last, "down")).toEqual(last);
  });

  it("`enter` descend au niveau 1 sur le premier bâtiment", () => {
    expect(villageReducer(at({ groupIndex: 3, moduleIndex: 5 }), "enter")).toEqual(
      at({ level: 1, groupIndex: 3, moduleIndex: 0 }),
    );
  });

  it("`back` ne fait rien à la racine du monde", () => {
    expect(villageReducer(at(), "back")).toEqual(at());
  });
});

describe("villageReducer — niveau 1", () => {
  const base = at({ level: 1, groupIndex: FINANCE.groupIndex });

  it("parcourt les bâtiments du quartier", () => {
    expect(villageReducer(base, "down").moduleIndex).toBe(1);
  });

  it("clampe au dernier bâtiment du quartier", () => {
    const max = modulesInGroup(base.groupIndex).length - 1;
    const last = { ...base, moduleIndex: max };
    expect(villageReducer(last, "down")).toEqual(last);
  });

  it("`enter` entre dans le bâtiment sur le premier onglet", () => {
    expect(villageReducer({ ...base, moduleIndex: 2 }, "enter")).toEqual({
      ...base,
      level: 2,
      moduleIndex: 2,
      tabIndex: 0,
    });
  });

  it("`back` remonte au niveau 0 en conservant le quartier", () => {
    expect(villageReducer({ ...base, moduleIndex: 2 }, "back")).toEqual({
      ...base,
      level: 0,
      moduleIndex: 2,
    });
  });
});

describe("villageReducer — niveau 2", () => {
  const base = at({ level: 2, ...FINANCE });

  it("`enter` (droite) avance d'un onglet", () => {
    expect(villageReducer(base, "enter", 3).tabIndex).toBe(1);
  });

  it("`enter` sur le dernier onglet ne déborde pas", () => {
    expect(villageReducer({ ...base, tabIndex: 2 }, "enter", 3).tabIndex).toBe(2);
  });

  it("`up`/`down` naviguent aussi les onglets (clavier)", () => {
    expect(villageReducer({ ...base, tabIndex: 1 }, "up", 3).tabIndex).toBe(0);
    expect(villageReducer(base, "down", 3).tabIndex).toBe(1);
  });

  it("sans onglets connus, la navigation d'onglet est inerte", () => {
    expect(villageReducer(base, "enter").tabIndex).toBe(0);
  });

  it("`back` (gauche) ressort du bâtiment et réinitialise l'onglet", () => {
    expect(villageReducer({ ...base, tabIndex: 2 }, "back", 3)).toEqual({
      ...base,
      level: 1,
      tabIndex: 0,
    });
  });
});

describe("urlForState", () => {
  const finance = at({ level: 2, ...FINANCE });
  const groupSlug = GROUP_SLUGS[MODULE_GROUPS[FINANCE.groupIndex].group];

  it("niveau 0 → `/?q=`", () => {
    expect(urlForState(at({ groupIndex: FINANCE.groupIndex }))).toBe(`/?q=${groupSlug}`);
  });

  it("niveau 1 → `/?q=&b=`", () => {
    expect(urlForState({ ...finance, level: 1 })).toBe(`/?q=${groupSlug}&b=finance`);
  });

  it("niveau 2 → la route module, sans encoder l'onglet", () => {
    expect(urlForState(finance)).toBe("/finance");
    // L'onglet vit dans la page, pas dans l'URL : changer d'onglet ne navigue pas.
    expect(urlForState({ ...finance, tabIndex: 3 })).toBe("/finance");
  });

  it("un état hors bornes dégrade proprement", () => {
    expect(urlForState(at({ groupIndex: 99 }))).toBe("/");
  });

  it("boucle : dériver l'URL produite redonne le même état", () => {
    const url = new URL(urlForState({ ...finance, level: 1 }), "http://x");
    expect(
      deriveVillageState(url.pathname, {
        q: url.searchParams.get("q"),
        b: url.searchParams.get("b"),
      }),
    ).toEqual({ ...finance, level: 1 });
  });
});

describe("historyModeFor / sameState", () => {
  it("empile l'historique au changement de niveau, le remplace sinon", () => {
    expect(historyModeFor(at(), at({ groupIndex: 2 }))).toBe("replace");
    expect(historyModeFor(at(), at({ level: 1 }))).toBe("push");
  });

  it("sameState compare les quatre coordonnées", () => {
    expect(sameState(at(), at())).toBe(true);
    expect(sameState(at(), at({ tabIndex: 1 }))).toBe(false);
  });
});
