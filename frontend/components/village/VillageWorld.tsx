"use client";

/**
 * Niveaux 0 et 1 du village : le rail vertical.
 *
 * Un seul composant pour les deux niveaux — c'est le même geste et la même
 * mécanique, seule la liste change (les quartiers, puis leurs bâtiments). La
 * position vient de l'index d'état, jamais du scroll natif : pas de
 * scroll-snap, pas d'IntersectionObserver, donc pas de désynchronisation
 * possible entre ce qu'on voit et ce que dit l'URL.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { MODULE_GROUPS } from "@/lib/modules";
import { springs, durations } from "@/lib/motion/tokens";
import { DISTRICT_ACCENT, buildingArt, districtArt } from "@/lib/village/art";
import { urlForState, type VillageAction, type VillageState } from "@/lib/village/state";
import { VillageArt } from "@/components/village/VillageArt";

/** Hauteur d'une case du rail, en unités de viewport. */
const SLOT_VH = 62;

type Item = {
  key: string;
  label: string;
  description: string;
  icon: LucideIcon;
  accent: string;
  art: string | null;
  href: string;
};

function itemsFor(state: VillageState): Item[] {
  if (state.level === 0) {
    return MODULE_GROUPS.map((g, i) => ({
      key: g.group,
      label: g.group,
      description: `${g.items.length} bâtiment${g.items.length > 1 ? "s" : ""}`,
      icon: g.items[0].icon,
      accent: DISTRICT_ACCENT[g.group],
      art: districtArt(g.group),
      href: urlForState({ ...state, level: 0, groupIndex: i }),
    }));
  }

  const group = MODULE_GROUPS[state.groupIndex];
  const accent = DISTRICT_ACCENT[group.group];
  return group.items.map((m) => ({
    key: m.slug,
    label: m.label,
    description: m.description,
    icon: m.icon,
    accent,
    art: buildingArt(m.slug),
    href: `/${m.slug}`,
  }));
}

export function VillageWorld({
  state,
  dispatch,
}: {
  state: VillageState;
  dispatch: (action: VillageAction) => void;
}) {
  const reduced = useReducedMotion();
  const items = itemsFor(state);
  const activeIndex = state.level === 0 ? state.groupIndex : state.moduleIndex;
  const group = MODULE_GROUPS[state.groupIndex];
  const accent = DISTRICT_ACCENT[group.group];

  return (
    <div
      className="village-stage"
      data-village-level={state.level}
      data-village-group={group.group}
      style={{ ["--village-accent" as string]: accent }}
    >
      <div
        className="village-wash"
        aria-hidden="true"
        style={{
          background: `radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, ${accent} 14%, transparent), transparent 70%)`,
        }}
      />

      <motion.div
        role="listbox"
        aria-label={state.level === 0 ? "Quartiers" : `Bâtiments — ${group.group}`}
        aria-activedescendant={`village-opt-${items[activeIndex]?.key}`}
        className="village-rail"
        // `initial={false}` : au montage le rail doit être DÉJÀ en place. Sans
        // ça, il part de y=0 et défile depuis le premier quartier à chaque
        // arrivée — on voit passer toute la liste avant d'atterrir.
        initial={false}
        animate={{ y: `calc(50vh - ${SLOT_VH / 2}vh - ${activeIndex * SLOT_VH}vh)` }}
        transition={reduced ? { duration: durations.fast } : springs.rail}
      >
        {items.map((item, i) => {
          const active = i === activeIndex;
          return (
            <motion.div
              key={item.key}
              id={`village-opt-${item.key}`}
              role="option"
              aria-selected={active}
              className="village-slot"
              style={{ height: `${SLOT_VH}vh` }}
              animate={
                reduced
                  ? { opacity: active ? 1 : 0.5 }
                  : { scale: active ? 1 : 0.86, opacity: active ? 1 : 0.32 }
              }
              transition={reduced ? { duration: durations.fast } : springs.rail}
            >
              <Link
                href={item.href}
                tabIndex={active ? 0 : -1}
                onClick={(e) => {
                  // Au niveau 0, cliquer une carte revient à « entrer » : on
                  // laisse la machine à états décider de l'URL.
                  if (state.level === 0) {
                    e.preventDefault();
                    dispatch("enter");
                  }
                }}
                className="village-card"
                data-village-module={state.level === 1 ? item.key : undefined}
              >
                <div className="village-card-art">
                  <VillageArt
                    src={item.art}
                    accent={item.accent}
                    icon={item.icon}
                    label={item.label}
                    active={active}
                  />
                </div>
                <div className="village-card-copy">
                  <h2>{item.label}</h2>
                  <p>{item.description}</p>
                </div>
              </Link>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
