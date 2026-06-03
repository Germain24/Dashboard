"use client";

import { useEffect, useState, useCallback } from "react";
import { financeApi, type PositionOut, type TreemapNode, type TransactionCreate } from "@/lib/finance";
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
  const [divers, setDivers] = useState<{ secteurs: { secteur: string; poids_pct: number; surpondere: boolean }[]; n_surponderes: number; seuil_pct: number } | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const [quick, setQuick] = useState<{ ticker: string; type: "ACHAT" | "VENTE"; quantite: number; prix: number }>(
    { ticker: "", type: "ACHAT", quantite: 0, prix: 0 },
  );
  const [quickSaving, setQuickSaving] = useState(false);

  const submitQuick = async () => {
    if (!quick.ticker || quick.quantite <= 0) return;
    setQuickSaving(true);
    try {
      const tx: TransactionCreate = {
        ticker: quick.ticker.toUpperCase(),
        type_transaction: quick.type,
        date_transaction: new Date().toISOString().slice(0, 10),
        quantite: quick.quantite,
        prix_unitaire: quick.prix,
        devise: "EUR",
      };
      await financeApi.createTransaction(tx);
      setQuick({ ticker: "", type: "ACHAT", quantite: 0, prix: 0 });
      setQuickOpen(false);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur saisie");
    } finally {
      setQuickSaving(false);
    }
  };

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [pos, tree] = await Promise.all([
        financeApi.portfolio(), financeApi.treemap(groupBy),
      ]);
      financeApi.diversification().then(setDivers).catch(() => {});
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
      {/* Alerte de surpondération sectorielle */}
      {divers && divers.n_surponderes > 0 && (
        <div className="rounded-xl border border-[var(--warning,#d97706)]/30 bg-[color-mix(in_srgb,var(--warning,#d97706)_8%,transparent)] px-4 py-2.5 text-sm">
          <span className="text-[var(--warning,#d97706)] font-medium">⚠ Surpondération sectorielle</span>
          <span className="text-[var(--muted-foreground)]">
            {" "}— {divers.secteurs.filter(s => s.surpondere).map(s => `${s.secteur} (${s.poids_pct.toFixed(0)}%)`).join(", ")}
            {" "}dépasse{divers.n_surponderes > 1 ? "nt" : ""} {divers.seuil_pct.toFixed(0)}%.
          </span>
        </div>
      )}

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
        <button
          onClick={() => setQuickOpen((o) => !o)}
          className="ml-auto text-xs px-3 py-1.5 rounded-full border border-[var(--border)] text-[var(--muted-foreground)] hover:border-[var(--ring)] hover:text-[var(--foreground)]"
        >
          + Saisie rapide
        </button>
      </div>

      {/* Saisie rapide d'une transaction depuis le portefeuille */}
      {quickOpen && (
        <div className="flex flex-wrap items-end gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
          <input
            placeholder="Ticker" value={quick.ticker}
            onChange={(e) => setQuick({ ...quick, ticker: e.target.value })}
            className="w-28 px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)] uppercase"
          />
          <select
            value={quick.type}
            onChange={(e) => setQuick({ ...quick, type: e.target.value as "ACHAT" | "VENTE" })}
            className="px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
          >
            <option value="ACHAT">Achat</option>
            <option value="VENTE">Vente</option>
          </select>
          <input
            type="number" placeholder="Qté" value={quick.quantite || ""}
            onChange={(e) => setQuick({ ...quick, quantite: parseFloat(e.target.value) || 0 })}
            className="w-24 px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
          />
          <input
            type="number" placeholder="Prix €" value={quick.prix || ""}
            onChange={(e) => setQuick({ ...quick, prix: parseFloat(e.target.value) || 0 })}
            className="w-24 px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
          />
          <button
            onClick={submitQuick} disabled={quickSaving || !quick.ticker || quick.quantite <= 0}
            className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {quickSaving ? "…" : "Enregistrer"}
          </button>
        </div>
      )}

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
