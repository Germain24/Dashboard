"use client";

/** Page d'erreur globale (App Router) — capture les erreurs de rendu des routes. */

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-lg font-semibold">Une erreur est survenue</h2>
      <p className="max-w-md text-sm text-[var(--muted-foreground)]">
        {error.message || "Quelque chose s'est mal passé lors du chargement de cette section."}
      </p>
      <button
        onClick={reset}
        className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
      >
        Réessayer
      </button>
    </div>
  );
}
