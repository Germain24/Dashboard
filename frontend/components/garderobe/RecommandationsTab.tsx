"use client";

import type { Recommendation } from "@/lib/garderobe";

export function RecommandationsTab({ recs }: { recs: Recommendation[] }) {
  if (recs.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">Aucune recommandation.</p>;
  }
  return (
    <div className="space-y-3">
      {recs.map((r, i) => (
        <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="flex items-center gap-2 mb-1">
            <div className="text-sm font-semibold">{r.nom}</div>
            <span className="ml-auto text-[10px] rounded bg-[var(--muted)] px-2 py-0.5 text-[var(--muted-foreground)]">
              {r.type}
            </span>
            <span className="text-xs font-mono">{r.potentiel}/100</span>
          </div>
          <div className="text-xs text-[var(--muted-foreground)]">{r.raison}</div>
          <div className="mt-2 h-1.5 bg-[var(--muted)] rounded overflow-hidden">
            <div className="h-full bg-[var(--ring)]" style={{ width: `${r.potentiel}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
