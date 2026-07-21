"use client";

/** Carte compacte « Indépendance financière » (#268) : taux d'épargne et années
 *  restantes, calculés côté serveur à partir du budget et du patrimoine net.
 *  Présentationnel — les données viennent de `useFire`. */

import type { FireReport } from "@/lib/budget";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

const fmtPct = (v: number) => `${v.toFixed(1).replace(".", ",")} %`;

export function FireCard({ fire }: { fire?: FireReport }) {
  if (!fire) return null;

  const annees = fire.annees_restantes;
  const horizon =
    fire.atteint ? "Atteinte ✓" : annees === null ? "Hors d'atteinte" : `${annees.toFixed(1).replace(".", ",")} ans`;
  const detail = fire.atteint
    ? `Ton patrimoine couvre déjà ${fire.taux_retrait_pct.toFixed(0)} % de retrait annuel`
    : annees === null
      ? `Objectif non atteint sous ${fire.horizon_max} ans au rythme d'épargne actuel`
      : `≈ ${fire.annee_cible} · objectif ${eur(fire.objectif_fi)}`;

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-xs font-semibold">Indépendance financière</h3>
        <span className="text-xs text-[var(--muted-foreground)]">
          règle des {fire.taux_retrait_pct.toFixed(0)} % · rendement réel {fire.rendement_reel_pct.toFixed(0)} % · {fire.mois_analyses} mois
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-[var(--muted-foreground)]">Taux d&apos;épargne</div>
          <div
            className="text-xl font-semibold tabular-nums"
            style={fire.taux_epargne_pct < 0 ? { color: "var(--warning-foreground)" } : undefined}
          >
            {fmtPct(fire.taux_epargne_pct)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--muted-foreground)]">Années restantes</div>
          <div className="text-xl font-semibold tabular-nums">{horizon}</div>
        </div>
      </div>

      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min(100, Math.max(0, fire.progression_pct))}%`,
            background: fire.atteint ? "var(--success)" : "var(--ring)",
          }}
        />
      </div>
      <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">{detail}</p>
    </div>
  );
}
