/**
 * Machine à états du village — logique pure, sans React ni DOM.
 *
 * Le village est une navigation à trois niveaux posée AU-DESSUS des routes
 * existantes ; il n'en crée aucune. L'URL reste la source de vérité unique
 * (comme `useTabParam`), ce qui donne gratuitement le bouton retour, F5, les
 * favoris et les liens partagés.
 *
 *   niveau 0 — les quartiers   → `/?q=<groupSlug>`
 *   niveau 1 — les bâtiments   → `/?q=<groupSlug>&b=<moduleSlug>`
 *   niveau 2 — les salles      → `/<moduleSlug>?v=salles`
 *   niveau 3 — le contenu      → `/<moduleSlug>`
 *
 * Le niveau 3 porte l'URL nue à dessein : un lien partagé `/finance` doit
 * ouvrir la donnée, pas le hall du bâtiment.
 *
 * Tout ici est pur et testé : le hook React (`useVillage`) ne fait que lire
 * l'URL, appeler `villageReducer`, puis pousser `urlForState`.
 */

import {
  GROUP_SLUGS,
  MODULE_GROUPS,
  groupForSlug,
  moduleForSlug,
  type Module,
} from "@/lib/modules";

export type VillageLevel = 0 | 1 | 2 | 3;

/** Valeur du paramètre `?v=` qui distingue le hall des salles du contenu. */
export const ROOMS_VIEW = "salles";

/** Les quatre gestes, déjà normalisés par la couche gestuelle. */
export type VillageAction = "up" | "down" | "enter" | "back";

export type VillageState = {
  level: VillageLevel;
  /** Index dans `MODULE_GROUPS`. */
  groupIndex: number;
  /** Index dans `MODULE_GROUPS[groupIndex].items`. */
  moduleIndex: number;
  /** Index de la salle (= de l'onglet), niveaux 2 et 3. */
  tabIndex: number;
};

/**
 * Routes réelles qui n'appartiennent à aucun groupe de `MODULES` : elles
 * existent sous `src/app/` et sont atteignables via Score ou la palette de
 * commandes. Sans ce rattachement, `moduleForSlug()` renvoie `undefined` et le
 * village n'a pas de bâtiment où ancrer la page.
 */
export const ORPHAN_HOST: Record<string, string> = {
  habitudes: "score",
  journal: "score",
  bilan: "score",
  snapshot: "score",
  "vue-360": "score",
};

const clamp = (v: number, max: number) => Math.max(0, Math.min(v, max));

/** Bâtiments du quartier `groupIndex`, tableau vide si l'index est hors bornes. */
export function modulesInGroup(groupIndex: number): Module[] {
  return MODULE_GROUPS[groupIndex]?.items ?? [];
}

/** Localise un module dans la grille quartier/bâtiment. */
function locate(slug: string): { groupIndex: number; moduleIndex: number } | null {
  for (let g = 0; g < MODULE_GROUPS.length; g++) {
    const m = MODULE_GROUPS[g].items.findIndex((it) => it.slug === slug);
    if (m !== -1) return { groupIndex: g, moduleIndex: m };
  }
  return null;
}

/** Premier segment de chemin, sans slash. `/finance` → `finance`, `/` → `''`. */
export function segmentOf(pathname: string): string {
  return pathname.split("/")[1] ?? "";
}

/**
 * Reconstruit l'état depuis l'URL.
 *
 * Renvoie `null` quand la route ne fait pas partie du village (404, route
 * inconnue) : l'appelant rend alors le contenu tel quel, sans décor.
 *
 * @param activeTabIndex onglet actif du module, publié par `ModuleHeader`.
 *   Il ne vient PAS de l'URL : dans ce repo l'onglet vit dans un `useState`
 *   local à chaque page, `?tab=` ne pilote rien.
 */
