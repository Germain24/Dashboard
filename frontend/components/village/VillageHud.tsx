"use client";

/**
 * Le HUD du village : où l'on est, ce qu'on peut faire, et comment en sortir.
 *
 * Il remplace le Dock (masqué en mode village) et porte l'annonce `aria-live`
 * qui rend la navigation gestuelle intelligible à un lecteur d'écran — sans
 * elle, changer de quartier au scroll ne produirait aucun retour vocal.
 */

import { ChevronLeft, ChevronRight, ChevronsUpDown, Search } from "lucide-react";
import { MODULE_GROUPS } from "@/lib/modules";
import { NavModeToggle } from "@/components/NavModeToggle";
import type { VillageState } from "@/lib/village/state";

function trail(state: VillageState, tabLabel?: string): string[] {
  const group = MODULE_GROUPS[state.groupIndex];
  if (!group) return [];
  if (state.level === 0) return [group.group];
  const mod = group.items[state.moduleIndex];
  if (!mod) return [group.group];
  if (state.level === 1) return [group.group, mod.label];
  return tabLabel ? [group.group, mod.label, tabLabel] : [group.group, mod.label];
}

export function VillageHud({
  state,
  tabLabel,
}: {
  state: VillageState;
  tabLabel?: string;
}) {
  const path = trail(state, tabLabel);
  const inside = state.level === 2;

  return (
    <div className="village-hud" data-village-hud>
      <nav
        aria-label="Position dans le village"
        className="glass-panel village-hud-panel"
      >
        <p className="village-trail">
          {path.map((part, i) => (
            <span key={part}>
              {i > 0 && <span aria-hidden="true"> › </span>}
              <span className={i === path.length - 1 ? "village-trail-current" : undefined}>
                {part}
              </span>
            </span>
          ))}
        </p>

        <span className="village-hud-sep" aria-hidden="true" />

        <p className="village-hints" aria-hidden="true">
          <span>
            <ChevronsUpDown size={13} />
            {inside ? "lire" : "parcourir"}
          </span>
          <span>
            <ChevronRight size={13} />
            {inside ? "onglet" : "entrer"}
          </span>
          {state.level > 0 && (
            <span>
              <ChevronLeft size={13} />
              retour
            </span>
          )}
        </p>

        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent("mc:command-palette"))}
          aria-label="Rechercher et naviguer"
          aria-keyshortcuts="Meta+K Control+K"
          title="Rechercher (Ctrl/Cmd+K)"
          className="village-hud-btn"
        >
          <Search size={15} />
        </button>
        <NavModeToggle />
      </nav>

      {/* Annonce la position à chaque changement d'état. */}
      <p aria-live="polite" className="sr-only">
        {path.join(", ")}
      </p>
    </div>
  );
}
