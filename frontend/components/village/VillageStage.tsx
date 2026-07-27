"use client";

/**
 * Le monde et sa caméra.
 *
 * Remplace l'ancien rail de cartes. Toutes les images vivent à des positions
 * FIXES sur un plan unique ; seul ce plan bouge, par un seul `transform`.
 * Changer de quartier ou entrer dans un bâtiment ne remplace donc jamais
 * l'écran : la caméra voyage, et on la voit voyager.
 *
 * Le zoom est une `MotionValue` et non une prop recalculée à chaque état.
 * C'est ce détail qui fait toute la différence : les opacités des couches en
 * dérivent, si bien que les fondus se produisent PENDANT le mouvement, à
 * l'échelle réelle de la caméra. Piloter les fondus depuis l'état donnerait
 * des transitions entre écrans — exactement ce qu'on cherche à éviter.
 */

import { useEffect, useState } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from "motion/react";
import { MODULE_GROUPS } from "@/lib/modules";
import { DISTRICT_ACCENT, buildingArt, districtArt, worldArt } from "@/lib/village/art";
import { WORLD, buildingRect, districtRect } from "@/lib/village/layout";
import { cameraFor, planeTransform } from "@/lib/village/camera";
import type { VillageState } from "@/lib/village/state";
import { VillageLayer } from "@/components/village/VillageLayer";
import { VillageRooms } from "@/components/village/VillageRooms";

/**
 * Bandes de visibilité par couche, en zoom caméra. Les recouvrements sont
 * voulus : c'est là que se joue le fondu d'une échelle à la suivante.
 */
const BANDS = {
  world: [0, 1.4, 2.2, 2.6],
  district: [1.5, 2.0, 3.0, 3.6],
  building: [2.6, 3.4, 999, 1000],
} as const;

/** Ressort de la caméra : ample, sans rebond — un mouvement d'appareil, pas un ressort de jouet. */
const CAMERA_SPRING = { stiffness: 92, damping: 24, mass: 1.1 } as const;

function useViewport() {
  const [vp, setVp] = useState({ vw: 1440, vh: 800 });
  useEffect(() => {
    const read = () => setVp({ vw: window.innerWidth, vh: window.innerHeight });
    read();
    window.addEventListener("resize", read);
    window.addEventListener("orientationchange", read);
    return () => {
      window.removeEventListener("resize", read);
      window.removeEventListener("orientationchange", read);
    };
  }, []);
  return vp;
}

export function VillageStage({ state }: { state: VillageState }) {
  const reduced = useReducedMotion();
  const viewport = useViewport();

  const cam = cameraFor(state, viewport);
  const target = planeTransform(cam, viewport);

  // Trois valeurs animées, et rien d'autre. Le `useSpring` interpole en
  // continu depuis la position courante : un changement d'état en cours
  // d'animation infléchit la trajectoire au lieu de la redémarrer.
  const rawX = useMotionValue(target.x);
  const rawY = useMotionValue(target.y);
  const rawScale = useMotionValue(target.scale);

  const spring = reduced ? { duration: 0.001 } : CAMERA_SPRING;
  const x = useSpring(rawX, spring);
  const y = useSpring(rawY, spring);
  const scale = useSpring(rawScale, spring);

  useEffect(() => {
    rawX.set(target.x);
    rawY.set(target.y);
    rawScale.set(target.scale);
  }, [target.x, target.y, target.scale, rawX, rawY, rawScale]);

  // Opacités dérivées du zoom RÉEL, pas de l'état.
  const worldOpacity = useTransform(scale, BANDS.world as unknown as number[], [0, 1, 1, 0]);
  const districtOpacity = useTransform(scale, BANDS.district as unknown as number[], [0, 1, 1, 0]);
  const buildingOpacity = useTransform(scale, BANDS.building as unknown as number[], [0, 1, 1, 1]);

  const group = MODULE_GROUPS[state.groupIndex];
  const accent = DISTRICT_ACCENT[group.group];

  // Culling par l'ÉTAT et non par le zoom : monter/démonter au fil de
  // l'animation ferait clignoter les couches en plein vol.
  const visibleDistricts = MODULE_GROUPS.map((_, i) => i).filter(
    (i) => Math.abs(i - state.groupIndex) <= 1 || state.level === 0,
  );

  return (
    <div
      className="village-viewport"
      data-village-level={state.level}
      style={{ ["--village-accent" as string]: accent }}
    >
      <motion.div
        className="village-plane"
        style={{ x, y, scale, width: WORLD.w, height: WORLD.h }}
      >
        <VillageLayer rect={{ x: 0, y: 0, ...WORLD }} src={worldArt()} opacity={worldOpacity} />

        {visibleDistricts.map((i) => (
          <VillageLayer
            key={MODULE_GROUPS[i].group}
            rect={districtRect(i)}
            src={districtArt(MODULE_GROUPS[i].group)}
            opacity={districtOpacity}
            accent={DISTRICT_ACCENT[MODULE_GROUPS[i].group]}
            icon={MODULE_GROUPS[i].items[0].icon}
            label={MODULE_GROUPS[i].group}
            priority={i === state.groupIndex}
          />
        ))}

        {MODULE_GROUPS[state.groupIndex].items.map((m, j) => (
          <VillageLayer
            key={m.slug}
            rect={buildingRect(state.groupIndex, j)}
            src={buildingArt(m.slug)}
            opacity={buildingOpacity}
            accent={accent}
            icon={m.icon}
            label={m.label}
            priority={state.level >= 1 && j === state.moduleIndex}
            data-village-module={m.slug}
          />
        ))}
      </motion.div>

      {/* L'intérieur vit HORS du plan : une enfilade posée sur la carte
          déborderait sur les bâtiments voisins dès six salles. */}
      <VillageRooms
        state={state}
        accent={accent}
        moduleLabel={group.items[state.moduleIndex]?.label ?? group.group}
      />

      <VillageStageLabel state={state} />
    </div>
  );
}

/** Le nom de ce qu'on regarde, en surimpression — pas sur le plan. */
function VillageStageLabel({ state }: { state: VillageState }) {
  const group = MODULE_GROUPS[state.groupIndex];
  const mod = group.items[state.moduleIndex];
  const showBuilding = state.level >= 1;

  return (
    <div className="village-title" aria-hidden="true">
      <p className="village-title-eyebrow">{showBuilding ? group.group : "Quartier"}</p>
      <h2>{showBuilding ? mod?.label : group.group}</h2>
      <p className="village-title-sub">
        {showBuilding
          ? mod?.description
          : `${group.items.length} bâtiment${group.items.length > 1 ? "s" : ""}`}
      </p>
    </div>
  );
}
