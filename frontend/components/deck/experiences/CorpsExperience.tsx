"use client";

/**
 * Expérience « Corps » (groupe Santé & Performance) — prototype de la nouvelle
 * norme : héros Score de forme + modules satellites (sommeil, macros, séance,
 * skincare), mise en page éditoriale asymétrique. Vitrine + drill-in.
 *
 * Parallax au scroll multi-couches : un halo et le titre se déplacent à des
 * vitesses différentes (profondeur), désactivé en reduced-motion.
 */

import { useRef } from "react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { DeckSection, FadeUpItem } from "@/components/deck/DeckSection";
import { useScrollParallax } from "@/lib/motion/useScrollParallax";
import { ScoreRingModule } from "@/components/deck/modules/ScoreRingModule";
import { MacrosModule } from "@/components/deck/modules/MacrosModule";
import { SleepModule } from "@/components/deck/modules/SleepModule";
import { NextWorkoutModule } from "@/components/deck/modules/NextWorkoutModule";
import { SkincareModule } from "@/components/deck/modules/SkincareModule";
import { MODULE_GROUPS } from "@/lib/modules";

const HEALTH_MODULES =
  MODULE_GROUPS.find((group) => group.group === "Santé & Performance")?.items ?? [];

export function CorpsExperience({
  index,
  accent,
  selectedModule = 0,
  onSelectModule,
  sectionRef,
}: {
  index: number;
  accent: string;
  selectedModule?: number;
  onSelectModule?: (index: number) => void;
  sectionRef?: (el: HTMLElement | null) => void;
}) {
  const titleRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const titleY = useScrollParallax(titleRef, 40);
  const haloY = useScrollParallax(titleRef, 90);

  return (
    <DeckSection label="Corps" index={index} accent={accent} sectionRef={sectionRef}>
      {/* Halo décoratif — désactivé sur mobile et reduced-motion (blur animé coûteux). */}
      {!reduced && (
        <motion.div
          aria-hidden="true"
          style={{ y: haloY }}
          className="pointer-events-none absolute -left-16 top-[18%] -z-10 hidden h-[440px] w-[440px] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--ring)_16%,transparent),transparent_70%)] blur-3xl md:block"
        />
      )}

      <div className="deck-composition deck-corps-composition">
        <FadeUpItem className="deck-copy">
          <motion.div ref={titleRef} style={{ y: titleY }}>
            <p className="deck-kicker">
              <span>{String(index).padStart(2, "0")}</span>
              État vivant
            </p>
            <h2>Corps</h2>
            <p className="deck-copy-body">
              Votre récupération, votre énergie et les routines du jour réunies dans une seule
              lecture.
            </p>
          </motion.div>
        </FadeUpItem>

        <div className="deck-corps-stage no-scrollbar">
          <FadeUpItem className="deck-corps-score">
            <ScoreRingModule />
          </FadeUpItem>
          <FadeUpItem className="deck-corps-card">
            <SleepModule />
          </FadeUpItem>
          <FadeUpItem className="deck-corps-card">
            <MacrosModule />
          </FadeUpItem>
          <FadeUpItem className="deck-corps-card">
            <NextWorkoutModule />
          </FadeUpItem>
          <FadeUpItem className="deck-corps-card">
            <SkincareModule />
          </FadeUpItem>
        </div>

        <FadeUpItem className="deck-district-key deck-corps-key" aria-label="Bâtiments — Corps">
          <p className="deck-card-kicker">Adresses du quartier</p>
          <div>
            {HEALTH_MODULES.map((module, moduleIndex) => (
              <Link
                key={module.slug}
                href={`/${module.slug}`}
                aria-label={module.label}
                aria-current={selectedModule === moduleIndex ? "location" : undefined}
                data-selected={selectedModule === moduleIndex ? "true" : undefined}
                onFocus={() => onSelectModule?.(moduleIndex)}
                onMouseEnter={() => onSelectModule?.(moduleIndex)}
              >
                <b>{String(moduleIndex + 1).padStart(2, "0")}</b>
                {module.label}
              </Link>
            ))}
          </div>
          <p className="deck-district-instruction">
            ↑↓ changer de quartier · ←→ choisir un bâtiment
          </p>
        </FadeUpItem>
      </div>
    </DeckSection>
  );
}
