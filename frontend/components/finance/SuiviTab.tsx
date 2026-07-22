"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Camera, RefreshCw, Trash2 } from "lucide-react";
import { financeApi, type HistoryPoint, type PriceAlertDirection } from "@/lib/finance";
import {
  annualizedCapitalReturn,
  capitalBreakIndexes,
  moneyWeightedAnnualizedReturn,
} from "@/lib/finance-chart";
import {
  useAlertsStatus,
  useBenchmarks,
  useCreateAlert,
  useDeleteAlert,
  useHistory,
  usePerf,
  useRisk,
  useSnapshot,
} from "@/lib/queries/finance";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProjectionTool } from "./ProjectionTool";
import { CashTaxPanel } from "./CashTaxPanel";
import { RiskMetricsRow } from "./RiskMetricsRow";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { StaggerGroup, StaggerItem } from "@/lib/motion/Stagger";

// Couleur de série du benchmark CW8 — token thémé, identique au chart et au
// tableau (cellule "text-[var(--warning)]" ci-dessous) dans les deux thèmes.
const CW8_COLOR = "var(--warning)";

const formatPct = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)} %`;

function fmt(n?: number | null, dec = 2) {
  if (n == null) return "—";
  return n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function kEur(n: number) {
  if (Math.abs(n) >= 1000)
    return `${(n / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} k€`;
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
  return (
    <Badge variant={v >= 0 ? "success" : "destructive"}>
      {v >= 0 ? "+" : ""}
      {fmt(v)}%
    </Badge>
  );
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

  const W = 800,
    H = 260,
    PL = 56,
    PR = 56,
    PT = 14,
    PB = 30;
  const iW = W - PL - PR,
    iH = H - PT - PB;

  const vVals = history.map((d) => d.valeur);
  const iVals = history.map((d) => d.investit);
  const allVals = [...vVals, ...iVals];

  // CW8 = simulation d'un portefeuille 100 % CW8.PA (mêmes apports), déjà en € et
  // alignée sur les dates des snapshots par le backend. On l'aligne par date (report
  // de la dernière valeur connue pour les jours sans point).
  let cw8Norm: number[] = [];
  if (cw8Serie.length > 1) {
    const byDate = new Map(cw8Serie.map((c) => [c.date, c.valeur]));
    let last: number | null = null;
    cw8Norm = history.map((h) => {
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
  const line = (vals: number[], start = 0) =>
    vals.map((v, i) => `${toX(start + i, history.length)},${toY(v)}`).join(" ");
  const breakIndexes = capitalBreakIndexes(history);
  const splitSeries = (vals: number[]) => {
    const starts = [0, ...breakIndexes];
    return starts.map((start, segmentIndex) => {
      const end = breakIndexes[segmentIndex] ?? vals.length;
      return { start, values: vals.slice(start, end) };
    });
  };
  const valueSegments = splitSeries(vVals);
  const investedSegments = splitSeries(iVals);
  const cw8Segments = splitSeries(cw8Norm);

  const ticks = [minV, minV + range * 0.25, minV + range * 0.5, minV + range * 0.75, maxV];
  const xIdx = [
    0,
    Math.floor(history.length / 3),
    Math.floor((2 * history.length) / 3),
    history.length - 1,
  ];

  const isUp = vVals[vVals.length - 1] >= vVals[0];
  const valColor = isUp ? "var(--success)" : "var(--destructive)";
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
            <line
              x1={PL}
              x2={W - PR}
              y1={toY(t)}
              y2={toY(t)}
              stroke="var(--border)"
              strokeWidth="1"
              strokeDasharray="2 3"
            />
            <text
              x={PL - 8}
              y={toY(t) + 3}
              textAnchor="end"
              fontSize="10"
              fill="var(--muted-foreground)"
            >
              {kEur(t)}
            </text>
          </g>
        ))}

        {/* Axe X (dates) */}
        {xIdx.map((i) => (
          <text
            key={i}
            x={toX(i, history.length)}
            y={H - 8}
            textAnchor="middle"
            fontSize="10"
            fill="var(--muted-foreground)"
          >
            {history[i]?.date?.slice(0, 7) ?? ""}
          </text>
        ))}

        {/* Aire sous la valeur */}
        {valueSegments.map(({ start, values }) => {
          if (values.length < 2) return null;
          const end = start + values.length - 1;
          const area = `${line(values, start)} ${toX(end, history.length)},${toY(minV)} ${toX(start, history.length)},${toY(minV)}`;
          return <polygon key={start} points={area} fill="url(#valFill)" />;
        })}

        {/* Benchmark CW8 (orange, tireté) */}
        {cw8Norm.length > 1 &&
          cw8Segments.map(({ start, values }) =>
            values.length > 1 ? (
              <polyline
                key={start}
                fill="none"
                stroke={CW8_COLOR}
                strokeWidth="2"
                strokeDasharray="5 3"
                points={line(values, start)}
              />
            ) : null,
          )}

        {/* Investi (gris, tireté) */}
        {investedSegments.map(({ start, values }) =>
          values.length > 1 ? (
            <polyline
              key={start}
              fill="none"
              stroke="var(--muted-foreground)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              points={line(values, start)}
            />
          ) : null,
        )}

        {/* Valeur portefeuille (plein) */}
        {valueSegments.map(({ start, values }) =>
          values.length > 1 ? (
            <polyline
              key={start}
              fill="none"
              stroke={valColor}
              strokeWidth="2.5"
              points={line(values, start)}
            />
          ) : null,
        )}
        <circle cx={lastX} cy={toY(vVals[vVals.length - 1])} r="3.5" fill={valColor} />
      </svg>

      {/* Légende */}
      <div className="flex flex-wrap gap-4 text-xs text-[var(--muted-foreground)] mt-2 px-1">
        <span className="flex items-center gap-1.5">
          <svg width="22" height="6">
            <line x1="0" y1="3" x2="22" y2="3" stroke={valColor} strokeWidth="2.5" />
          </svg>
          Valeur portefeuille
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="22" height="6">
            <line
              x1="0"
              y1="3"
              x2="22"
              y2="3"
              stroke="var(--muted-foreground)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          </svg>
          Investi
        </span>
        {cw8Norm.length > 1 && (
          <span className="flex items-center gap-1.5">
            <svg width="22" height="6">
              <line
                x1="0"
                y1="3"
                x2="22"
                y2="3"
                stroke={CW8_COLOR}
                strokeWidth="2"
                strokeDasharray="5 3"
              />
            </svg>
            CW8.PA (100% simulé)
          </span>
        )}
        {breakIndexes.length > 0 && (
          <span
            className="flex items-center gap-1.5 text-[var(--warning-foreground)]"
            title="La courbe est interrompue lors des changements de capital supérieurs à 50 %."
          >
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {breakIndexes.length} variation{breakIndexes.length > 1 ? "s" : ""} majeure
            {breakIndexes.length > 1 ? "s" : ""} du capital
          </span>
        )}
      </div>
    </div>
  );
}

function MarketAlertsCard() {
  const alertsQuery = useAlertsStatus();
  const createAlert = useCreateAlert();
  const deleteAlert = useDeleteAlert();
  const alerts = alertsQuery.data ?? [];

  const [ticker, setTicker] = useState("");
  const [seuil, setSeuil] = useState("");
  const [direction, setDirection] = useState<PriceAlertDirection>("au_dessus");
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const seuilNum = Number(seuil);
    if (!ticker.trim() || !Number.isFinite(seuilNum) || seuilNum <= 0) {
      setFormError("Ticker et seuil (> 0) requis.");
      return;
    }
    try {
      await createAlert.mutateAsync({
        ticker: ticker.trim().toUpperCase(),
        seuil: seuilNum,
        direction,
      });
      setTicker("");
      setSeuil("");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Erreur lors de la création de l'alerte");
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p className="text-sm font-semibold mb-3">Alertes de marché</p>

      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        className="flex flex-wrap items-end gap-2 mb-4"
      >
        <div className="flex flex-col gap-1">
          <label htmlFor="alert-ticker" className="text-xs text-[var(--muted-foreground)]">
            Ticker
          </label>
          <input
            id="alert-ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL"
            className="w-24 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="alert-direction" className="text-xs text-[var(--muted-foreground)]">
            Condition
          </label>
          <select
            id="alert-direction"
            value={direction}
            onChange={(e) => setDirection(e.target.value as PriceAlertDirection)}
            className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
          >
            <option value="au_dessus">au-dessus de</option>
            <option value="en_dessous">en-dessous de</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="alert-seuil" className="text-xs text-[var(--muted-foreground)]">
            Seuil
          </label>
          <input
            id="alert-seuil"
            type="number"
            step="0.01"
            value={seuil}
            onChange={(e) => setSeuil(e.target.value)}
            placeholder="200"
            className="w-24 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
          />
        </div>
        <Button type="submit" size="sm" variant="secondary" loading={createAlert.isPending}>
          Ajouter
        </Button>
      </form>

      {formError && <p className="text-xs text-[var(--destructive)] mb-3">{formError}</p>}

      {alertsQuery.isPending ? (
        <div className="skeleton-shimmer h-10 w-full rounded-lg" />
      ) : alerts.length === 0 ? (
        <p className="text-xs text-[var(--muted-foreground)]">Aucune alerte configurée.</p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-3 py-2 text-sm"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span className="font-medium">{a.ticker}</span>
                <span className="text-[var(--muted-foreground)]">
                  {a.direction === "au_dessus" ? "au-dessus de" : "en-dessous de"} {fmt(a.seuil)}
                </span>
                <span className="text-[var(--muted-foreground)]">
                  · actuel {a.prix_actuel != null ? fmt(a.prix_actuel) : "—"}
                </span>
              </span>
              <span className="flex items-center gap-2 shrink-0">
                <Badge variant={a.declenchee ? "destructive" : "outline"}>
                  {a.declenchee ? "déclenchée" : "en veille"}
                </Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Supprimer l'alerte ${a.ticker}`}
                  onClick={() => {
                    void deleteAlert.mutateAsync(a.id);
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden />
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SuiviTab() {
  const snapshotQuery = useSnapshot();
  const perfQuery = usePerf();
  const historyQuery = useHistory(10_000);
  const benchmarksQuery = useBenchmarks();
  const riskQuery = useRisk();
  const snap = snapshotQuery.data ?? null;
  const perf = perfQuery.data ?? null;
  const history = historyQuery.data ?? [];
  const benchmarks = benchmarksQuery.data ?? [];
  const loading = snapshotQuery.isPending || perfQuery.isPending || historyQuery.isPending;
  const refetchSnapshot = snapshotQuery.refetch;
  const refetchPerf = perfQuery.refetch;
  const refetchHistory = historyQuery.refetch;
  const refetchBenchmarks = benchmarksQuery.refetch;
  const [error, setError] = useState<string | null>(null);
  const [snapping, setSnapping] = useState(false);
  const [currency, setCurrency] = useState<"EUR" | "USD" | "CAD">("EUR");
  const [remoteRate, setRemoteRate] = useState(1);
  const rate = currency === "EUR" ? 1 : remoteRate;
  const autoSnapshotRequested = useRef(false);

  useEffect(() => {
    if (currency === "EUR") return;
    let cancelled = false;
    financeApi
      .fx("EUR", currency)
      .then((r) => !cancelled && setRemoteRate(r.rates[currency] || 1))
      .catch(() => !cancelled && setRemoteRate(1));
    return () => {
      cancelled = true;
    };
  }, [currency]);

  const money = useCallback(
    (v: number) => new Intl.NumberFormat("fr-CA", { style: "currency", currency }).format(v * rate),
    [currency, rate],
  );

  const load = useCallback(async () => {
    setError(null);
    await Promise.allSettled([
      refetchSnapshot(),
      refetchPerf(),
      refetchHistory(),
      refetchBenchmarks(),
    ]);
  }, [refetchSnapshot, refetchPerf, refetchHistory, refetchBenchmarks]);

  useEffect(() => {
    if (loading || autoSnapshotRequested.current) return;
    const today = new Date().toISOString().split("T")[0];
    if (snap && snap.date >= today) return;
    autoSnapshotRequested.current = true;
    financeApi
      .snapshotAuto()
      .then(() => load())
      .catch(() => {
        autoSnapshotRequested.current = false;
      });
  }, [load, loading, snap]);

  const handleSnapshot = async () => {
    setSnapping(true);
    try {
      await financeApi.snapshotCreate();
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur snapshot");
    } finally {
      setSnapping(false);
    }
  };

  const valeur = perf?.valeur ?? 0;
  const investit = perf?.investit ?? 0;
  const plTotal = perf?.pl_total ?? 0;
  const plPct = perf?.pl_pct ?? 0;
  const cw8 = benchmarks.find((b) => b.nom === "CW8" || b.ticker === "CW8.PA");
  const hasMoneyWeightedReturn = perf?.mwr_annualise_pct != null;
  const annualizedReturn = hasMoneyWeightedReturn
    ? perf.mwr_annualise_pct
    : (perf?.cagr_pct ?? null);
  const cw8MoneyWeighted = cw8 ? moneyWeightedAnnualizedReturn(cw8.serie, history) : null;
  const cw8CapitalReturn =
    cw8?.serie.length && history.length
      ? annualizedCapitalReturn(
          cw8.serie[cw8.serie.length - 1].valeur,
          investit,
          history[0].date,
          history[history.length - 1].date,
        )
      : null;
  const cw8Annualized = hasMoneyWeightedReturn ? cw8MoneyWeighted : cw8CapitalReturn;
  const coreError = snapshotQuery.error ?? perfQuery.error ?? historyQuery.error;
  const errorMessage = error ?? (coreError instanceof Error ? coreError.message : null);

  if (errorMessage) {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-[var(--destructive)]/30 bg-[var(--destructive)]/5 p-4"
      >
        <div className="flex min-w-0 items-center gap-2 text-sm text-[var(--destructive)]">
          <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
          <span>{errorMessage}</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            void load();
          }}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Réessayer
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Sélecteur de devise (conversion au taux du jour) */}
      <div className="flex items-center justify-end gap-1.5">
        <span className="text-xs text-[var(--muted-foreground)]">Devise</span>
        {(["EUR", "USD", "CAD"] as const).map((c) => (
          <button
            type="button"
            key={c}
            onClick={() => setCurrency(c)}
            aria-pressed={currency === c}
            className={`cursor-pointer rounded-md px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)] ${
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
      <StaggerGroup className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
              { label: "Investi", value: money(investit), color: "" },
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
            ].map((stat) => (
              <StaggerItem key={stat.label}>
                <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover">
                  <p className="text-xs text-[var(--muted-foreground)] font-medium mb-1">
                    {stat.label}
                  </p>
                  <p className={`font-display text-xl tabular-nums ${stat.color}`}>{stat.value}</p>
                </div>
              </StaggerItem>
            ))}
          </>
        )}
      </StaggerGroup>

      {/* TRI pondéré par les flux ; ancien CAGR seulement si le MWR est indisponible. */}
      {!loading && annualizedReturn != null && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span
            className="text-[var(--muted-foreground)]"
            title={
              hasMoneyWeightedReturn
                ? "TRI/XIRR annualisé : chaque apport ou retrait est pondéré par son montant et sa date."
                : "CAGR simplifié du rapport entre la valeur actuelle et le capital net investi ; les dates des apports ne sont pas neutralisées."
            }
          >
            {hasMoneyWeightedReturn
              ? "Rendement annualisé (TRI)"
              : "Rendement annualisé (CAGR simplifié)"}
          </span>
          <span
            className={`font-mono font-semibold ${annualizedReturn >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}
          >
            {formatPct(annualizedReturn)}
          </span>
          {cw8Annualized != null && (
            <span className="text-[var(--muted-foreground)]">
              vs <strong className="text-[var(--foreground)]">CW8</strong>{" "}
              <span className="font-mono">{formatPct(cw8Annualized)}</span>
            </span>
          )}
          <span className="text-xs text-[var(--muted-foreground)]">
            · même période · mêmes apports
          </span>
          {!hasMoneyWeightedReturn && (
            <span className="text-xs text-[var(--warning-foreground)]">
              · TRI indisponible : dates d&apos;apports incomplètes
            </span>
          )}
        </div>
      )}

      {/* Ratios de risque (Sharpe / Sortino / drawdown) */}
      {!loading && riskQuery.data && <RiskMetricsRow metrics={riskQuery.data} />}

      {/* Chart */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <p className="text-sm font-semibold">Évolution du portefeuille</p>
            <p className="text-xs text-[var(--muted-foreground)]">
              {loading
                ? "Chargement…"
                : `${history.length} snapshots${cw8?.serie.length ? " · vs 100 % CW8.PA (mêmes apports)" : ""}`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                void handleSnapshot();
              }}
              loading={snapping}
              disabled={loading}
            >
              <Camera className="h-3.5 w-3.5" aria-hidden />
              Snapshot maintenant
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
      {!loading && (
        <CollapsibleSection title="Benchmarks" defaultOpen={false}>
          {benchmarksQuery.isError ? (
            <div className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm text-[var(--muted-foreground)]">
              <span>Les indices sont momentanément indisponibles.</span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  void benchmarksQuery.refetch();
                }}
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                Réessayer
              </Button>
            </div>
          ) : benchmarks.length === 0 ? (
            <div
              className="flex items-center gap-2 py-3 text-sm text-[var(--muted-foreground)]"
              aria-live="polite"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${benchmarksQuery.isFetching ? "animate-spin" : ""}`}
                aria-hidden
              />
              Actualisation des indices en arrière-plan…
            </div>
          ) : (
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
                  {benchmarks.map((b) => (
                    <tr key={b.ticker ?? b.nom} className="border-b border-[var(--border)]">
                      <td
                        className={`py-1.5 pr-4 font-medium ${
                          b.nom === "CW8" || b.ticker === "CW8.PA" ? "text-[var(--warning)]" : ""
                        }`}
                      >
                        {b.nom}
                        {b.nom === "CW8" || b.ticker === "CW8.PA" ? " (CW8.PA)" : ""}
                      </td>
                      <td className="py-1.5 pr-4">
                        <PerfBadge v={b.perf_6m_pct} />
                      </td>
                      <td className="py-1.5 pr-4">
                        <PerfBadge v={b.perf_mtd_pct} />
                      </td>
                      <td className="py-1.5">
                        <PerfBadge v={b.perf_1a_pct} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CollapsibleSection>
      )}

      <CashTaxPanel />
      <MarketAlertsCard />
      <ProjectionTool />
    </div>
  );
}
