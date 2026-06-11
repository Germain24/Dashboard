"use client";

import type { CorrelationsOut } from "@/lib/journal";
import { useJournalCorrelations } from "@/lib/queries/journal";

const LABEL: Record<string, string> = {
  sommeil: "Sommeil", sport: "Sport", poids: "Poids", depenses: "Dépenses",
};

export function CorrelationsPanel() {
  const data: CorrelationsOut | null = useJournalCorrelations(90).data ?? null;
  if (!data) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  const humeur = data.correlations.filter((c) => c.source === "humeur");

  return (
    <div className="space-y-3">
      <p className="text-xs text-[var(--muted-foreground)]">
        Humeur vs… (90 j) · {data.caveat}
      </p>
      <div className="grid grid-cols-2 gap-2">
        {humeur.map((c) => (
          <div key={c.cible} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <div className="text-sm font-medium">{LABEL[c.cible] ?? c.cible}</div>
            {c.r == null ? (
              <div className="text-xs text-[var(--muted-foreground)]">Pas assez de données ({c.n} j)</div>
            ) : (
              <div className="text-xs">
                <span className="font-mono">r = {c.r}</span> · corrélation {c.force} {c.signe} · {c.n} j
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
