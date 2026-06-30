"use client";

import { type Emplacement } from "@/lib/garderobe";

/** Une ligne d'emplacement : nom de marque + barre 0→100 (Q/P → Qualité Max). */
export function ObjectifBar({ slot, excedent = false }: { slot: Emplacement; excedent?: boolean }) {
  const empty = slot.statut === "vide";
  const pos = slot.position ?? 0;

  let barClass = "bg-[var(--primary)]";
  if (excedent) barClass = "bg-[var(--destructive)]";
  else if (empty) barClass = "bg-transparent";
  else if (slot.hors_echelle) barClass = "bg-[var(--muted-foreground)]"; // marque hors échelle = gris

  return (
    <div className={`flex items-center gap-3 ${excedent ? "text-[var(--destructive)]" : ""}`}>
      <span className="w-32 shrink-0 truncate text-sm">
        {empty ? <span className="text-[var(--muted-foreground)]">—</span> : slot.marque ?? "?"}
      </span>
      <div className="relative h-2 flex-1 rounded-full bg-[var(--muted)]">
        {!empty && (
          <div
            className={`absolute top-0 left-0 h-2 rounded-full ${barClass}`}
            style={{ width: `${Math.max(pos, 2)}%` }}
          />
        )}
      </div>
    </div>
  );
}
