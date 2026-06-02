"use client";

/**
 * Indicateur de fraîcheur des données : « mis à jour il y a 3 min ».
 * Se met à jour tout seul. Passer le timestamp de la dernière récupération.
 */

import { useEffect, useState } from "react";

function relative(from: number): string {
  const s = Math.max(0, Math.round((Date.now() - from) / 1000));
  if (s < 10) return "à l'instant";
  if (s < 60) return `il y a ${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `il y a ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.round(h / 24);
  return `il y a ${d} j`;
}

export function Freshness({ updatedAt, className }: { updatedAt: number | null; className?: string }) {
  const [, tick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => tick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  if (!updatedAt) return null;
  return (
    <span className={className ?? "text-xs text-[var(--muted-foreground)]"}>
      mis à jour {relative(updatedAt)}
    </span>
  );
}
