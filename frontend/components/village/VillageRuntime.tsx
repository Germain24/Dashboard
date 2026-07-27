"use client";

/**
 * Le village en marche : une **surcouche**, pas un emballage.
 *
 * Il ne rend jamais le contenu de l'application — celui-ci vit à sa place
 * habituelle dans l'arbre. Cette séparation est structurelle : `useSearchParams`
 * force une frontière `<Suspense>`, et y enfermer toute l'application faisait
 * cohabiter le sous-arbre streamé par le serveur et celui rendu par le client
 * (deux pages module empilées, deux barres d'onglets).
 *
 * Aux niveaux 0 et 1, le rail se pose en plein écran par-dessus la page
 * d'accueil. Au niveau 2, la page module s'affiche telle quelle et le village
 * n'ajoute que son lavis et son HUD.
 */

import { useEffect } from "react";
import { motion, useReducedMotion } from "motion/react";
import { MODULE_GROUPS } from "@/lib/modules";
import { durations, springs } from "@/lib/motion/tokens";
import { DISTRICT_ACCENT } from "@/lib/village/art";
import { useNavMode } from "@/lib/village/navMode";
import { useVillage } from "@/lib/village/useVillage";
import { useVillageTabs } from "@/lib/village/tabs";
import { VillageHud } from "@/components/village/VillageHud";
import { VillageWorld } from "@/components/village/VillageWorld";

export function VillageRuntime() {
  const mode = useNavMode();
  const tabs = useVillageTabs();
  const village = mode === "village";
  const { state, dispatch } = useVillage(tabs, village);
  const reduced = useReducedMotion();

  // Marque le document tant que le village est réellement aux commandes : le
  // CSS s'en sert pour masquer le Dock, le fil d'Ariane et la nav mobile, et
  // pour dégager la place du HUD à l'intérieur d'un bâtiment.
  useEffect(() => {
    const root = document.documentElement;
    if (state) {
      root.setAttribute("data-village-active", "");
      root.setAttribute("data-village-level", String(state.level));
    } else {
      root.removeAttribute("data-village-active");
      root.removeAttribute("data-village-level");
    }
    return () => {
      root.removeAttribute("data-village-active");
      root.removeAttribute("data-village-level");
    };
  }, [state]);

  if (!state) return null;

  const group = MODULE_GROUPS[state.groupIndex];
  const accent = DISTRICT_ACCENT[group.group];
  const inside = state.level === 2;

  return (
    <>
      {inside ? (
        <div
          className="village-interior-wash"
          aria-hidden="true"
          style={{ ["--village-accent" as string]: accent }}
        />
      ) : (
        /*
          Changer de `key` remonte le sous-arbre et rejoue l'animation
          d'entrée. Pas d'`AnimatePresence` : l'enfant sortant y serait re-rendu
          à chaque navigation, ce qui relance son `animate` et annule sa sortie
          — le nœud resterait monté indéfiniment.
        */
        <div className="village-overlay">
          {/*
            Le calque opaque et l'élément animé sont séparés à dessein : animer
            l'opacité du calque lui-même laisse la page d'accueil transparaître
            tant que le ressort n'a pas fini de converger — et il repart de zéro
            à chaque changement de niveau. Le fond est donc opaque par
            construction, l'animation ne porte que sur le contenu.
          */}
          <motion.div
            key={`world-${state.level}`}
            className="village-overlay-inner"
            initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={reduced ? { duration: durations.fast } : springs.zoom}
          >
            <VillageWorld state={state} dispatch={dispatch} />
          </motion.div>
        </div>
      )}

      <VillageHud state={state} tabLabel={tabs.tabs[state.tabIndex]?.label} />
    </>
  );
}
