"use client";

/**
 * Toggle de thème clair / sombre / système, persistant (localStorage).
 *
 * Applique l'attribut `data-theme` sur <html> :
 *   - "light" / "dark" : force le thème (prime sur la préférence OS via le CSS).
 *   - absent ("system") : suit `prefers-color-scheme`.
 *
 * Le script anti-flash dans layout.tsx applique le choix avant le paint.
 */

import { useEffect, useState } from "react";
import { Moon, Sun, Monitor } from "lucide-react";

type Theme = "light" | "dark" | "system";
const STORAGE_KEY = "mc-theme";
const ORDER: Theme[] = ["system", "light", "dark"];

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    setTheme(stored);
    setMounted(true);
  }, []);

  function cycle() {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    apply(next);
  }

  // Évite un mismatch d'hydratation : on n'affiche l'icône réelle qu'après montage.
  const Icon = !mounted ? Monitor : theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  const label =
    theme === "light" ? "Thème clair" : theme === "dark" ? "Thème sombre" : "Thème système";

  return (
    <button
      type="button"
      onClick={cycle}
      title={label}
      aria-label={label}
      className="flex items-center justify-center h-8 w-8 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
    >
      <Icon size={16} />
    </button>
  );
}
