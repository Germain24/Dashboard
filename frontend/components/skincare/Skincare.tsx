"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { skincareApi, type SkincareProduct, type SkincareToday } from "@/lib/skincare";

export function Skincare() {
  const [today, setToday] = useState<SkincareToday | null>(null);
  const [repurchase, setRepurchase] = useState<SkincareProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([skincareApi.today(), skincareApi.toRepurchase()])
      .then(([t, r]) => {
        setToday(t);
        setRepurchase(r);
      })
      .catch((e) => setError(e?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false));
  }, []);

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
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 shrink-0" />
          <h1 className="text-xl font-semibold tracking-tight">Skincare</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Routines &amp; produits</p>
      </div>

      <div className="p-6 grid gap-6 sm:grid-cols-2 animate-fade-in-up">
        {renderRoutine("Routine matin (AM)", today?.AM ?? [])}
        {renderRoutine("Routine soir (PM)", today?.PM ?? [])}
      </div>

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
