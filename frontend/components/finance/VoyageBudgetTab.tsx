"use client";

/** Budget de voyage finançable en chaînant les cartes de crédit actives —
 *  une carte à la fois, vidée puis remboursée avant l'échéance (0% d'intérêt
 *  via le délai de grâce), jamais deux cartes ouvertes en parallèle. */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { financeApi } from "@/lib/finance";

const cad = (n: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(n);

export function VoyageBudgetTab() {
  const [ordre, setOrdre] = useState<"desc" | "asc">("desc");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["finance", "credit", "voyage-budget", ordre],
    queryFn: () => financeApi.creditVoyageBudget(ordre),
  });

  if (isError)
    return <div className="text-sm text-[var(--warning-foreground)]">Impossible de calculer le budget.</div>;
  if (isLoading || !data) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--muted-foreground)]">
        Chaque carte active est utilisée seule, un mois complet, vidée jusqu'à sa limite puis remboursée
        intégralement avant l'échéance — 0% d'intérêt via le délai de grâce. On enchaîne à la carte suivante
        le mois d'après, jamais deux en même temps.
      </p>

      <div className="flex items-center gap-2">
        <span className="text-xs text-[var(--muted-foreground)]">Ordre :</span>
        <button
          onClick={() => setOrdre("desc")}
          className={`rounded px-2 py-1 text-xs ${ordre === "desc" ? "bg-[var(--ring)] text-white" : "border border-[var(--border)]"}`}
        >
          Plus grosse limite d'abord
        </button>
        <button
          onClick={() => setOrdre("asc")}
          className={`rounded px-2 py-1 text-xs ${ordre === "asc" ? "bg-[var(--ring)] text-white" : "border border-[var(--border)]"}`}
        >
          Plus petite limite d'abord
        </button>
      </div>

      {data.mois_total === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune carte active — ajoute des comptes dans "Feuille de route".</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Budget total finançable" value={cad(data.budget_total)} strong />
            <Stat label="Durée" value={`${data.mois_total} mois`} strong />
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--muted-foreground)]">
                <th className="pb-1">Mois</th>
                <th className="pb-1">Carte</th>
                <th className="pb-1 text-right">Budget</th>
              </tr>
            </thead>
            <tbody>
              {data.mois.map((m) => (
                <tr key={m.mois} className="border-t border-[var(--glass-border)]">
                  <td className="py-1.5">Mois {m.mois}</td>
                  <td className="py-1.5">{m.institution} — {m.produit}</td>
                  <td className="py-1.5 text-right tabular-nums">{cad(m.budget)}</td>
                </tr>
              ))}
              <tr className="border-t border-[var(--glass-border)] font-semibold">
                <td className="py-1.5" colSpan={2}>Total</td>
                <td className="py-1.5 text-right tabular-nums">{cad(data.budget_total)}</td>
              </tr>
            </tbody>
          </table>

          <Link
            href={`/voyage?budget=${Math.round(data.budget_total)}&jours=${data.mois_total * 30}`}
            className="inline-block rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] hover:opacity-90"
          >
            Trouver des itinéraires avec ce budget →
          </Link>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-3">
      <div className="text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`tabular-nums ${strong ? "text-xl font-semibold" : "text-base"}`}>{value}</div>
    </div>
  );
}
