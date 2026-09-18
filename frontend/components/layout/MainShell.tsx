"use client";

/**
 * Enveloppe du contenu principal (desktop).
 *
 * - Accueil (le Deck) : plein écran, scroll interne, aucun padding.
 * - Pages module : on réserve un espace en bas pour que le Dock flottant ne
 *   masque jamais la dernière ligne de contenu.
 * - Pose `data-module` sur <body> : le lavis d'accent du module (globals.css)
 *   vit sur body::before, hors de portée d'un sélecteur depuis <main>.
 */

import { useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Server } from "lucide-react";
import { cn } from "@/lib/utils";

export function MainShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const onHome = pathname === "/";
  const [backendOffline, setBackendOffline] = useState(false);

  const handleStatus = useCallback((e: Event) => {
    setBackendOffline((e as CustomEvent).detail === "offline");
  }, []);

  useEffect(() => {
    const segment = pathname.split("/")[1] ?? "";
    if (segment) document.body.dataset.module = segment;
    else delete document.body.dataset.module;
  }, [pathname]);

  useEffect(() => {
    window.addEventListener("mc:backend-status", handleStatus);
    return () => window.removeEventListener("mc:backend-status", handleStatus);
  }, [handleStatus]);

  return (
    <>
      {backendOffline && (
        <div className="fixed inset-x-0 top-12 z-[var(--z-toast)] flex items-center justify-center gap-2 bg-[var(--destructive-muted)] px-4 py-2 text-sm font-medium text-[var(--destructive-foreground)] md:top-0">
          <Server className="h-3.5 w-3.5" aria-hidden="true" />
          Backend inaccessible — certaines données peuvent être périmées.
        </div>
      )}
      <main
        id="main-content"
        tabIndex={-1}
        className={cn(
          "min-w-0 flex-1 focus:outline-none",
          !onHome && "pb-24 md:pb-28",
          backendOffline && !onHome && "pt-9",
        )}
      >
        {children}
      </main>
    </>
  );
}
