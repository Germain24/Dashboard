"use client";

import { Sparkles } from "lucide-react";
import type { SkincareProduct, SkincareToday } from "@/lib/skincare";
import { useSkincareToday, useToRepurchase } from "@/lib/queries/skincare";
import { EmptyState } from "@/components/ui/empty-state";
import { ModuleHeader } from "@/components/layout";
import { Freshness } from "@/components/Freshness";

export function Skincare() {
  const todayQ = useSkincareToday();
  const repurchaseQ = useToRepurchase();
  const today: SkincareToday | null = todayQ.data ?? null;
  const repurchase: SkincareProduct[] = repurchaseQ.data ?? [];
  const loading = todayQ.isLoading || repurchaseQ.isLoading;
  const error = todayQ.isError || repurchaseQ.isError
    ? (((todayQ.error ?? repurchaseQ.error) as Error)?.message ?? "Erreur de chargement")
    : null;
  const updatedAt = todayQ.dataUpdatedAt || null;

  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-[var(--destructive)]">⚠ {error}</div>;

  const renderRoutine = (label: string, items: SkincareProduct[]) => (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold tracking-tight">{label}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucun produit.</p>
      ) : (
        <ol className="space-y-1.5">
          {items.map((p, i) => (
            <li
              key={p.id}
              className="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm card-hover"
            >
              <span className="text-xs text-[var(--muted-foreground)] w-5">{i + 1}.</span>
              <span className="font-medium">{p.nom}</span>
              <span className="text-xs text-[var(--muted-foreground)]">· {p.type}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Skincare"
        subtitle="Routines & produits"
        actions={<Freshness updatedAt={updatedAt} />}
      />

      {(today?.AM?.length ?? 0) === 0 && (today?.PM?.length ?? 0) === 0 ? (
        <div className="p-6 animate-fade-in-up">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Aucun produit skincare"
            description="Ajoute tes produits (nettoyant, sérum, SPF…) pour générer tes routines matin et soir."
          />
        </div>
      ) : (
        <div className="p-6 grid gap-6 sm:grid-cols-2 animate-fade-in-up">
          {renderRoutine("Routine matin (AM)", today?.AM ?? [])}
          {renderRoutine("Routine soir (PM)", today?.PM ?? [])}
        </div>
      )}

      {(today?.due?.length ?? 0) > 0 && (
        <div className="px-6 pb-2">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-sm font-semibold mb-2">Dû aujourd&apos;hui</h2>
            <ul className="text-sm text-[var(--muted-foreground)] flex flex-wrap gap-2">
              {today!.due.map((p) => (
                <li key={p.id} className="rounded-md bg-[var(--muted)] px-2 py-0.5">
                  {p.nom}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {repurchase.length > 0 && (
        <div className="px-6 pb-6">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <h2 className="text-sm font-semibold mb-2">À racheter</h2>
            <ul className="text-sm text-[var(--muted-foreground)] space-y-1">
              {repurchase.map((p) => (
                <li key={p.id}>• {p.nom}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
