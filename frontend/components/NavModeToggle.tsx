"use client";

/**
 * Bascule entre la navigation classique (dock + palette) et le village
 * immersif. Applique `data-nav` sur <html> ; le script anti-flash du layout
 * restaure le choix avant le paint.
 */

import { Compass, LayoutGrid } from "lucide-react";
import { setNavMode, useNavMode } from "@/lib/village/navMode";

export function NavModeToggle() {
  const mode = useNavMode();
  const village = mode === "village";
  const Icon = village ? Compass : LayoutGrid;
  const label = village ? "Navigation : village" : "Navigation : classique";

  return (
    <button
      type="button"
      onClick={() => setNavMode(village ? "classique" : "village")}
      title={`${label} — cliquer pour basculer`}
      aria-label={label}
      aria-pressed={village}
      className="flex items-center justify-center h-8 w-8 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
    >
      <Icon size={16} />
    </button>
  );
}
