"use client";

/**
 * L'intérieur d'un bâtiment : une enfilade de salles.
 *
 * Rendu HORS du plan du village, en coordonnées d'écran. Deux raisons : une
 * enfilade posée sur la carte déborderait sur les bâtiments voisins dès qu'un
 * module a six onglets, et le contenu du niveau 3 ne doit jamais se retrouver
 * sous un `transform` — ça créerait un bloc conteneur et casserait les en-têtes
 * `sticky` des pages module.
 *
 * La continuité est préservée autrement : la couche apparaît en fondu pendant
 * que la caméra pousse encore vers la façade, et l'enfilade coulisse au même
 * ressort. On ne voit pas de coupure, on voit une entrée.
 */

import { motion, useReducedMotion } from "motion/react";
import { useVillageTabs } from "@/lib/village/tabs";
import type { VillageState } from "@/lib/village/state";

/** Largeur d'une salle à l'écran, et écart entre deux. */
const ROOM_VW = 34;
const GAP_VW = 4;

const SPRING = { stiffness: 92, damping: 24, mass: 1.1 } as const;

export function VillageRooms({
  state,
  accent,
  moduleLabel,
}: {
  state: VillageState;
  accent: string;
  moduleLabel: string;
}) {
  const reduced = useReducedMotion();
  const { tabs } = useVillageTabs();
  const inside = state.level >= 2;

  // Quelques modules dessinent leur barre d'onglets à la main plutôt que par
  // `ModuleHeader` : ils ne publient donc rien. Le hall ne doit pas rester vide
  // pour autant — il montre une salle unique au nom du module, et le geste
  // reste le même partout.
  const rooms = tabs.length > 0 ? tabs : [{ id: "__module", label: moduleLabel }];

  if (!inside) return null;

  const step = ROOM_VW + GAP_VW;
  const transition = reduced ? { duration: 0.12 } : SPRING;

  return (
    <motion.div
      className="village-rooms"
      aria-hidden="true"
      initial={{ opacity: 0 }}
      animate={{ opacity: state.level === 2 ? 1 : 0.25 }}
      transition={transition}
    >
      <motion.div
        className="village-rooms-strip"
        initial={false}
        animate={{ x: `calc(50vw - ${ROOM_VW / 2}vw - ${state.tabIndex * step}vw)` }}
        transition={transition}
      >
        {rooms.map((tab, i) => {
          const active = i === state.tabIndex;
          return (
            <motion.div
              key={tab.id}
              className="village-room"
              style={{
                width: `${ROOM_VW}vw`,
                marginRight: `${GAP_VW}vw`,
                // Translucide, pas opaque : une salle doit se lire COMME étant
                // dans le bâtiment. Un pavé plein masquerait la façade et
                // romprait l'illusion d'être entré quelque part.
                background: `linear-gradient(165deg, color-mix(in srgb, ${accent} 30%, transparent), color-mix(in srgb, ${accent} 8%, transparent))`,
                borderColor: `color-mix(in srgb, ${accent} 45%, transparent)`,
              }}
              animate={
                reduced
                  ? { opacity: active ? 1 : 0.45 }
                  : { scale: active ? 1 : 0.88, opacity: active ? 1 : 0.4 }
              }
              transition={transition}
            >
              <span className="village-room-label">{tab.label}</span>
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}
