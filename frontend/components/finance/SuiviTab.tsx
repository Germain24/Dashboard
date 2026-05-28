"use client";

import { useEffect, useState, useCallback } from "react";
import { financeApi, type SnapshotOut, type PerfMetrics, type HistoryPoint, type BenchmarkOut } from "@/lib/finance";
import { Spinner } from "@/components/ui/spinner";
import { ChartFrame } from "@/components/ui/chart-frame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function fmt(n?: number, dec = 2) {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function PerfBadge({ v }: { v?: number }) {
  if (v == null) return <span className="text-xs text-[var(--muted-foreground)]">—</span>;
  const variant = v >= 0 ? "success" : "destructive";
  return <Badge variant={variant}>{v >= 0 ? "+" : ""}{fmt(v)}%</Badge>;
}

function MiniChart({ data }: { data: HistoryPoint[] }) {
  if (!data.length) return null;
  const vals = data.map(d => d.valeur_totale);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const W = 400, H = 80, PAD = 4;
  const pts = data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2);
    const y = PAD + (1 - (d.valeur_totale - min) / range) * (H - PAD * 2);
    return `${x},${y}`;
  }).join(" ");
  const isUp = vals[vals.length - 1] >= vals[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-20">
      <polyline fill="none" stroke={isUp ? "var(--success)" : "var(--destructive)"}
        strokeWidth="1.5" points={pts} />
    </svg>
  );
}

export function SuiviTab() {
  const [snap, setSnap] = useState<SnapshotOut | null>(null);
  const [perf, setPerf] = useState<PerfMetrics | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [snapping, setSnapping] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [s, p, h, b] = await Promise.all([
        financeApi.snapshot(), financeApi.perf(),
        financeApi.history(365), financeApi.benchmarks(),
      ]);
      setSnap(s); setPerf(p); setHistory(h); setBenchmarks(b);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur réseau");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSnapshot = async () => {
    setSnapping(true);
    try { await financeApi.snapshotCreate(); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur snapshot"); }
    finally { setSnapping(false); }
  };

  if (loading) return <Spinner label="Chargement portefeuille..." />;
  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Valeur totale", value: `${fmt(perf?.valeur_totale)} €` },
          { label: "Investi", value: `${fmt(perf?.montant_investi)} €` },
          { label: "+/- latente", value: `${fmt(perf?.plus_value_latente)} €`, pct: perf?.plus_value_pct },
          { label: "Max drawdown", value: perf?.max_drawdown_pct != null ? `${fmt(perf.max_drawdown_pct)}%` : "—" },
        ].map(k => (
          <div key={k.label} className="rounded-[var(--radius-lg)] border border-[var(--border)] p-3 space-y-1">
            <p className="text-xs text-[var(--muted-foreground)]">{k.label}</p>
            <p className="text-base font-semibold">{k.value}</p>
            {"pct" in k && <PerfBadge v={k.pct} />}
          </div>
        ))}
      </div>

      {/* Chart */}
      <ChartFrame title={`Évolution valeur (${history.length} jours)`}
        action={<Button size="sm" variant="secondary" onClick={handleSnapshot}
          disabled={snapping}>{snapping ? "..." : "Snapshot maintenant"}</Button>}>
        <MiniChart data={history} />
      </ChartFrame>

      {/* Last snapshot */}
      {snap && (
        <p className="text-xs text-[var(--muted-foreground)]">
          Dernier snapshot : {snap.date} — {snap.nb_lignes} ligne(s)
        </p>
      )}

      {/* Benchmarks */}
      {benchmarks.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-base font-semibold">Benchmarks</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="pb-1 pr-4">Indice</th>
                  <th className="pb-1 pr-4">1 mois</th>
                  <th className="pb-1 pr-4">3 mois</th>
                  <th className="pb-1 pr-4">YTD</th>
                  <th className="pb-1">1 an</th>
                </tr>
              </thead>
              <tbody>
                {benchmarks.map(b => (
                  <tr key={b.ticker} className="border-b border-[var(--border)]">
                    <td className="py-1.5 pr-4 font-medium">{b.nom}</td>
                    <td className="py-1.5 pr-4"><PerfBadge v={b.perf_1m_pct} /></td>
                    <td className="py-1.5 pr-4"><PerfBadge v={b.perf_3m_pct} /></td>
                    <td className="py-1.5 pr-4"><PerfBadge v={b.perf_ytd_pct} /></td>
                    <td className="py-1.5"><PerfBadge v={b.perf_1a_pct} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