export function deriveVillageState(
  pathname: string,
  params: { q?: string | null; b?: string | null; v?: string | null },
  activeTabIndex = 0,
): VillageState | null {
  const segment = segmentOf(pathname);

  // ── Niveau 0 / 1 : l'accueil, piloté par les query params ──────────────
  if (segment === "") {
    const group = params.q ? groupForSlug(params.q) : undefined;
    const groupIndex = group
      ? MODULE_GROUPS.findIndex((g) => g.group === group)
      : 0;
    const safeGroup = clamp(groupIndex, MODULE_GROUPS.length - 1);

    const moduleIndex = params.b
      ? modulesInGroup(safeGroup).findIndex((m) => m.slug === params.b)
      : -1;

    return moduleIndex >= 0
      ? { level: 1, groupIndex: safeGroup, moduleIndex, tabIndex: 0 }
      : { level: 0, groupIndex: safeGroup, moduleIndex: 0, tabIndex: 0 };
  }

  // ── Niveau 2 : une route module (ou une de ses annexes) ────────────────
  const hostSlug = moduleForSlug(segment) ? segment : ORPHAN_HOST[segment];
  if (!hostSlug) return null;

  const at = locate(hostSlug);
  if (!at) return null;

  return {
    // `?v=salles` = on parcourt le hall ; sans lui, on est dans le contenu.
    level: params.v === ROOMS_VIEW ? 2 : 3,
    groupIndex: at.groupIndex,
    moduleIndex: at.moduleIndex,
    tabIndex: Math.max(0, activeTabIndex),
  };
}

/**
 * Applique un geste. Pur, total (toujours un état valide), clampé aux bornes.
 *
 * Chaque niveau a son axe vertical : les quartiers, puis les bâtiments, puis
 * les salles. « Droite » descend d'un niveau, « gauche » remonte. Le niveau 3
 * fait exception : l'axe vertical y appartient au contenu de la page, qu'il
 * faut pouvoir lire — `up`/`down` n'y font donc rien.
 *
 * @param tabCount nombre de salles du module courant (0 si inconnu).
 */
export function villageReducer(
  state: VillageState,
  action: VillageAction,
  tabCount = 0,
): VillageState {
  switch (state.level) {
    case 0: {
      const max = MODULE_GROUPS.length - 1;
      if (action === "up") return { ...state, groupIndex: clamp(state.groupIndex - 1, max) };
      if (action === "down") return { ...state, groupIndex: clamp(state.groupIndex + 1, max) };
      if (action === "enter") return { ...state, level: 1, moduleIndex: 0 };
      return state; // `back` : on est déjà à la racine du monde
    }

    case 1: {
      const max = modulesInGroup(state.groupIndex).length - 1;
      if (max < 0) return { ...state, level: 0 };
      if (action === "up") return { ...state, moduleIndex: clamp(state.moduleIndex - 1, max) };
      if (action === "down") return { ...state, moduleIndex: clamp(state.moduleIndex + 1, max) };
      if (action === "enter") return { ...state, level: 2, tabIndex: 0 };
      return { ...state, level: 0 };
    }

    case 2: {
      const max = Math.max(0, tabCount - 1);
      if (action === "up") return { ...state, tabIndex: clamp(state.tabIndex - 1, max) };
      if (action === "down") return { ...state, tabIndex: clamp(state.tabIndex + 1, max) };
      if (action === "enter") return { ...state, level: 3 };
      return { ...state, level: 1, tabIndex: 0 };
    }

    case 3: {
      // On lit. Seul « gauche » répond : il ramène dans le hall, sur la salle
      // qu'on vient de quitter.
      if (action === "back") return { ...state, level: 2 };
      return state;
    }
  }
}

/**
 * URL correspondant à un état.
 *
 * L'onglet n'y figure PAS : il vit dans la page, pas dans l'URL. Changer de
 * salle ne navigue donc pas — le village appelle le `onChange` publié par
 * `ModuleHeader` (voir `lib/village/tabs.tsx`).
 */
export function urlForState(state: VillageState): string {
  const group = MODULE_GROUPS[state.groupIndex];
  if (!group) return "/";

  if (state.level === 0) return `/?q=${GROUP_SLUGS[group.group]}`;

  const mod = group.items[state.moduleIndex];
  if (!mod) return `/?q=${GROUP_SLUGS[group.group]}`;

  if (state.level === 1) return `/?q=${GROUP_SLUGS[group.group]}&b=${mod.slug}`;
  if (state.level === 2) return `/${mod.slug}?v=${ROOMS_VIEW}`;

  return `/${mod.slug}`;
}

/**
 * Changer de niveau empile une entrée d'historique (le retour navigateur =
 * « ressortir », le geste attendu) ; se déplacer au sein d'un niveau la
 * remplace, sinon parcourir les 24 bâtiments noierait l'historique.
 */
export function historyModeFor(prev: VillageState, next: VillageState): "push" | "replace" {
  return prev.level === next.level ? "replace" : "push";
}

/** Deux états décrivent-ils la même position ? Évite les navigations inutiles. */
export function sameState(a: VillageState, b: VillageState): boolean {
  return (
    a.level === b.level &&
    a.groupIndex === b.groupIndex &&
    a.moduleIndex === b.moduleIndex &&
    a.tabIndex === b.tabIndex
  );
}
