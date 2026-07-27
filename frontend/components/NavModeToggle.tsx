"use client";

/**
 * Bascule entre la navigation classique (dock + palette) et le village
 * immersif. Applique `data-nav` sur <html> ; le script anti-flash du layout
 * restaure le choix avant le paint.
 *
 * L'icône est TOUJOURS la boussole, y compris village éteint. Une icône qui
 * change de nature selon l'état est indevinable : on ne peut pas décrire le
 * bouton à quelqu'un qui ne l'a jamais activé, puisqu'il ne voit pas encore
 * l'icône qu'on lui nomme. L'état passe donc par `aria-pressed`, la teinte et
 * l'infobulle — pas par un changement de symbole.
 */

import { Compass } from "lucide-react";
import { cn } from "@/lib/utils";
import { setNavMode, useNavMode } from "@/lib/village/navMode";

export function NavModeToggle() {
  const mode = useNavMode();
  const village = mode === "village";
  const label = village
    ? "Village activé — revenir à la navigation classique"
    : "Activer le village (navigation au scroll)";

  return (
    <button
      type="button"
      onClick={() => setNavMode(village ? "classique" : "village")}
      title={label}
      aria-label={label}
      aria-pressed={village}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
        village
          ? "bg-[color-mix(in_srgb,var(--ring)_14%,transparent)] text-[var(--nav-active-fg)]"
          : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
      )}
    >
      <Compass size={16} />
    </button>
  );
}
