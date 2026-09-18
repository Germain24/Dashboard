import type { BuffettEquityLookthrough, BuffettResultOut } from "@/lib/finance";
import { DataTable } from "@/components/ui/data-table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AllocCell, AllocationAnalysisCell, fmtEur, investedEur } from "./BuffettAllocationCells";
import { fmt } from "./buffett-ui";

export interface BuffettAllocationSectionProps {
  allocated: BuffettResultOut[];
  displayRows: BuffettResultOut[];
  hasAlloc: boolean;
  totalInvested: number;
  totalPct: number;
  runStatus: string;
  showLookthrough: boolean;
  loadingLookthrough: boolean;
  lookthroughError: string | null;
  lookthrough: BuffettEquityLookthrough | null;
  onSelectAllocationView: (value: string) => void | Promise<void>;
}

function AllocationHeader({
  hasAlloc,
  runStatus,
  showLookthrough,
  loadingLookthrough,
  onSelectAllocationView,
}: Pick<
  BuffettAllocationSectionProps,
  "hasAlloc" | "runStatus" | "showLookthrough" | "loadingLookthrough" | "onSelectAllocationView"
>) {
  if (!hasAlloc || runStatus !== "termine") return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-4">
      <h3 className="text-sm font-semibold">Composition du portefeuille</h3>
      <div className="flex items-center gap-2">
        {loadingLookthrough && (
          <span className="text-xs text-[var(--muted-foreground)]" aria-live="polite">
            Décomposition en cours…
          </span>
        )}
        <Tabs
          value={showLookthrough ? "actions" : "etf"}
          onValueChange={(value) => void onSelectAllocationView(value)}
        >
          <TabsList>
            <TabsTrigger value="etf">ETF</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>
  );
}

function LookthroughTable({ lookthrough }: { lookthrough: BuffettEquityLookthrough }) {
  const data = lookthrough.rows.map((row) => ({
    ...row,
    source_label: row.sources.join(" + ") || "—",
  }));
  return (
    <DataTable
      data={data}
      columns={[
        {
          key: "ticker",
          header: "Titre / catégorie",
          sortable: true,
          render: (row) => <span className="font-mono text-xs">{row.ticker}</span>,
        },
        { key: "name", header: "Entreprise / exposition", sortable: true },
        {
          key: "source_label",
          header: "ETF d’origine",
          sortable: true,
          render: (row) => (
            <span className="text-xs text-[var(--muted-foreground)]">{row.source_label}</span>
          ),
        },
        {
          key: "weight_pct",
          header: "Poids dans le portefeuille",
          align: "right",
          sortable: true,
          render: (row) => (
            <span className="whitespace-nowrap text-xs font-semibold">
              {fmt(row.weight_pct, 2)} %
            </span>
          ),
        },
      ]}
      searchKeys={["ticker", "name", "source_label"]}
      pageSize={50}
      emptyLabel="Aucune exposition identifiée"
      ariaLabel="Expositions détenues indirectement dans le portefeuille"
      getRowId={(row) => row.ticker}
    />
  );
}

function LookthroughContent({ lookthrough }: { lookthrough: BuffettEquityLookthrough }) {
  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold flex items-baseline gap-2 flex-wrap">
          Exposition économique détaillée
          <span className="text-xs font-normal text-[var(--muted-foreground)]">
            — {fmt(lookthrough.total_pct)} % du portefeuille · {fmt(lookthrough.equity_coverage_pct)}
            % des actions identifiées
          </span>
        </h3>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Les actions présentes dans plusieurs ETF sont cumulées. Les obligations sont regroupées
          par pays et tranche d’échéance.
        </p>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Actions connues {fmt(lookthrough.known_equities_pct)} % · autres actions {" "}
          {fmt(lookthrough.other_equities_pct)} % · compositions indisponibles {" "}
          {fmt(lookthrough.unknown_pct)} % · obligations détaillées {" "}
          {fmt(lookthrough.known_bonds_pct)} % · autres non-actions {" "}
          {fmt(lookthrough.other_non_equity_pct)} %
        </p>
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        {lookthrough.etfs.map((etf) => (
          <span
            key={etf.ticker}
            className="rounded-full border border-[var(--border)] px-2.5 py-1"
          >
            {etf.ticker} · {etf.status === "non_equity" ? `${etf.known_holdings} obligation(s)` : `${etf.known_holdings} ligne(s)`}
            {` · couverture ${fmt(etf.holdings_coverage_pct)} % · ${etf.source}`}
          </span>
        ))}
      </div>
      <LookthroughTable lookthrough={lookthrough} />
    </div>
  );
}

