"use client";

/**
 * Transition de page, keyée sur le MODULE (1er segment d'URL) :
 * naviguer à l'intérieur d'un module ne rejoue rien (fini le « flash »
 * à chaque clic), changer de module joue une sortie brève puis une entrée
 * spatiale douce.
 *
 * Le conteneur public reste statique : les transforms/filtres ne vivent que
 * sur la scène animée et sont explicitement remis à `none` en fin d'entrée.
 * Les descendants `position: fixed` (rail de points du Deck) retrouvent ainsi
 * le viewport comme bloc conteneur une fois la transition terminée.
 * Remplace src/app/template.tsx (qui remontait à CHAQUE navigation).
 */

import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { durations, EASE_CAMERA } from "./tokens";

const ENTER = {
  opacity: 1,
  y: 0,
  scale: 1,
  filter: "blur(0px)",
  transition: {
    duration: durations.routeEnter,
    ease: EASE_CAMERA,
  },
  transitionEnd: {
    transform: "none",
    filter: "none",
  },
} as const;

const EXIT = {
  opacity: 0,
  y: -8,
  scale: 0.992,
  filter: "blur(4px)",
  transition: {
    duration: durations.routeExit,
    ease: EASE_CAMERA,
  },
} as const;

const INITIAL = {
  opacity: 0,
  y: 18,
  scale: 0.985,
  filter: "blur(10px)",
} as const;

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const reduced = useReducedMotion();
  const segment = "/" + (pathname.split("/")[1] ?? "");

  return (
    <div data-testid="page-transition" data-segment={segment}>
      {reduced ? (
        children
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={segment}
            initial={INITIAL}
            animate={ENTER}
            exit={EXIT}
            style={{ willChange: "auto" }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}
