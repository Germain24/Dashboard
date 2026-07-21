"use client";

/**
 * Toggle de densité d'affichage (confort / compact), persistant.
 * Applique `data-density` sur <html> (le CSS réduit la taille racine en compact).
 * Le script anti-flash du layout applique le choix avant le paint.
 */

import { useSyncExternalStore } from "react";
import { Rows3, Rows2 } from "lucide-react";

type Density = "comfortable" | "compact";
const STORAGE_KEY = "mc-density";
const listeners = new Set<() => void>();

function apply(d: Density) {
  const root = document.documentElement;
  if (d === "compact") root.setAttribute("data-density", "compact");
  else root.removeAttribute("data-density");
}

function getDensity(): Density {
  return localStorage.getItem(STORAGE_KEY) === "compact" ? "compact" : "comfortable";
}

function subscribe(listener: () => void) {
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) listener();
  };
  listeners.add(listener);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function persistDensity(density: Density) {
  localStorage.setItem(STORAGE_KEY, density);
  apply(density);
  listeners.forEach((listener) => listener());
}

export function DensityToggle() {
  const density = useSyncExternalStore<Density>(subscribe, getDensity, () => "comfortable");

  function toggle() {
    const next: Density = density === "compact" ? "comfortable" : "compact";
    persistDensity(next);
  }

  const compact = density === "compact";
  const Icon = compact ? Rows2 : Rows3;
  const label = compact ? "Densité compacte" : "Densité confort";

  return (
    <button
      type="button"
      onClick={toggle}
      title={label}
      aria-label={label}
      data-ui-control
      className="flex h-9 w-9 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
    >
      <Icon size={16} aria-hidden="true" />
    </button>
  );
}
