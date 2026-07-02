"use client";

import { RefreshCw } from "lucide-react";
import { useLieuxVoyage, useSyncVoyage } from "@/lib/queries/voyage";

export function LieuxTab({ selected, onToggle }: {
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  const lieuxQ = useLieuxVoyage();
  const syncMut = useSyncVoyage();

  if (lieuxQ.isLoading) {
    return <div className="p-2 text-[var(--muted-foreground)]">Chargement…</div>;
  }
  if (lieuxQ.isError || !lieuxQ.data) {
    return <div className="p-2 text-[var(--destructive)]">⚠ Impossible de charger la liste.</div>;
  }

  const aVisiter = lieuxQ.data.filter((l) => !l.visite);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-[var(--muted-foreground)]">
          {aVisiter.length} lieux à visiter · {selected.size} sélectionné(s) pour la planification
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending}
          className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
          Re-synchroniser l'Excel
        </button>
      </div>
      {syncMut.data && syncMut.data.incomplets.length > 0 && (
        <div className="rounded-lg border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
          ⚠ {syncMut.data.incomplets.length} lieu(x) incomplet(s) (aéroport ou jours manquants) :{" "}
          {syncMut.data.incomplets.join(", ")}
        </div>
      )}
      <div className="space-y-1">
        {aVisiter.map((l) => (
          <label
            key={l.id}
            className={`flex items-center gap-3 rounded-lg border border-[var(--border)] p-2 text-sm ${
              l.complet ? "cursor-pointer hover:bg-[var(--muted)]" : "opacity-50"
            }`}
          >
            <input
              type="checkbox"
              disabled={!l.complet}
              checked={selected.has(l.id)}
              onChange={() => onToggle(l.id)}
            />
            <span className="flex-1">{l.nom}</span>
            <span className="text-[var(--muted-foreground)]">{l.ville ?? l.pays ?? ""}</span>
            {!l.complet && <span className="text-xs text-[var(--destructive)]">incomplet</span>}
          </label>
        ))}
      </div>
    </div>
  );
}
