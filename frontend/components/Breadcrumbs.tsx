"use client";

/**
 * Fil d'Ariane (Accueil / Module) + mise à jour du <title> par module.
 *
 * Approche DRY : dérive le segment courant du pathname et résout le libellé
 * via MODULES, plutôt que de dupliquer des metadata dans 13 pages. Ne s'affiche
 * pas sur l'accueil.
 */

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { MODULES } from "@/lib/modules";

const EXTRA_LABELS: Record<string, string> = {
  jobs: "Jobs",
};

function labelFor(slug: string): string {
  const m = MODULES.find((x) => x.slug === slug);
  return m?.label ?? EXTRA_LABELS[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1);
}

export function Breadcrumbs() {
  const pathname = usePathname() ?? "/";
  const segment = pathname.split("/").filter(Boolean)[0];
  const label = segment ? labelFor(segment) : null;

  useEffect(() => {
    document.title = label ? `${label} · Mission Control` : "Mission Control";
  }, [label]);

  if (!label) return null;

  return (
    <nav
      aria-label="Fil d'Ariane"
      className="flex items-center gap-1.5 px-6 pt-4 text-xs text-[var(--muted-foreground)]"
    >
      <Link href="/" className="hover:text-[var(--foreground)] transition-colors">
        Accueil
      </Link>
      <ChevronRight size={12} aria-hidden="true" />
      <span className="text-[var(--foreground)] font-medium">{label}</span>
    </nav>
  );
}
