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
  it("un deep link module nu atterrit DANS LE CONTENU, pas dans le hall", () => {
    expect(deriveVillageState("/finance", {})).toEqual(at({ level: 3, ...FINANCE }));
  });

  it("`?v=salles` ouvre le hall des salles", () => {
    expect(deriveVillageState("/finance", { v: "salles" })).toEqual(
      at({ level: 2, ...FINANCE }),
    );
  });

  it("une valeur de vue inconnue retombe sur le contenu", () => {
    expect(deriveVillageState("/finance", { v: "nimporte" })).toEqual(
      at({ level: 3, ...FINANCE }),
    );
  });

  it("prend la salle active publiée par la page, pas l'URL", () => {
    expect(deriveVillageState("/finance", {}, 2)).toEqual(
      at({ level: 3, ...FINANCE, tabIndex: 2 }),
    );
  });

  it("sans salle publiée, retombe sur la première", () => {
    expect(deriveVillageState("/finance", {})).toEqual(
      at({ level: 3, ...FINANCE, tabIndex: 0 }),
    );
    expect(deriveVillageState("/finance", {}, -1)).toEqual(
      at({ level: 3, ...FINANCE, tabIndex: 0 }),
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

describe("villageReducer — niveau 2 (le hall des salles)", () => {
  const base = at({ level: 2, ...FINANCE });

  it("`up`/`down` parcourent les salles", () => {
    expect(villageReducer(base, "down", 3).tabIndex).toBe(1);
    expect(villageReducer({ ...base, tabIndex: 1 }, "up", 3).tabIndex).toBe(0);
  });

  it("clampe à la dernière salle", () => {
    expect(villageReducer({ ...base, tabIndex: 2 }, "down", 3).tabIndex).toBe(2);
  });

  it("`enter` (droite) entre dans la salle, sans en changer", () => {
    expect(villageReducer({ ...base, tabIndex: 2 }, "enter", 3)).toEqual({
      ...base,
      level: 3,
      tabIndex: 2,
    });
  });

  it("sans salles connues, le parcours est inerte", () => {
    expect(villageReducer(base, "down").tabIndex).toBe(0);
  });

  it("`back` (gauche) ressort du bâtiment", () => {
    expect(villageReducer({ ...base, tabIndex: 2 }, "back", 3)).toEqual({
      ...base,
      level: 1,
      tabIndex: 0,
    });
  });
});

describe("villageReducer — niveau 3 (on lit)", () => {
  const base = at({ level: 3, ...FINANCE, tabIndex: 2 });

  it("l'axe vertical est rendu au contenu : `up`/`down` ne font rien", () => {
    expect(villageReducer(base, "up", 5)).toEqual(base);
    expect(villageReducer(base, "down", 5)).toEqual(base);
  });

  it("`enter` ne descend pas plus bas", () => {
    expect(villageReducer(base, "enter", 5)).toEqual(base);
  });

  it("`back` ramène au hall, sur la salle qu'on quitte", () => {
    expect(villageReducer(base, "back", 5)).toEqual({ ...base, level: 2 });
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

  it("niveau 2 → la route module marquée `?v=salles`", () => {
    expect(urlForState(finance)).toBe("/finance?v=salles");
  });

  it("niveau 3 → la route module nue", () => {
    expect(urlForState({ ...finance, level: 3 })).toBe("/finance");
  });

  it("n'encode jamais la salle : elle vit dans la page, pas dans l'URL", () => {
    expect(urlForState({ ...finance, level: 3, tabIndex: 3 })).toBe("/finance");
    expect(urlForState({ ...finance, tabIndex: 3 })).toBe("/finance?v=salles");
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
