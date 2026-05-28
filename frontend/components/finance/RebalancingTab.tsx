"use client";

import { useEffect, useState, useCallback } from "react";
import { financeApi, type RebalancingDiff } from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";

function fmt(n: number, dec = 2) {
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function ActionBadge({ a }: { a: string }) {
  const map: Record<string, "success" | "destructive" | "outline"> = {
    ACHETER: "success", VENDRE: "destructive", CONSERVER: "outline",
  };
  return <Badge variant={map[a] ?? "outline"}>{a}</Badge>;
}

export function RebalancingTab() {
  const [diff, setDiff] = useState<RebalancingDiff | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setDiff(await financeApi.rebalancing()); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur réseau"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Spinner label="Calcul rebalancing..." />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;
  if (!diff) return (
    <EmptyState
      title="Aucune analyse Buffett disponible"
      description="Lancez une analyse Buffett mensuelle pour obtenir les recommandations de rebalancing."
    />
  );

  return (
    <div className="space-y-4">
      {/* Header disclaimer */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--warning-muted)] bg-[var(--warning-muted)]
        p-3 text-sm text-[var(--warning-foreground)]">
        ⚠ Affichage uniquement — aucune exécution de trades. Effectuez les ordres vous-même chez votre broker.
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Valeur totale", value: `${fmt(diff.valeur_totale_eur)} €`, color: "" },
          { label: "À acheter", value: `${diff.n_acheter} ligne(s)`, color: "text-[var(--success)]" },
          { label: "À vendre", value: `${diff.n_vendre} ligne(s)`, color: "text-[var(--destructive)]" },
        ].map(k => (
          <div key={k.label}
            className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3">
            <p className="text-xs text-[var(--muted-foreground)]">{k.label}</p>
            <p className={`text-base font-semibold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        Basé sur le run Buffett du {diff.run_date} (run_id={diff.run_id})
      </p>

      {/* Diff table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
              <th className="pb-1 pr-3">Ticker</th>
              <th className="pb-1 pr-3">Nom</th>
              <th className="pb-1 pr-3 text-right">Actuel %</th>
              <th className="pb-1 pr-3 text-right">Cible %</th>
              <th className="pb-1 pr-3 text-right">Actuel €</th>
              <th className="pb-1 pr-3 text-right">Cible €</th>
              <th className="pb-1 pr-3 text-right">Delta €</th>
              <th className="pb-1">Action</th>
            </tr>
          </thead>
          <tbody>
            {diff.lignes.map(l => (
              <tr key={l.ticker}
                className="border-b border-[var(--border)] hover:bg-[var(--muted)]">
                <td className="py-1.5 pr-3 font-mono text-xs">{l.ticker}</td>
                <td className="py-1.5 pr-3 text-xs text-[var(--muted-foreground)]">
                  {l.nom.length > 20 ? l.nom.slice(0, 18) + "…" : l.nom}
                </td>
                <td className="py-1.5 pr-3 text-right text-xs">{fmt(l.allocation_actuelle_pct)}%</td>
                <td className="py-1.5 pr-3 text-right text-xs">{fmt(l.allocation_cible_pct)}%</td>
                <td className="py-1.5 pr-3 text-right">{fmt(l.valeur_actuelle_eur)} €</td>
                <td className="py-1.5 pr-3 text-right">{fmt(l.valeur_cible_eur)} €</td>
                <td className={`py-1.5 pr-3 text-right font-medium ${
                  l.delta_eur > 0 ? "text-[var(--success)]"
                  : l.delta_eur < 0 ? "text-[var(--destructive)]" : ""}`}>
                  {l.delta_eur > 0 ? "+" : ""}{fmt(l.delta_eur)} €
                </td>
                <td className="py-1.5"><ActionBadge a={l.action} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
