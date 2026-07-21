"use client";

import { Suspense, useState } from "react";
import { LieuxTab } from "./LieuxTab";
import { PlanifierTab } from "./PlanifierTab";
import { PlanifierAutoTab } from "./PlanifierAutoTab";
import { VoyagesConfirmesTab } from "./VoyagesConfirmesTab";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { useSuggererLieux } from "@/lib/queries/voyage";

const MAX_CANDIDATS = 25;

export function Voyage() {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [ancrageIata, setAncrageIata] = useState("YUL");
  const suggererMut = useSuggererLieux();

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < MAX_CANDIDATS) next.add(id);
      return next;
    });
  };

  // Au lieu de cocher un par un dans ~1300 lieux : propose automatiquement les
  // plus proches (vol d'oiseau) d'un aéroport-pivot — typiquement le premier
  // arrêt du voyage — pour couvrir une région entière (ex. Amérique du Sud
  // depuis un hub colombien) sans payer un aller-retour Montréal par lieu.
  const suggerer = () => {
    suggererMut.mutate(
      { departIata: ancrageIata, limit: MAX_CANDIDATS },
      { onSuccess: (lieux) => setSelected(new Set(lieux.map((l) => l.id))) },
    );
  };

  return (
    <div className="space-y-6">
      <Suspense fallback={<p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>}>
        <PlanifierAutoTab />
      </Suspense>

      <CollapsibleSection title="Sélection manuelle (avancé)" defaultOpen={false}>
        <div className="space-y-6">
          <div className="flex flex-wrap items-end gap-2 rounded-lg border border-[var(--border)] p-3">
            <label className="text-sm">
              Aéroport-pivot (ex. premier arrêt prévu)
              <input
                value={ancrageIata}
                onChange={(e) => setAncrageIata(e.target.value.toUpperCase())}
                className="mt-1 block w-32 rounded border border-[var(--border)] p-1.5"
              />
            </label>
            <button
              onClick={suggerer}
              disabled={suggererMut.isPending}
              className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
            >
              {suggererMut.isPending ? "Recherche…" : `Suggérer les ${MAX_CANDIDATS} lieux les plus proches`}
            </button>
            {suggererMut.isError && (
              <span className="text-sm text-[var(--destructive)]">
                {suggererMut.error?.message ?? "Erreur"}
              </span>
            )}
          </div>
          <LieuxTab selected={selected} onToggle={toggle} />
          <PlanifierTab candidats={[...selected]} onConfirmed={() => setSelected(new Set())} />
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Voyages confirmés — checklist & budget" defaultOpen={true}>
        <VoyagesConfirmesTab />
      </CollapsibleSection>
    </div>
  );
}
