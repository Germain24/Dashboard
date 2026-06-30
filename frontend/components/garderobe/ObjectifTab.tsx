"use client";

import { RefreshCw, Sparkles } from "lucide-react";
import { useObjectif, useSyncObjectif, useAutoRattacher } from "@/lib/queries/garderobe";
import { ObjectifBar } from "./ObjectifBar";

export function ObjectifTab() {
  const objectifQ = useObjectif();
  const syncMut = useSyncObjectif();
  const autoMut = useAutoRattacher();

  if (objectifQ.isLoading) {
    return <div className="p-2 text-[var(--muted-foreground)]">Chargement de l'objectif…</div>;
  }
  if (objectifQ.isError || !objectifQ.data) {
    return <div className="p-2 text-[var(--destructive)]">⚠ Impossible de charger l'objectif.</div>;
  }

  const { total_emplacements, total_remplis, non_rattaches, non_rattaches_items, types } = objectifQ.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="text-sm text-[var(--muted-foreground)]">
          <span className="font-semibold text-[var(--foreground)]">
            {total_remplis}/{total_emplacements}
          </span>{" "}
          emplacements remplis
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => autoMut.mutate()}
            disabled={autoMut.isPending}
            className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <Sparkles className={`h-4 w-4 ${autoMut.isPending ? "animate-pulse" : ""}`} />
            Rattacher automatiquement
          </button>
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending}
            className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
            Re-synchroniser l'Excel
          </button>
        </div>
      </div>

      {non_rattaches > 0 && (
        <div className="rounded-lg border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
          ⚠ {non_rattaches} pièce{non_rattaches > 1 ? "s" : ""} non rattachée{non_rattaches > 1 ? "s" : ""} :{" "}
          {non_rattaches_items.map((p) => `${p.vetement_nom} (${p.type_objectif ?? "?"})`).join(", ")}
        </div>
      )}

      {types.map((t) => (
        <div key={t.nom} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="font-semibold">{t.nom}</h3>
            <span className="text-xs text-[var(--muted-foreground)]">
              {t.rempli} / {t.quantite_objectif}
            </span>
          </div>
          <div className="space-y-2">
            {t.emplacements.map((slot, i) => (
              <ObjectifBar key={`${t.nom}-${i}`} slot={slot} />
            ))}
            {t.excedent.map((slot, i) => (
              <ObjectifBar key={`${t.nom}-x${i}`} slot={slot} excedent />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
