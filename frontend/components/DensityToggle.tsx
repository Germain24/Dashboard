"use client";

/**
 * Toggle de densité d'affichage (confort / compact), persistant.
 * Applique `data-density` sur <html> (le CSS réduit la taille racine en compact).
 * Le script anti-flash du layout applique le choix avant le paint.
 */

import { useEffect, useState } from "react";
import { Rows3, Rows2 } from "lucide-react";

type Density = "comfortable" | "compact";
const STORAGE_KEY = "mc-density";

function apply(d: Density) {
  const root = document.documentElement;
  if (d === "compact") root.setAttribute("data-density", "compact");
  else root.removeAttribute("data-density");
}

export function DensityToggle() {
  const [density, setDensity] = useState<Density>("comfortable");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Density | null) ?? "comfortable";
    setDensity(stored);
    setMounted(true);
  }, []);

  function toggle() {
    const next: Density = density === "compact" ? "comfortable" : "compact";
    setDensity(next);
    localStorage.setItem(STORAGE_KEY, next);
    apply(next);
  }

  const compact = mounted && density === "compact";
  const Icon = compact ? Rows2 : Rows3;
  const label = compact ? "Densité compacte" : "Densité confort";

  return (
    <button
      type="button"
      onClick={toggle}
      title={label}
      aria-label={label}
      className="flex items-center justify-center h-8 w-8 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
    >
      <Icon size={16} />
    </button>
  );
}
