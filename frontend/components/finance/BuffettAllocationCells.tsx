import type { BuffettResultOut } from "@/lib/finance";
import { fmt, ScoreChip } from "./buffett-ui";

const BROKER_LABELS: Array<[string[], string]> = [
  [["trading212", "t212"], "T212"],
  [["boursedirect", "boursdirect"], "Bourso"],
  [["ibkr"], "IBKR"],
];

export function brokerShort(broker?: string): string {
  if (!broker) return "";
  const normalized = broker.toLowerCase().replace(/[^a-z0-9]/g, "");
  const match = BROKER_LABELS.find(([keys]) => keys.some((key) => normalized.includes(key)));
  return match?.[1] ?? broker;
}

export function investedEur(result: BuffettResultOut): number {
  return (result.allocations ?? []).reduce((sum, allocation) => sum + (allocation.eur ?? 0), 0);
}

export function fmtEur(value: number) {
  return `${Math.round(value).toLocaleString("fr-FR")} €`;
}

function isActionable(allocation: NonNullable<BuffettResultOut["allocations"]>[number]) {
  const value = allocation.type === "pie" ? allocation.pie_pct : allocation.shares;
  return (value ?? 0) > 0;
}

function AllocationLine({ allocation }: { allocation: NonNullable<BuffettResultOut["allocations"]>[number] }) {
  if (allocation.type === "pie") {
    return <><span className="font-semibold">{allocation.pie_pct} %</span>{" "}<span className="text-[var(--muted-foreground)]">pie {brokerShort(allocation.broker)}</span></>;
  }
  const label = allocation.shares === 1 ? "action" : "actions";
  return <><span className="font-semibold">{allocation.shares}</span>{" "}<span className="text-[var(--muted-foreground)]">{label} {brokerShort(allocation.broker)}</span></>;
}

export function AllocCell({ result }: { result: BuffettResultOut }) {
  const lines = (result.allocations ?? []).filter(isActionable);
  if (!lines.length) return <span>{result.allocation_pct ? `${fmt(result.allocation_pct)} %` : "—"}</span>;
  return <div className="flex flex-col items-end gap-0.5">{lines.map((allocation, index) => <span key={index} className="whitespace-nowrap"><AllocationLine allocation={allocation} /></span>)}</div>;
}

function hasScoreDetails(result: BuffettResultOut) {
  return [
    result.durability_score,
    result.dilution_discipline_score,
    result.financial_moat_proxy_score,
    result.score_confidence_pct,
    result.buffett_rules_score,
    result.score_model_fit,
  ].some((value) => value != null) || Boolean(result.score_business_model);
}

function ScoreConfidence({ result }: { result: BuffettResultOut }) {
  if (result.score_confidence_pct == null) return <>—</>;
  return <>{fmt(result.score_confidence_pct)} %</>;
}

function scoreValue(value: number | null | undefined) {
  return fmt(value ?? undefined);
}

function BusinessModelScore({ result }: { result: BuffettResultOut }) {
  if (!result.score_business_model) return null;
  const fit = result.score_model_fit != null ? ` · fit ${fmt(result.score_model_fit, 2)}` : "";
  return <><span>Modèle</span><strong className="font-medium">{result.score_business_model}{fit}</strong></>;
}

function ScoreDetailsGrid({ result }: { result: BuffettResultOut }) {
  return (
    <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 rounded border border-[var(--border)] bg-[var(--muted)]/30 p-2">
      <span>Durabilité</span><strong>{scoreValue(result.durability_score)}</strong>
      <span>Dilution</span><strong>{scoreValue(result.dilution_discipline_score)}</strong>
      <span>Moat financier</span><strong>{scoreValue(result.financial_moat_proxy_score)}</strong>
      <span>Confiance</span><strong><ScoreConfidence result={result} /></strong>
      <span>Règles v1</span><strong>{scoreValue(result.buffett_rules_score)}</strong>
      <BusinessModelScore result={result} />
    </div>
  );
}

function ScoreDetails({ result }: { result: BuffettResultOut }) {
  if (!hasScoreDetails(result)) return null;
  return (
    <details className="mt-1">
      <summary className="cursor-pointer select-none text-[11px] text-[var(--muted-foreground)] hover:text-[var(--foreground)]">Détails du score</summary>
      <ScoreDetailsGrid result={result} />
    </details>
  );
}

export function AllocationAnalysisCell({ result }: { result: BuffettResultOut }) {
  if (result.secteur === "ETF") {
    return <span className="inline-flex rounded-full border border-[var(--info)]/40 px-2 py-0.5 text-xs font-medium text-[var(--info)]">ETF</span>;
  }
  const quality = result.buffett_quality_score ?? result.score;
  return (
    <div className="min-w-40 text-xs">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span><span className="text-[var(--muted-foreground)]">Qualité </span><ScoreChip score={quality} /></span>
        {result.score != null && <span><span className="text-[var(--muted-foreground)]">Classement </span><span className="font-medium">{fmt(result.score)}</span></span>}
      </div>
      <ScoreDetails result={result} />
    </div>
  );
}
