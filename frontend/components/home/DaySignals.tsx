"use client";

/**
 * « État du jour » — rangée compacte de signaux transverses, en remplacement de
 * l'ancienne grille de 12 cartes identiques. Chaque puce n'apparaît que si son
 * endpoint répond (dégradation propre) ; si aucun ne répond (backend hors
 * ligne), la section entière disparaît. Endpoints éprouvés (cf. ex-LiveModuleStat).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { moduleForSlug } from "@/lib/modules";
import { Skeleton } from "@/components/ui/skeleton";

type Signal = {
  slug: string;
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "success" | "destructive";
};

async function getJson<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

type Loaded = Omit<Signal, "slug" | "label">;

const LOADERS: { slug: string; label: string; load: () => Promise<Loaded | null> }[] = [
  {
    slug: "habitudes",
    label: "Habitudes (semaine)",
    load: async () => {
      const w = await getJson<{ taux: number; done: number; total: number }>("/api/habitudes/weekly-completion");
      if (!w) return null;
      return {
        value: `${w.taux}%`,
        delta: `${w.done}/${w.total}`,
        deltaTone: w.taux >= 80 ? "success" : w.taux < 40 ? "destructive" : undefined,
      };
    },
  },
  {
    slug: "skincare",
    label: "Skincare",
    load: async () => {
      const t = await getJson<{ due?: unknown[] }>("/api/skincare/today");
      if (!t) return null;
      const due = t.due?.length ?? 0;
      return { value: due > 0 ? `${due} dû` : "à jour" };
    },
  },
  {
    slug: "finance",
    label: "Portefeuille",
    load: async () => {
      const m = await getJson<{ pl_pct?: number; valeur?: number }>("/api/finance/portfolio/perf");
      if (!m || m.valeur == null) return null;
      const value = `${Math.round(m.valeur).toLocaleString("fr-CA")} €`;
      if (m.pl_pct == null) return { value };
      const sign = m.pl_pct >= 0 ? "+" : "";
      return {
        value,
        delta: `${sign}${m.pl_pct.toFixed(1)} %`,
        deltaTone: m.pl_pct >= 0 ? "success" : "destructive",
      };
    },
  },
  {
    slug: "livres",
    label: "Lecture",
    load: async () => {
      const s = await getJson<Array<unknown>>("/api/livres/books?statut=en_cours");
      if (!s) return null;
      return { value: s.length > 0 ? `${s.length} en cours` : "aucun" };
    },
  },
];

export function DaySignals() {
  const [signals, setSignals] = useState<Signal[] | null>(null); // null = chargement

  useEffect(() => {
    let active = true;
    // Chaque signal renvoie toujours une puce : sa vraie valeur si l'endpoint
    // répond, sinon « — » (ex. backend hors ligne). La rangée ne disparaît
    // jamais silencieusement ; l'état hors ligne reste lisible (cf. HealthBadge).
    void Promise.all(
      LOADERS.map(async (l) => {
        const r = await l.load();
        return { slug: l.slug, label: l.label, ...(r ?? { value: "—" }) };
      }),
    ).then((res) => {
      if (active) setSignals(res);
    });
    return () => {
      active = false;
    };
  }, []);

  if (signals === null) {
    return (
      <Section>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {LOADERS.map((l) => (
            <Skeleton key={l.slug} className="h-14" />
          ))}
        </div>
      </Section>
    );
  }

  return (
    <Section>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {signals.map((s) => (
          <SignalChip key={s.slug} signal={s} />
        ))}
      </div>
    </Section>
  );
}

function Section({ children }: { children: React.ReactNode }) {
  return (
    <section className="mt-8 animate-fade-in" aria-labelledby="signals-heading">
      <h2 id="signals-heading" className="mb-3 text-sm font-medium text-[var(--foreground)]">
        État du jour
      </h2>
      {children}
    </section>
  );
}

function SignalChip({ signal }: { signal: Signal }) {
  const Icon = moduleForSlug(signal.slug)?.icon;
  const toneClass =
    signal.deltaTone === "success"
      ? "text-[var(--success)]"
      : signal.deltaTone === "destructive"
        ? "text-[var(--destructive)]"
        : "text-[var(--muted-foreground)]";

  return (
    <Link
      href={`/${signal.slug}`}
      className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2.5 transition-colors hover:border-[color-mix(in_srgb,var(--ring)_30%,transparent)]"
    >
      {Icon && (
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--muted)]">
          <Icon className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
        </span>
      )}
      <span className="min-w-0">
        <span className="block truncate text-xs text-[var(--muted-foreground)]">{signal.label}</span>
        <span className="flex items-baseline gap-1.5">
          <span className="truncate text-sm font-medium tabular-nums text-[var(--foreground)]">
            {signal.value}
          </span>
          {signal.delta && (
            <span className={`shrink-0 text-xs font-medium tabular-nums ${toneClass}`}>
              {signal.delta}
            </span>
          )}
        </span>
      </span>
    </Link>
  );
}
