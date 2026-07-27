"use client";

/**
 * Une couche d'échelle posée sur le plan.
 *
 * Positionnée en unités de plan, jamais en pixels d'écran : c'est le
 * `transform` du plan qui la met à l'échelle. Son opacité vient d'une
 * `MotionValue` dérivée du zoom, donc elle apparaît et s'efface pendant le vol
 * de la caméra.
 *
 * Sans visuel généré, la couche retombe sur la façade procédurale de
 * `VillageArt` — un module ajouté demain s'affiche donc sans qu'on ait à
 * penser à son image.
 */

import Image from "next/image";
import { motion, type MotionValue } from "motion/react";
import type { LucideIcon } from "lucide-react";
import type { Rect } from "@/lib/village/layout";
import { VillageArt } from "@/components/village/VillageArt";

type Props = {
  rect: Rect;
  src: string | null;
  opacity: MotionValue<number>;
  accent?: string;
  icon?: LucideIcon;
  label?: string;
  priority?: boolean;
  "data-village-module"?: string;
};

export function VillageLayer({
  rect,
  src,
  opacity,
  accent,
  icon,
  label,
  priority = false,
  ...rest
}: Props) {
  return (
    <motion.div
      className="village-layer"
      style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h, opacity }}
      {...rest}
    >
      {src ? (
        <Image
          src={src}
          alt=""
          fill
          // La couche est mise à l'échelle par le plan : sa taille CSS ne dit
          // rien de sa taille à l'écran. On demande donc la pleine résolution,
          // sinon Next servirait une vignette qu'on verrait exploser au zoom.
          sizes="1200px"
          priority={priority}
          loading={priority ? "eager" : undefined}
          className="object-contain"
          draggable={false}
        />
      ) : (
        accent &&
        icon &&
        label && <VillageArt src={null} accent={accent} icon={icon} label={label} />
      )}
    </motion.div>
  );
}