function AssetCell({ result }: { result: BuffettResultOut }) {
  return (
    <td className="py-2 pr-4 text-xs">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-mono font-semibold">{result.ticker}</span>
        <span>{result.display_name ?? result.nom ?? "—"}</span>
      </div>
      <span className="mt-0.5 block text-[11px] text-[var(--muted-foreground)]">
        {result.secteur ?? "Secteur inconnu"}
      </span>
      {(result.company_listings?.length ?? 0) > 1 && (
        <span className="block text-[10px] text-[var(--muted-foreground)]">
          {result.company_listings!.length} cotations · {result.company_listings!.join(", ")}
        </span>
      )}
      {result.fundamental_mismatch && (
        <span className="block text-[10px] font-semibold text-red-600">FUNDAMENTAL_MISMATCH</span>
      )}
      {(result.purchase_ineligibility_reasons?.length ?? 0) > 0 && (
        <span className="block text-[10px] font-semibold text-red-600">
          Achat bloqué · {result.purchase_ineligibility_reasons!.join(", ")}
        </span>
      )}
    </td>
  );
}

function InvestedCell({ result }: { result: BuffettResultOut }) {
  return (
    <td className="py-2 pr-3 text-right text-xs whitespace-nowrap">
      <span className="font-semibold">{fmtEur(investedEur(result))}</span>
      {result.allocation_pct != null && (
        <span className="text-[var(--muted-foreground)]"> · {fmt(result.allocation_pct)} %</span>
      )}
    </td>
  );
}

function AllocationRow({ result, hasAlloc }: { result: BuffettResultOut; hasAlloc: boolean }) {
  return (
    <tr
      key={result.id}
      className="border-b border-[var(--border)] align-top transition-colors hover:bg-[var(--muted)]/25"
    >
      <AssetCell result={result} />
      <td className="py-2 pr-4">
        <AllocationAnalysisCell result={result} />
      </td>
      {hasAlloc && <InvestedCell result={result} />}
      <td className="py-2 text-right text-xs">
        <AllocCell result={result} />
      </td>
    </tr>
  );
}

function AllocationTable({
  displayRows: rows,
  hasAlloc,
  runStatus,
  totalInvested,
  totalPct,
}: Pick<BuffettAllocationSectionProps, "displayRows" | "hasAlloc" | "runStatus" | "totalInvested" | "totalPct">) {
  const title = hasAlloc
    ? runStatus === "en_cours"
      ? "Meilleure allocation provisoire (par montant investi)"
      : "Allocation cible (par montant investi)"
    : "Top 50 scores Buffett";
  return (
    <div>
      <h3 className="text-sm font-semibold mb-2 flex items-baseline gap-2 flex-wrap">
        {title}
        {hasAlloc && (
          <span className="text-xs font-normal text-[var(--muted-foreground)]">
            — {fmtEur(totalInvested)} investis ({fmt(totalPct)} % du capital)
          </span>
        )}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-xs text-[var(--muted-foreground)] text-left">
              <th className="pb-2 pr-4">Actif</th>
              <th className="pb-2 pr-4">Analyse</th>
              {hasAlloc && <th className="pb-1 pr-3 text-right">Investi</th>}
              <th className="pb-1 text-right">{hasAlloc ? "À acheter" : "Alloc. cible"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((result) => (
              <AllocationRow key={result.id} result={result} hasAlloc={hasAlloc} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AllocationContent({
  showLookthrough,
  loadingLookthrough,
  lookthroughError,
  lookthrough,
  ...tableProps
}: Omit<BuffettAllocationSectionProps, "allocated" | "onSelectAllocationView">) {
  if (showLookthrough && lookthroughError) {
    return (
      <div
        className="rounded-[var(--radius)] border border-[var(--destructive)] p-4 text-sm text-[var(--destructive)]"
        role="alert"
      >
        {lookthroughError}
      </div>
    );
  }
  if (showLookthrough && loadingLookthrough) {
    return (
      <div
        className="rounded-[var(--radius)] border border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]"
        role="status"
      >
        Chargement et cumul des actions détenues par les ETF…
      </div>
    );
  }
  if (showLookthrough && lookthrough) return <LookthroughContent lookthrough={lookthrough} />;
  return <AllocationTable {...tableProps} />;
}

export function BuffettAllocationSection({ onSelectAllocationView, ...props }: BuffettAllocationSectionProps) {
  return (
    <>
      <AllocationHeader {...props} onSelectAllocationView={onSelectAllocationView} />
      <AllocationContent {...props} />
    </>
  );
}
