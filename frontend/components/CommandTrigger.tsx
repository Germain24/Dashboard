"use client";

/**
 * Déclencheur visible de la palette de commandes (⌘K / Ctrl K).
 *
 * Stylé comme un champ de recherche pour signaler l'affordance, là où la
 * palette n'était jusqu'ici découvrable que par hasard. Au clic, émet
 * l'évènement écouté par <CommandPalette>. L'indice clavier n'apparaît qu'après
 * montage (détection mac/non-mac) pour éviter un mismatch d'hydratation.
 */

import { useEffect, useState } from "react";
import { Search } from "lucide-react";

export function CommandTrigger() {
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    const isMac = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    setHint(isMac ? "⌘K" : "Ctrl K");
  }, []);

  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent("mc:command-palette"))}
      aria-label="Rechercher et naviguer"
      aria-keyshortcuts="Meta+K Control+K"
      className="flex w-full items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] bg-[var(--field)] px-3 py-2 text-sm text-[var(--muted-foreground)] transition-colors duration-200 hover:border-[color-mix(in_srgb,var(--ring)_40%,transparent)] hover:text-[var(--foreground)]"
    >
      <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 text-left">Rechercher…</span>
      {hint && (
        <kbd className="shrink-0 rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-[var(--muted-foreground)]">
          {hint}
        </kbd>
      )}
    </button>
  );
}
