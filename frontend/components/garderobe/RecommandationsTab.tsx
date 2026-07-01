"use client";

import type { ConseilsAchat } from "@/lib/garderobe";

export function RecommandationsTab({ recs }: { recs: ConseilsAchat }) {
  const { total_tenues, conseils } = recs;
  const maxGain = conseils.length ? conseils[0].debloque : 1;

  return (
    <div className="space-y-3">
      <div className="text-sm text-[var(--muted-foreground)]">
        Tu as actuellement{" "}
        <span className="font-semibold text-[var(--foreground)]">{total_tenues}</span> tenue
        {total_tenues > 1 ? "s" : ""} possible{total_tenues > 1 ? "s" : ""}.
      </div>

      {conseils.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">
          Ajoute d'abord des hauts, pantalons et chaussures pour débloquer des tenues.
        </p>
      ) : (
        conseils.map((c, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center gap-2 mb-1">
              <div className="text-sm font-semibold">
                Ajouter {c.slot} {c.couleur}
              </div>
              <span className="ml-auto text-xs font-mono text-[var(--success,#16a34a)]">
                +{c.debloque} tenue{c.debloque > 1 ? "s" : ""}
              </span>
            </div>
            <div className="mt-2 h-1.5 bg-[var(--muted)] rounded overflow-hidden">
              <div
                className="h-full bg-[var(--ring)]"
                style={{ width: `${(c.debloque / maxGain) * 100}%` }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  );
}
