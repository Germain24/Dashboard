"use client";

/**
 * Wrapper générique d'une scène du Deck.
 *
 * Le snap reste en CSS. La couche `.deck-scene` porte le travelling continu lié
 * au scroll (zoom/translation), tandis que Motion orchestre la copie : sortie
 * rapide, puis entrée en cascade quand la caméra est presque stabilisée.
 * Chaque scène expose aussi sa couleur d'atmosphère via `--deck-accent`.
 */

import { useCallback, useRef, type CSSProperties, type ReactNode } from "react";
import { motion, useInView } from "motion/react";
import { fadeUp, staggerContainer } from "@/lib/motion/variants";

/** Enfant standard d'une DeckSection : entre en fondu + slide-up. */
export const MotionFadeUp = motion.create("div");

export function DeckSection({
  children,
  label,
  index,
  accent,
  sectionRef,
}: {
  children: ReactNode;
  label: string;
  index: number;
  accent?: string;
  sectionRef?: (el: HTMLElement | null) => void;
}) {
  const inViewRef = useRef<HTMLElement>(null);
  const setSectionRef = useCallback(
    (node: HTMLElement | null) => {
      inViewRef.current = node;
      sectionRef?.(node);
    },
    [sectionRef],
  );
  // La copie n'entre qu'après le passage plein cadre de la caméra.
  const inView = useInView(inViewRef, { once: false, amount: 0.72 });
  const style = accent ? ({ "--deck-accent": accent } as CSSProperties) : undefined;

  return (
    <section
      ref={setSectionRef}
      className="deck-section"
      aria-label={label}
      data-index={index}
      data-active={inView ? "true" : "false"}
      style={style}
    >
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate={inView ? "visible" : "hidden"}
        className="deck-scene relative mx-auto w-full max-w-[1328px] px-5 sm:px-6"
      >
        {children}
      </motion.div>
    </section>
  );
}

/** Helper : enfant fadeUp prêt à l'emploi. */
export function FadeUpItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <MotionFadeUp variants={fadeUp} className={className}>
      {children}
    </MotionFadeUp>
  );
}
