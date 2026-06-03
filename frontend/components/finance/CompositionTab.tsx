"use client";

import { useEffect, useState, useCallback } from "react";
import { financeApi, type PositionOut, type TreemapNode } from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { TitreDetailModal } from "./TitreDetailModal";

type GroupBy = "secteur" | "pays" | "devise";

function fmt(n?: number) {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function PerfBadge({ v }: { v?: number }) {
  if (v == null) return <span className="text-xs text-[var(--muted-foreground)]">—</span>;
  const variant = v >= 0 ? "success" : "destructive";
  return <Badge variant={variant} className="text-xs">{v >= 0 ? "+" : ""}{fmt(v)}%</Badge>;
}

function FlatTreemap({ nodes }: { nodes: TreemapNode[] }) {
  const roots = nodes.filter(n => n.parent === "");
  const children = nodes.filter(n => n.parent !== "");
  const total = roots.reduce((s, n) => s + n.valeur, 0) || 1;

  return (
    <div className="space-y-3">
      {roots.map(root => {
        const kids = children.filter(c => c.parent === root.id);
        const pct = (root.valeur / total * 100).toFixed(1);
        return (
          <div key={root.id}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium">{root.label}</span>
              <span className="text-xs text-[var(--muted-foreground)]">{pct}% — {fmt(root.valeur)} €</span>
            </div>
            <div className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden">
              <div className="h-full rounded-full bg-[var(--ring)]"
                style={{ width: `${pct}%` }} />
            </div>
            {kids.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {kids.map(k => (
                  <span key={k.id}
                    className="text-xs px-2 py-0.5 rounded-full bg-[var(--muted)] text-[var(--muted-foreground)]">
                    {k.label} {(k.valeur / total * 100).toFixed(1)}%
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function CompositionTab() {
  const [positions, setPositions] = useState<PositionOut[]>([]);
  const [treemap, setTreemap] = useState<TreemapNode[]>([]);
  const [groupBy, setGroupBy] = useState<GroupBy>("secteur");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detailTicker, setDetailTicker] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [pos, tree] = await Promise.all([
        financeApi.portfolio(), financeApi.treemap(groupBy),
      ]);
      setPositions(pos); setTreemap(tree);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur réseau");
    } finally { setLoading(false); }
  }, [groupBy]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Spinner label="Chargement composition..." />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;
  if (!positions.length) return (
    <EmptyState title="Aucune position" description="Importez des transactions pour voir votre composition." />
  );

  return (
    <div className="space-y-5">
      {/* Group-by selector */}
      <div className="flex gap-2">
        {(["secteur", "pays", "devise"] as GroupBy[]).map(g => (
          <button key={g} onClick={() => setGroupBy(g)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              groupBy === g
                ? "bg-[var(--ring)] text-white border-[var(--ring)]"
                : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--ring)]"
            }`}>
            {g.charAt(0).toUpperCase() + g.slice(1)}
          </button>
        ))}
      </div>

      {/* Treemap bars */}
      <FlatTreemap nodes={treemap} />

      {/* Positions table */}
      <div>
        <h2 className="text-base font-semibold mb-2">Détail des positions</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                <th className="pb-1 pr-3">Ticker</th>
                <th className="pb-1 pr-3">Broker</th>
                <th className="pb-1 pr-3 text-right">Qté</th>
                <th className="pb-1 pr-3 text-right">PRU</th>
                <th className="pb-1 pr-3 text-right">Cours</th>
                <th className="pb-1 pr-3 text-right">Valeur</th>
                <th className="pb-1 text-right">+/-</th>
              </tr>
            </thead>
            <tbody>
              {positions.map(p => (
                <tr
                  key={`${p.ticker}-${p.broker ?? ""}`}
                  onClick={() => setDetailTicker(p.ticker)}
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)] cursor-pointer"
                  title={`Détail ${p.ticker}`}
                >
                  <td className="py-1.5 pr-3 font-mono text-xs">{p.ticker}</td>
                  <td className="py-1.5 pr-3 text-xs text-[var(--muted-foreground)]">{p.broker ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-right">{fmt(p.quantite)}</td>
                  <td className="py-1.5 pr-3 text-right">{p.pmu ? `${fmt(p.pmu)} €` : "—"}</td>
                  <td className="py-1.5 pr-3 text-right">{p.prix_actuel ? `${fmt(p.prix_actuel)} €` : "—"}</td>
                  <td className="py-1.5 pr-3 text-right font-medium">{p.valeur_actuelle ? `${fmt(p.valeur_actuelle)} €` : "—"}</td>
                  <td className="py-1.5 text-right"><PerfBadge v={p.pl_pct} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {detailTicker && (
        <TitreDetailModal ticker={detailTicker} onClose={() => setDetailTicker(null)} />
      )}
    </div>
  );
}
