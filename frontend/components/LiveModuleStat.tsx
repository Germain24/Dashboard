"use client";

/**
 * Mini-stat live affichée dans une ModuleCard de la page d'accueil.
 *
 * Récupère côté client un résumé léger pour les modules qui exposent un
 * endpoint bon marché. Les modules sans stat connue n'affichent rien
 * (dégradation propre). Point d'extension : ajouter une entrée à FETCHERS.
 */

import { useEffect, useState } from "react";

type Fetcher = () => Promise<string | null>;

async function getJson<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

const FETCHERS: Record<string, Fetcher> = {
  finance: async () => {
    const m = await getJson<{ pl_pct?: number; valeur?: number }>("/api/finance/portfolio/perf");
    if (!m || m.valeur == null) return null;
    const pl = m.pl_pct != null ? ` · ${m.pl_pct >= 0 ? "+" : ""}${m.pl_pct.toFixed(1)}%` : "";
    return `${Math.round(m.valeur).toLocaleString("fr-CA")} €${pl}`;
  },
  habitudes: async () => {
    const rows = await getJson<Array<{ entry: unknown | null }>>("/api/habitudes/today");
    if (!rows) return null;
    const done = rows.filter((r) => r.entry).length;
    return `${done}/${rows.length} aujourd'hui`;
  },
  skincare: async () => {
    const t = await getJson<{ due?: unknown[]; AM?: unknown[]; PM?: unknown[] }>("/api/skincare/today");
    if (!t) return null;
    const due = t.due?.length ?? 0;
    return due > 0 ? `${due} dû aujourd'hui` : `${(t.AM?.length ?? 0) + (t.PM?.length ?? 0)} produits`;
  },
  livres: async () => {
    const s = await getJson<Array<{ statut?: string }>>("/api/livres/books?statut=en_cours");
    if (!s) return null;
    return `${s.length} en cours`;
  },
};

export function LiveModuleStat({ slug }: { slug: string }) {
  const [stat, setStat] = useState<string | null>(null);

  useEffect(() => {
    const fetcher = FETCHERS[slug];
    if (!fetcher) return;
    let cancelled = false;
    fetcher().then((s) => {
      if (!cancelled) setStat(s);
    });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (!stat) return null;
  return (
    <span className="mt-1 inline-block text-xs font-medium tabular-nums text-[var(--ring)]">
      {stat}
    </span>
  );
}
