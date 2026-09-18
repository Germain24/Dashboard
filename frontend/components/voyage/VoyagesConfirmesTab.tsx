"use client";

/** Voyages confirmés : checklist de préparation + budget par étape. */

import { useVoyagesConfirmes } from "@/lib/queries/voyage";
import { VoyagesConfirmedContent } from "@/components/voyage/VoyagesConfirmesParts";

export function VoyagesConfirmesTab() {
  const query = useVoyagesConfirmes();
  if (query.isError) return <p className="text-sm text-[var(--destructive)]">{query.error?.message ?? "Erreur de chargement des voyages"}</p>;
  if (query.isLoading) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  return <VoyagesConfirmedContent voyages={query.data} />;
}
