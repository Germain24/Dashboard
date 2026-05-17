"use client";

import type { TenueHistory } from "@/lib/garderobe";

export function HistoriqueTab({ history }: { history: TenueHistory[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">Aucun historique pour le moment.</p>;
  }
  return (
    <div className="space-y-3">
      {history.map((entry) => (
        <div key={entry.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
          <div className="text-sm font-medium">📅 {formatDate(entry.date)}</div>
          <div className="text-xs text-[var(--muted-foreground)] mt-1">
            {Object.values(entry.tenue).filter(Boolean).join(", ")}
          </div>
          {entry.note ? <div className="text-xs italic mt-1">« {entry.note} »</div> : null}
        </div>
      ))}
    </div>
  );
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}
