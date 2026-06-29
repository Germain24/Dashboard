"use client";

import { useMemo, useState } from "react";
import type { QualityRow } from "@/lib/musique";
import { useQuality, useSetQobuzAvailable } from "@/lib/queries/musique";

const STATUS_LABEL: Record<QualityRow["status"], string> = {
  owned: "✅ Déjà en qualité",
  to_buy: "🛒 À acheter",
  unavailable: "⛔ Indispo Qobuz",
  unknown: "❔ À vérifier",
};

const FILTERS: [string, string][] = [
  ["all", "Tous"], ["to_buy", "À acheter"], ["unknown", "À vérifier"], ["owned", "Déjà en qualité"],
];

export function Qualite() {
  const rows: QualityRow[] = useQuality().data ?? [];
  const setQobuz = useSetQobuzAvailable();
  const [filter, setFilter] = useState<string>("all");

  const counts = useMemo(() => {
    const c = { to_buy: 0, unknown: 0, owned: 0, unavailable: 0 };
    rows.forEach((r) => { c[r.status] += 1; });
    return c;
  }, [rows]);

  const shown = filter === "all" ? rows : rows.filter((r) => r.status === filter);

  const setValue = (id: number, v: string) =>
    setQobuz.mutate({ id, available: v === "oui" ? true : v === "non" ? false : null });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-sm">
        <span>🛒 À acheter : <b>{counts.to_buy}</b></span>
        <span>❔ À vérifier : <b>{counts.unknown}</b></span>
        <span>✅ En qualité : <b>{counts.owned}</b></span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map(([id, label]) => (
          <button key={id} onClick={() => setFilter(id)}
            className={`text-xs px-2.5 py-1 rounded-full border ${filter === id
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>{label}</button>
        ))}
      </div>

      <div className="space-y-1">
        {shown.map((r) => (
          <div key={r.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate">{r.title} — <span className="text-[var(--muted-foreground)]">{r.artist}</span></div>
              <div className="text-xs text-[var(--muted-foreground)]">{r.quality_label} · {STATUS_LABEL[r.status]}</div>
            </div>
            <select
              value={r.qobuz_available === true ? "oui" : r.qobuz_available === false ? "non" : "?"}
              onChange={(e) => setValue(r.id, e.target.value)}
              className="text-xs rounded border border-[var(--border)] bg-transparent px-1.5 py-1">
              <option value="?">Qobuz ?</option>
              <option value="oui">Achetable</option>
              <option value="non">Indispo</option>
            </select>
          </div>
        ))}
        {shown.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Aucun morceau — lance un scan.</p>}
      </div>
    </div>
  );
}
