"use client";

/**
 * Le hook du village : lit l'état dans l'URL, écoute les gestes, repousse
 * l'URL. Aucun état de navigation en React — l'URL fait foi, ce qui donne
 * gratuitement le bouton retour, F5, les favoris et les liens partagés.
 */

import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  actionForKey,
  actionForSwipe,
  initialAccumulator,
  resolveGesture,
  type GestureAccumulator,
} from "@/lib/village/gestures";
import { useSelectVillageTab, type TabsView } from "@/lib/village/tabs";
import {
  deriveVillageState,
  historyModeFor,
  sameState,
  urlForState,
  villageReducer,
  type VillageAction,
  type VillageState,
} from "@/lib/village/state";

/**
 * Contextes où le village doit rendre la main : saisie de texte, boîte de
 * dialogue ouverte, ou zone qui s'est explicitement désabonnée.
 */
function isInert(target: EventTarget | null): boolean {
  const el = target instanceof Element ? target : null;
  if (el?.closest('input, textarea, select, [contenteditable="true"]')) return true;
  if (el?.closest("[data-village-ignore]")) return true;
  return Boolean(document.querySelector('[role="dialog"][data-state="open"]'));
}

export type Village = {
  /** `null` quand la route ne fait pas partie du village. */
  state: VillageState | null;
  dispatch: (action: VillageAction) => void;
};

const EMPTY_TABS: TabsView = { tabs: [], activeIndex: 0 };

/**
 * @param enabled à `false` (mode classique), les écouteurs restent posés mais
 *   n'agissent jamais. Un hook conditionnel casserait l'ordre des hooks ;
 *   c'est le drapeau qui est conditionnel, pas l'appel.
 */
export function useVillage(tabs: TabsView = EMPTY_TABS, enabled = true): Village {
  const pathname = usePathname();
  const search = useSearchParams();
  const router = useRouter();
  const selectTab = useSelectVillageTab();

  const q = search.get("q");
  const b = search.get("b");
  const v = search.get("v");

  const state = useMemo(
    () => (enabled ? deriveVillageState(pathname, { q, b, v }, tabs.activeIndex) : null),
    [enabled, pathname, q, b, v, tabs.activeIndex],
  );

  // Référence vivante : les écouteurs natifs sont posés une fois et ne doivent
  // pas se ré-attacher à chaque navigation.
  const ref = useRef({ state, tabs, selectTab });
  useEffect(() => {
    ref.current = { state, tabs, selectTab };
  }, [state, tabs, selectTab]);

  const dispatch = useCallback(
    (action: VillageAction) => {
      const { state: current, tabs: liveTabs, selectTab: select } = ref.current;
      if (!current) return;
      const next = villageReducer(current, action, liveTabs.tabs.length);
      if (sameState(current, next)) return;

      // Changer de salle ne navigue pas : l'onglet actif vit dans la page. On
      // appelle son `onChange`, et l'état se re-dérive de la republication.
      // Parcourir le hall change donc DÉJÀ l'onglet affiché derrière, si bien
      // qu'entrer dans la salle n'a plus rien à charger.
      if (current.level === 2 && next.level === 2) {
        select?.(next.tabIndex);
        return;
      }

      const href = urlForState(next);
      if (historyModeFor(current, next) === "push") router.push(href);
      else router.replace(href, { scroll: false });
    },
    [router],
  );

  // ── Molette et trackpad ────────────────────────────────────────────────
  useEffect(() => {
    let acc: GestureAccumulator = initialAccumulator;

    const onWheel = (e: WheelEvent) => {
      const current = ref.current.state;
      if (!current || e.ctrlKey || e.metaKey || isInert(e.target)) return;

      // Le vertical n'appartient au contenu de la page qu'au niveau 3, celui
      // où on lit vraiment. Aux niveaux 0 à 2 il fait voyager la caméra —
      // entre quartiers, entre bâtiments, puis entre salles.
      const allowVertical = current.level !== 3;

      const { acc: next, action, consumed } = resolveGesture(acc, {
        dx: e.deltaX,
        dy: e.deltaY,
        at: e.timeStamp,
        allowVertical,
        allowHorizontal: true,
      });
      acc = next;

      if (consumed && e.cancelable) e.preventDefault();
      if (action) dispatch(action);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, [dispatch]);

  // ── Clavier ────────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const current = ref.current.state;
      if (!current || isInert(e.target)) return;

      // La barre d'onglets gère elle-même ←/→ (navigation à tabIndex glissant,
      // pattern ARIA). Sans cette garde, la touche serait traitée DEUX fois :
      // une fois par le bouton, une fois par le village — on sauterait deux
      // onglets, ou on changerait d'onglet en ressortant du bâtiment.
      const el = e.target instanceof Element ? e.target : null;
      if (el?.closest('[role="tablist"]')) return;

      const action = actionForKey(e.key);
      if (!action) return;
      // Au niveau 2 les flèches verticales restent le seul moyen clavier de
      // changer d'onglet — c'est voulu, la molette y scrolle le contenu.
      e.preventDefault();
      dispatch(action);
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch]);

  // ── Tactile ────────────────────────────────────────────────────────────
  useEffect(() => {
    let start: { x: number; y: number } | null = null;

    const onStart = (e: TouchEvent) => {
      const t = e.touches[0];
      start = t && !isInert(e.target) ? { x: t.clientX, y: t.clientY } : null;
    };

    const onEnd = (e: TouchEvent) => {
      const current = ref.current.state;
      const t = e.changedTouches[0];
      if (!start || !t || !current) return;
      const dx = t.clientX - start.x;
      const dy = t.clientY - start.y;
      start = null;

      const action = actionForSwipe(dx, dy);
      // Niveau 2 : le balayage vertical fait défiler la page, pas le village.
      if (!action) return;
      if (current.level === 3 && (action === "up" || action === "down")) return;
      dispatch(action);
    };

    window.addEventListener("touchstart", onStart, { passive: true });
    window.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      window.removeEventListener("touchstart", onStart);
      window.removeEventListener("touchend", onEnd);
    };
  }, [dispatch]);

  return { state, dispatch };
}
