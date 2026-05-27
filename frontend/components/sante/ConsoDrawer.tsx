"use client";

import { useEffect, useState } from "react";
import { type PlanItem } from "@/lib/sante";

type Props = {
  open: boolean;
  onClose: () => void;
  planItems: PlanItem[];           // ce que dit le plan
  initialConsumed?: Record<string, number> | null;  // ce que tu as déjà déclaré (g/aliment)
  onSave: (consumedG: Record<string, number>) => Promise<void>;
};

/**
 * Drawer permettant d'éditer la quantité (en grammes) réellement consommée
 * pour chaque aliment du plan. La compensation J-1 utilise ces valeurs.
 *
 * Pratique : par défaut, on pré-remplit avec le plan généré. L'utilisateur
 * ajuste les lignes qu'il a changées.
 */
export function ConsoDrawer({ open, onClose, planItems, initialConsumed, onSave }: Props) {
  // Map nom → grammes. Si initialConsumed est null, on pré-remplit avec le plan.
  const [grams, setGrams] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const next: Record<string, number> = {};
    // Pré-remplit avec le plan
    for (const it of planItems) {
      next[it.aliment] = Math.round(it.quantite_g);
    }
    // initialConsumed est stocké sous forme `<aliment>_g` côté backend (cf. ConvertedConsumed)
    // ou bien sous forme `Calories: X` (totaux agrégés). On distingue : si la clé matche
    // un aliment, on prend cette quantité ; sinon on ignore (les totaux nutritifs ne se
    // ré-éditent pas ici, ils sont recalculés à partir des grammes).
    if (initialConsumed) {
      for (const [k, v] of Object.entries(initialConsumed)) {
        if (k.endsWith("_g")) {
          const aliment = k.slice(0, -2);
          next[aliment] = Math.round(v);
        }
      }
    }
    setGrams(next);
    setErr(null);
  }, [open, planItems, initialConsumed]);

  if (!open) return null;

  const setQty = (aliment: string, qty: number) => {
    setGrams((g) => ({ ...g, [aliment]: Math.max(0, qty) }));
  };

  const handleSave = async () => {
    setSaving(true);
    setErr(null);
    try {
      // On garde toutes les lignes, même celles à 0 (pour distinguer "rien mangé" de "non saisi").
      await onSave(grams);
      onClose();
    } catch (e: any) {
      setErr(e?.message ?? "Erreur enregistrement");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <aside className="w-full max-w-md bg-[var(--background)] border-l border-[var(--border)] p-4 overflow-y-auto">
        <header className="flex items-center justify-between mb-3">
          <h2 className="font-medium">Ce que j'ai mangé aujourd'hui</h2>
          <button onClick={onClose} className="rounded border border-[var(--border)] px-2 py-1 text-xs hover:bg-[var(--accent)]">
            ✕
          </button>
        </header>
        <p className="text-xs text-[var(--muted-foreground)] mb-3">
          Pré-rempli avec le plan généré. Modifie les lignes qui ne correspondent pas, puis enregistre.
          Ces valeurs alimentent la compensation J-1 du lendemain.
        </p>

        <div className="space-y-2">
          {planItems.map((it) => (
            <div key={it.aliment} className="flex items-center gap-2 text-sm">
              <span className="flex-1 truncate" title={it.aliment}>{it.aliment}</span>
              <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
                plan : {it.quantite_g.toFixed(0)}g
              </span>
              <input
                type="number"
                min={0}
                step={10}
                value={grams[it.aliment] ?? 0}
                onChange={(e) => setQty(it.aliment, parseFloat(e.target.value) || 0)}
                className="w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm text-right"
              />
              <span className="text-xs">g</span>
            </div>
          ))}
        </div>

        {planItems.length === 0 && (
          <div className="text-sm text-[var(--muted-foreground)]">Aucun item dans le plan.</div>
        )}

        {err && <div className="mt-3 text-sm text-[var(--destructive)]">⚠ {err}</div>}

        <div className="mt-4 flex gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-[var(--success)] text-[var(--success-foreground)] px-3 py-1.5 text-sm font-semibold disabled:opacity-50"
          >
            {saving ? "…" : "💾 Enregistrer ma conso"}
          </button>
          <button
            onClick={onClose}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--accent)]"
          >
            Annuler
          </button>
        </div>
      </aside>
    </div>
  );
}
