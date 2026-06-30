"use client";

import { useState } from "react";
import { type Emplacement } from "@/lib/garderobe";

/** Une ligne d'emplacement : vignette + nom de marque + barre 0→100 (Q/P → Qualité Max). */
export function ObjectifBar({ slot, excedent = false }: { slot: Emplacement; excedent?: boolean }) {
  const empty = slot.statut === "vide";
  const pos = slot.position ?? 0;
  const [imgFailed, setImgFailed] = useState(false);

  let barClass = "bg-[var(--primary)]";
  if (excedent) barClass = "bg-[var(--destructive)]";
  else if (empty) barClass = "bg-transparent";
  else if (slot.hors_echelle) barClass = "bg-[var(--muted-foreground)]"; // marque hors échelle = gris

  return (
    <div className={`flex items-center gap-3 ${excedent ? "text-[var(--destructive)]" : ""}`}>
      <div className="h-6 w-6 shrink-0 flex items-center justify-center">
        {!empty && slot.image && !imgFailed && (
          <img
            src={`/garderobe/assets/${slot.image}`}
            alt={slot.vetement_nom ?? ""}
            onError={() => setImgFailed(true)}
            style={{ imageRendering: "pixelated" }}
            className="max-h-6 max-w-6 object-contain"
          />
        )}
      </div>
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
