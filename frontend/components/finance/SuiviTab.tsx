"use client";

import { useEffect, useState, useCallback } from "react";
import {
  financeApi, type SnapshotOut, type PerfMetrics,
  type HistoryPoint, type BenchmarkOut,
} from "@/lib/finance";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProjectionTool } from "./ProjectionTool";

// Couleur de série du benchmark CW8 (demande explicite : orange)
const CW8_COLOR = "#f97316";

const formatCAD = (v: number) =>
  new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD" }).format(v);

const formatPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)} %`;

function fmt(n?: number | null, dec = 2) {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function kEur(n: number) {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k€`;
  return `${Math.round(n)} €`;
}

function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="skeleton-shimmer h-3 w-20 mb-3" />
      <div className="skeleton-shimmer h-6 w-28" />
    </div>
  );
}

function PerfBadge({ v }: { v?: number | null }) {
  if (v == null) return <span className="text-xs text-[var(--muted-foreground)]">—</span>;
  return <Badge variant={v >= 0 ? "success" : "destructive"}>{v >= 0 ? "+" : ""}{fmt(v)}%</Badge>;
}

interface ChartProps {
  history: HistoryPoint[];
  cw8Serie: { date: string; valeur: number }[];
}

function PortfolioChart({ history, cw8Serie }: ChartProps) {
  if (history.length < 2) {
    return (
      <p className="text-xs text-[var(--muted-foreground)] py-10 text-center">
        Pas encore assez de données — les snapshots s'accumulent chaque jour automatiquement.
      </p>
    );
  }

  const W = 800, H = 260, PL = 56, PR = 56, PT = 14, PB = 30;
  const iW = W - PL - PR, iH = H - PT - PB;

  const vVals = history.map(d => d.valeur);
  const iVals = history.map(d => d.investit);
  const allVals = [...vVals, ...iVals];

  // CW8 = simulation d'un portefeuille 100 % CW8.PA (mêmes apports), déjà en € et
  // alignée sur les dates des snapshots par le backend. On l'aligne par date (report
  // de la dernière valeur connue pour les jours sans point).
  let cw8Norm: number[] = [];
  if (cw8Serie.length > 1) {
    const byDate = new Map(cw8Serie.map(c => [c.date, c.valeur]));
    let last: number | null = null;
    cw8Norm = history.map(h => {
      const v = byDate.get(h.date);
      if (v != null) last = v;
      return last ?? cw8Serie[0].valeur;
    });
    allVals.push(...cw8Norm);
  }

  const minV = Math.min(...allVals) * 0.99;
  const maxV = Math.max(...allVals) * 1.01;
  const range = maxV - minV || 1;

  const toX = (i: number, total: number) => PL + (i / (total - 1)) * iW;
  const toY = (v: number) => PT + (1 - (v - minV) / range) * iH;
  const line = (vals: number[]) => vals.map((v, i) => `${toX(i, vals.length)},${toY(v)}`).join(" ");

  const ticks = [minV, minV + range * 0.25, minV + range * 0.5, minV + range * 0.75, maxV];
  const xIdx = [0, Math.floor(history.length / 3), Math.floor((2 * history.length) / 3), history.length - 1];

  const isUp = vVals[vVals.length - 1] >= vVals[0];
  const valColor = isUp ? "var(--success)" : "var(--destructive)";
  const area = `${line(vVals)} ${toX(vVals.length - 1, vVals.length)},${toY(minV)} ${toX(0, vVals.length)},${toY(minV)}`;

  const lastX = toX(vVals.length - 1, vVals.length);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: "auto" }}>
        <defs>
          <linearGradient id="valFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={valColor} stopOpacity="0.18" />
            <stop offset="100%" stopColor={valColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Grille + axe Y (€) */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PL} x2={W - PR} y1={toY(t)} y2={toY(t)}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="2 3" />
            <text x={PL - 8} y={toY(t) + 3} textAnchor="end" fontSize="10" fill="var(--muted-foreground)">
              {kEur(t)}
            </text>
          </g>
        ))}

        {/* Axe X (dates) */}
        {xIdx.map(i => (
          <text key={i} x={toX(i, history.length)} y={H - 8} textAnchor="middle"
            fontSize="10" fill="var(--muted-foreground)">
            {history[i]?.date?.slice(0, 7) ?? ""}
          </text>
        ))}

        {/* Aire sous la valeur */}
        <polygon points={area} fill="url(#valFill)" />

        {/* Benchmark CW8 (orange, tireté) */}
        {cw8Norm.length > 1 && (
          <polyline fill="none" stroke={CW8_COLOR} strokeWidth="2"
            strokeDasharray="5 3" points={line(cw8Norm)} />
        )}

        {/* Investi (gris, tireté) */}
        <polyline fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5"
          strokeDasharray="4 4" points={line(iVals)} />

        {/* Valeur portefeuille (plein) */}
        <polyline fill="none" stroke={valColor} strokeWidth="2.5" points={line(vVals)} />
        <circle cx={lastX} cy={toY(vVals[vVals.length - 1])} r="3.5" fill={valColor} />
      </svg>

      {/* Légende */}
      <div className="flex flex-wrap gap-4 text-xs text-[var(--muted-foreground)] mt-2 px-1">
        <span className="flex items-center gap-1.5">
          <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke={valColor} strokeWidth="2.5" /></svg>
          Valeur portefeuille
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeDasharray="4 4" /></svg>
          Investi
        </span>
        {cw8Norm.length > 1 && (
          <span className="flex items-center gap-1.5">
            <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke={CW8_COLOR} strokeWidth="2" strokeDasharray="5 3" /></svg>
            CW8.PA (100% simulé)
          </span>
        )}
      </div>
    </div>
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
  const [syncing, setSyncing] = useState(false);
  const [currency, setCurrency] = useState<"EUR" | "USD" | "CAD">("EUR");
  const [rate, setRate] = useState(1);

  useEffect(() => {
    if (currency === "EUR") { setRate(1); return; }
    let cancelled = false;
    financeApi.fx("EUR", currency)
      .then((r) => !cancelled && setRate(r.rates[currency] || 1))
      .catch(() => !cancelled && setRate(1));
    return () => { cancelled = true; };
  }, [currency]);

  const money = useCallback(
    (v: number) => new Intl.NumberFormat("fr-CA", { style: "currency", currency }).format(v * rate),
    [currency, rate],
  );

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [s, p, h, b] = await Promise.all([
        financeApi.snapshot(), financeApi.perf(),
        financeApi.history(10000), financeApi.benchmarks(),  // tout l'historique
      ]);
      setSnap(s); setPerf(p); setHistory(h); setBenchmarks(b);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur réseau");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load().then(async () => {
      try {
        const today = new Date().toISOString().split("T")[0];
        const s = await financeApi.snapshot();
        if (!s || s.date < today) {
          await financeApi.snapshotAuto();
          load();
        }
      } catch { /* silencieux */ }
    });
  }, [load]);

  const handleSnapshot = async () => {
    setSnapping(true);
    try { await financeApi.snapshotCreate(); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur snapshot"); }
    finally { setSnapping(false); }
  };

  // Recharge l'historique depuis Historique_portefeuille.xlsx (l'Excel = la source)
  const handleSyncExcel = async () => {
    setSyncing(true); setError(null);
    try { await financeApi.historySyncExcel(); await load(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Erreur rechargement Excel"); }
    finally { setSyncing(false); }
  };

  const valeur = perf?.valeur ?? 0;
  const investit = perf?.investit ?? 0;
  const plTotal = perf?.pl_total ?? 0;
  const plPct = perf?.pl_pct ?? 0;
  const cw8 = benchmarks.find(b => b.nom === "CW8" || b.ticker === "CW8.PA");

  if (error) return <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>;

  return (
    <div className="space-y-4">
      {/* Sélecteur de devise (conversion au taux du jour) */}
      <div className="flex items-center justify-end gap-1.5">
        <span className="text-xs text-[var(--muted-foreground)]">Devise</span>
        {(["EUR", "USD", "CAD"] as const).map((c) => (
          <button
            key={c}
            onClick={() => setCurrency(c)}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
              currency === c
                ? "bg-[var(--accent)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* KPIs — skeleton pendant le loading, vraies valeurs ensuite */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
        {loading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            {[
              { label: "Valeur totale", value: money(valeur), color: "" },
              { label: "Investi",       value: money(investit), color: "" },
              {
                label: "+/- latente",
                value: money(plTotal),
                color: plTotal >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]",
              },
              {
                label: "Rendement",
                value: formatPct(plPct),
                color: plPct >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]",
              },
            ].map(stat => (
              <div
                key={stat.label}
                className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up"
              >
                <p className="text-xs text-[var(--muted-foreground)] uppercase tracking-wider font-medium mb-1">
                  {stat.label}
                </p>
                <p className={`text-xl font-bold font-mono ${stat.color}`}>{stat.value}</p>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Rendement annualisé (TWR) vs benchmark */}
      {!loading && perf?.twr_annualise_pct != null && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span className="text-[var(--muted-foreground)]">Rendement annualisé (TWR)</span>
          <span className={`font-mono font-semibold ${perf.twr_annualise_pct >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}>
            {perf.twr_annualise_pct >= 0 ? "+" : ""}{formatPct(perf.twr_annualise_pct)}
          </span>
          {cw8?.perf_1a_pct != null && (
            <span className="text-[var(--muted-foreground)]">
              vs <strong className="text-[var(--foreground)]">CW8</strong> (1 an){" "}
              <span className="font-mono">{cw8.perf_1a_pct >= 0 ? "+" : ""}{formatPct(cw8.perf_1a_pct)}</span>
            </span>
          )}
          <span className="text-xs text-[var(--muted-foreground)]">· hors effet des apports</span>
        </div>
      )}

      {/* Chart */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <p className="text-sm font-semibold">Évolution du portefeuille</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              {loading ? "Chargement…" : `${history.length} snapshots · vs 100 % CW8.PA (mêmes apports)`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={handleSyncExcel} disabled={syncing || loading}
              title="Relit Historique_portefeuille.xlsx (Date, Valeur, Investit)">
              {syncing ? "..." : "↻ Recharger l'Excel"}
            </Button>
            <Button size="sm" variant="secondary" onClick={handleSnapshot} disabled={snapping || loading}>
              {snapping ? "..." : "Snapshot maintenant"}
            </Button>
          </div>
        </div>
        {loading ? (
          <div className="skeleton-shimmer h-[260px] w-full rounded-lg" />
        ) : (
          <PortfolioChart history={history} cw8Serie={cw8?.serie ?? []} />
        )}
      </div>

      {snap && !loading && (
        <p className="text-xs text-[var(--muted-foreground)]">
          Dernier snapshot : {snap.date} · {fmt(snap.valeur)} € · investi {fmt(snap.investit)} €
        </p>
      )}

      {/* Benchmarks */}
      {!loading && benchmarks.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-sm font-semibold">Benchmarks</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="pb-1 pr-4">Indice</th>
                  <th className="pb-1 pr-4">6 mois</th>
                  <th className="pb-1 pr-4">MTD</th>
                  <th className="pb-1">1 an</th>
                </tr>
              </thead>
              <tbody>
                {benchmarks.map(b => (
                  <tr key={b.ticker ?? b.nom} className="border-b border-[var(--border)]">
                    <td className="py-1.5 pr-4 font-medium"
                      style={(b.nom === "CW8" || b.ticker === "CW8.PA") ? { color: CW8_COLOR } : {}}>
                      {b.nom}{(b.nom === "CW8" || b.ticker === "CW8.PA") ? " (CW8.PA)" : ""}
                    </td>
                    <td className="py-1.5 pr-4"><PerfBadge v={b.perf_6m_pct} /></td>
                    <td className="py-1.5 pr-4"><PerfBadge v={b.perf_mtd_pct} /></td>
                    <td className="py-1.5"><PerfBadge v={b.perf_1a_pct} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <ProjectionTool />
    </div>
  );
}
