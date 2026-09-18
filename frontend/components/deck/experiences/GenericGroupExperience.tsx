"use client";

/**
 * Rendu générique des groupes du Deck.
 *
 * Chaque domaine devient un quartier de la carte isométrique persistante.
 * Les bâtiments portent la navigation principale ; cette couche éditoriale
 * donne les noms et un accès alternatif compact, sans masquer l'architecture.
 */

import Link from "next/link";
import { DeckSection, FadeUpItem } from "@/components/deck/DeckSection";
import type { MODULE_GROUPS } from "@/lib/modules";

type Group = (typeof MODULE_GROUPS)[number];

const GROUP_COPY: Record<Group["group"], string> = {
  "Exécution & Système":
    "Cadrez la journée, les priorités et les automatismes depuis un même point de contrôle.",
  "Finances & Ingénierie":
    "Lisez vos flux, votre patrimoine et vos décisions d’investissement avec une vue longue.",
  "Santé & Performance":
    "Mesurez la récupération, l’entraînement et les routines qui soutiennent votre énergie.",
  "Carrière & Études":
    "Gardez les échéances, les heures et les objectifs de progression dans la même trajectoire.",
  "Culture & Loisirs":
    "Faites vivre vos bibliothèques et choisissez la prochaine expérience sans perdre le fil.",
  "Style & Horizons":
    "Préparez ce que vous portez, apprenez et explorez comme un seul horizon personnel.",
  Configuration:
    "Pilotez les données, les routines et la mécanique discrète qui maintient le système fiable.",
};

export function GenericGroupExperience({
  group,
  index,
  accent,
  selectedModule = 0,
  onSelectModule,
  sectionRef,
}: {
  group: Group;
  index: number;
  accent: string;
  selectedModule?: number;
  onSelectModule?: (index: number) => void;
  sectionRef?: (el: HTMLElement | null) => void;
}) {
  return (
    <DeckSection label={group.group} index={index} accent={accent} sectionRef={sectionRef}>
      <div className="deck-district-overlay">
        <FadeUpItem className="deck-copy deck-district-copy">
          <p className="deck-kicker">
            <span>{String(index).padStart(2, "0")}</span>
            Quartier
          </p>
          <h2>{group.group}</h2>
          <p className="deck-copy-body">{GROUP_COPY[group.group]}</p>
        </FadeUpItem>

        <FadeUpItem className="deck-district-key" aria-label={`Bâtiments — ${group.group}`}>
          <p className="deck-card-kicker">Adresses du quartier</p>
          <div>
            {group.items.map((module, moduleIndex) =>
              module.ready === false ? (
                <span
                  key={module.slug}
                  aria-disabled="true"
                  data-selected={selectedModule === moduleIndex ? "true" : undefined}
                >
                  <b>{String(moduleIndex + 1).padStart(2, "0")}</b>
                  {module.label}
                </span>
              ) : (
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
              ),
            )}
          </div>
          <p className="deck-district-instruction">
            ↑↓ changer de quartier · ←→ choisir un bâtiment
          </p>
        </FadeUpItem>
      </div>
    </DeckSection>
  );
}
