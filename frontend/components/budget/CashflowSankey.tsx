"use client";

import { useMemo, useState } from "react";
import { RotateCcw } from "lucide-react";
import type { BudgetCategory } from "@/lib/budget";
import { categoryDescendantIds, flattenCategoryOptions } from "@/lib/budget-categories";
import {
  bucketTransactionCategory,
  buildCashflowSankey,
  compactFlowBuckets,
  type FlowBucket,
} from "@/lib/budget-sankey";
import { useBudgetCategories, useBudgetTransactions } from "@/lib/queries/budget";
import { CHART_SERIES } from "@/lib/design/colors";

type BudgetFlowTransaction = {
  id: number;
  date: string;
  montant: number;
  marchand?: string;
  description?: string;
  category_id: number | null;
  compte?: string;
  tags?: string[];
};

type PositionedBucket = FlowBucket & { x: number; y: number; height: number; color: string };

const formatCAD = (value: number) =>
  new Intl.NumberFormat("fr-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(value ?? 0);

const localIsoDate = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

function initialRange() {
  const today = new Date();
  return { from: `${localIsoDate(today).slice(0, 7)}-01`, to: localIsoDate(today) };
}

function addToBuckets(
  buckets: Map<string, FlowBucket>,
  id: string,
  label: string,
  value: number,
  categoryId: number | null,
) {
  const existing = buckets.get(id);
  if (existing) existing.value += value;
  else buckets.set(id, { id, label, value, categoryId });
}

function groupBuckets(
  transactions: BudgetFlowTransaction[],
  getBucket: (transaction: BudgetFlowTransaction) => FlowBucket,
): FlowBucket[] {
  const buckets = new Map<string, FlowBucket>();
  for (const transaction of transactions) {
    const bucket = getBucket(transaction);
    addToBuckets(
      buckets,
      bucket.id,
      bucket.label,
      Math.abs(transaction.montant),
      bucket.categoryId ?? null,
    );
  }
  return [...buckets.values()];
}

function positionBuckets(
  buckets: FlowBucket[],
  x: number,
  scale: number,
  height: number,
  colors: string[],
): PositionedBucket[] {
  const top = 20;
  const innerHeight = height - top * 2;
  const gap = 7;
  const contentHeight =
    buckets.reduce((sum, bucket) => sum + bucket.value * scale, 0) +
    gap * Math.max(0, buckets.length - 1);
  let y = top + (innerHeight - contentHeight) / 2;
  return buckets.map((bucket, index) => {
    const node = {
      ...bucket,
      x,
      y,
      height: bucket.value * scale,
      color: colors[index % colors.length],
    };
    y += node.height + gap;
    return node;
  });
}

export default function CashflowSankey() {
  const dates = useMemo(() => initialRange(), []);
  const [fromDate, setFromDate] = useState(dates.from);
  const [toDate, setToDate] = useState(dates.to);
  const [expenseFocusFilter, setExpenseFocusFilter] = useState("");
  const [incomeFocusFilter, setIncomeFocusFilter] = useState("");
  const [accountFilter, setAccountFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [merchantFilter, setMerchantFilter] = useState("");

  const transactionsQuery = useBudgetTransactions({
    from: fromDate || undefined,
    to: toDate || undefined,
  });
  const categoriesQuery = useBudgetCategories();
  const transactions = (
    Array.isArray(transactionsQuery.data) ? transactionsQuery.data : []
  ) as BudgetFlowTransaction[];
  const categories = (
    Array.isArray(categoriesQuery.data) ? categoriesQuery.data : []
  ) as BudgetCategory[];
  const loading = transactionsQuery.isLoading || categoriesQuery.isLoading;

  const incomeRoot = categories.find(
    (category) =>
      category.parent_id == null && category.nom.toLocaleLowerCase("fr-CA") === "revenus",
  );
  const expenseRoot = categories.find(
    (category) =>
      category.parent_id == null && category.nom.toLocaleLowerCase("fr-CA") === "dépenses",
  );
  const incomeCategoryIds = incomeRoot
    ? categoryDescendantIds(categories, incomeRoot.id)
    : new Set<number>();
  const categoryOptions = flattenCategoryOptions(categories);
  const expenseCategoryOptions = categoryOptions.filter(
    ({ category }) => !incomeCategoryIds.has(category.id),
  );
  const incomeCategoryOptions = categoryOptions.filter(({ category }) =>
    incomeCategoryIds.has(category.id),
  );
  const expenseFocusId = expenseFocusFilter ? Number(expenseFocusFilter) : null;
  const selectedIncomeFocusId = incomeFocusFilter ? Number(incomeFocusFilter) : null;
  const expenseFocusCategoryId = expenseFocusId ?? expenseRoot?.id ?? null;
  const incomeFocusId = selectedIncomeFocusId ?? incomeRoot?.id ?? null;
  const accounts = [
    ...new Set(
      transactions
        .map((transaction) => transaction.compte)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort();
  const tags = [...new Set(transactions.flatMap((transaction) => transaction.tags ?? []))].sort();

  const matchingTransactions = transactions.filter((transaction) => {
    if (accountFilter && transaction.compte !== accountFilter) return false;
    if (tagFilter && !(transaction.tags ?? []).includes(tagFilter)) return false;
    const search = merchantFilter.trim().toLocaleLowerCase("fr-CA");
    if (
      search &&
      !`${transaction.marchand ?? ""} ${transaction.description ?? ""}`
        .toLocaleLowerCase("fr-CA")
        .includes(search)
    )
      return false;
    return true;
  });

  const incomeTransactions = matchingTransactions.filter((transaction) => transaction.montant > 0);
  const expenseTransactions = matchingTransactions.filter((transaction) => transaction.montant < 0);
  const incomeBuckets = groupBuckets(incomeTransactions, (transaction) =>
    bucketTransactionCategory(
      transaction.category_id,
      categories,
      incomeFocusId,
      "income",
      incomeRoot?.id ?? null,
    ),
  );
  const expenseBuckets = groupBuckets(expenseTransactions, (transaction) =>
    bucketTransactionCategory(
      transaction.category_id,
      categories,
      expenseFocusCategoryId,
      "expense",
      incomeRoot?.id ?? null,
    ),
  );
  const incomeTotal = incomeTransactions.reduce((sum, transaction) => sum + transaction.montant, 0);
  const expensesTotal = expenseTransactions.reduce(
    (sum, transaction) => sum - transaction.montant,
    0,
  );

  const flow = buildCashflowSankey(
    compactFlowBuckets(incomeBuckets, "Autres revenus", 12),
    compactFlowBuckets(expenseBuckets, "Autres dépenses", 12),
  );

  const chartHeight = Math.max(300, Math.max(flow.sources.length, flow.targets.length) * 48 + 56);
  const maximumNodeCount = Math.max(flow.sources.length, flow.targets.length);
  const chartScale =
    flow.totalFlow > 0
      ? Math.max(0, chartHeight - 40 - 7 * Math.max(0, maximumNodeCount - 1)) / flow.totalFlow
      : 0;
  const sourceNodes = positionBuckets(flow.sources, 160, chartScale, chartHeight, ["#22c55e"]);
  const targetNodes = positionBuckets(flow.targets, 880, chartScale, chartHeight, CHART_SERIES);
  const sourcePositions = new Map(sourceNodes.map((node) => [node.id, node]));
  const targetPositions = new Map(targetNodes.map((node) => [node.id, node]));
  const sourceOffsets = new Map(sourceNodes.map((node) => [node.id, node.y]));
  const targetOffsets = new Map(targetNodes.map((node) => [node.id, node.y]));
  const links = flow.links.map((link, index) => {
    const source = sourcePositions.get(link.sourceId);
    const target = targetPositions.get(link.targetId);
    const thickness = link.value * chartScale;
    const sourceY = (sourceOffsets.get(link.sourceId) ?? source?.y ?? 0) + thickness / 2;
    const targetY = (targetOffsets.get(link.targetId) ?? target?.y ?? 0) + thickness / 2;
    sourceOffsets.set(link.sourceId, (sourceOffsets.get(link.sourceId) ?? 0) + thickness);
    targetOffsets.set(link.targetId, (targetOffsets.get(link.targetId) ?? 0) + thickness);
    const curve = (880 - (160 + 14)) * 0.45;
    const path = `M 174 ${sourceY - thickness / 2} C ${174 + curve} ${sourceY - thickness / 2}, ${880 - curve} ${targetY - thickness / 2}, 880 ${targetY - thickness / 2} L 880 ${targetY + thickness / 2} C ${880 - curve} ${targetY + thickness / 2}, ${174 + curve} ${sourceY + thickness / 2}, 174 ${sourceY + thickness / 2} Z`;
    return { ...link, index, path, source, target };
  });

  const total = incomeTotal + expensesTotal;
  const net = incomeTotal - expensesTotal;

  const applyPreset = (days: number | "month" | "year") => {
    const today = new Date();
    let start = new Date(today);
    if (days === "month") start = new Date(today.getFullYear(), today.getMonth(), 1);
    else if (days === "year") start = new Date(today.getFullYear(), 0, 1);
    else start.setDate(today.getDate() - days + 1);
    setFromDate(localIsoDate(start));
    setToDate(localIsoDate(today));
  };

  const drillExpense = (categoryId: number | null | undefined) => {
    if (categoryId == null) return;
    setExpenseFocusFilter(String(categoryId));
  };

  const drillIncome = (categoryId: number | null | undefined) => {
    if (categoryId != null) setIncomeFocusFilter(String(categoryId));
  };

  const resetFilters = () => {
    setExpenseFocusFilter("");
    setIncomeFocusFilter("");
    setAccountFilter("");
    setTagFilter("");
    setMerchantFilter("");
    applyPreset("month");
  };

  return (
    <section
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 sm:p-5"
      aria-labelledby="cashflow-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="cashflow-title" className="text-base font-semibold">
            Flux de trésorerie
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-[var(--muted-foreground)]">
            Classe chaque transaction à sa catégorie finale dans l’onglet Transactions : son montant
            remonte automatiquement vers ses catégories parentes. Choisis ou clique une catégorie
            pour explorer ses niveaux. Les rubans sont ventilés au prorata, pas dollar par dollar.
          </p>
        </div>
        <button
          type="button"
          onClick={resetFilters}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-xs transition-colors hover:bg-[var(--muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          <RotateCcw size={13} aria-hidden="true" /> Réinitialiser
        </button>
      </div>

      <div className="mt-4 flex flex-wrap gap-1.5" aria-label="Période rapide">
        {(
          [
            ["month", "Ce mois-ci"],
            [30, "30 jours"],
            [90, "3 mois"],
            ["year", "Cette année"],
          ] as const
        ).map(([preset, label]) => (
          <button
            key={String(preset)}
            type="button"
            onClick={() => applyPreset(preset)}
            className="rounded-full border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--muted-foreground)] transition-colors hover:border-[var(--primary)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-[var(--muted-foreground)]">
          Du
          <input
            type="date"
            value={fromDate}
            max={toDate || undefined}
            onChange={(event) => setFromDate(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          />
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Au
          <input
            type="date"
            value={toDate}
            min={fromDate || undefined}
            onChange={(event) => setToDate(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          />
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Dépenses à détailler
          <select
            value={expenseFocusFilter}
            onChange={(event) => setExpenseFocusFilter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          >
            <option value="">Toutes les catégories de dépenses</option>
            {expenseCategoryOptions.map(({ category, label }) => (
              <option key={category.id} value={category.id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Revenus à détailler
          <select
            value={incomeFocusFilter}
            onChange={(event) => setIncomeFocusFilter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          >
            <option value="">Toutes les sources de revenus</option>
            {incomeCategoryOptions.map(({ category, label }) => (
              <option key={category.id} value={category.id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Compte / carte
          <select
            value={accountFilter}
            onChange={(event) => setAccountFilter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          >
            <option value="">Tous les comptes</option>
            {accounts.map((account) => (
              <option key={account} value={account}>
                {account}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Tag
          <select
            value={tagFilter}
            onChange={(event) => setTagFilter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)]"
          >
            <option value="">Tous les tags</option>
            {tags.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted-foreground)]">
          Marchand / libellé
          <input
            type="search"
            value={merchantFilter}
            onChange={(event) => setMerchantFilter(event.target.value)}
            placeholder="Ex. épicerie, loyer…"
            className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-2 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]"
          />
        </label>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 rounded-lg bg-[var(--muted)]/50 p-3 text-center sm:gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)] sm:text-xs">
            Entrées
          </p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--success)] sm:text-base">
            {formatCAD(incomeTotal)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)] sm:text-xs">
            Sorties
          </p>
          <p className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--destructive)] sm:text-base">
            {formatCAD(expensesTotal)}
          </p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wide text-[var(--muted-foreground)] sm:text-xs">
            Solde
          </p>
          <p
            className={`mt-0.5 text-sm font-semibold tabular-nums sm:text-base ${net >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]"}`}
          >
            {formatCAD(net)}
          </p>
        </div>
      </div>

      {loading ? (
        <div
          className="mt-4 h-72 rounded-lg skeleton-shimmer"
          aria-label="Chargement du diagramme"
        />
      ) : total === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
          Aucune entrée ni sortie pour ces dates et filtres.
        </p>
      ) : (
        <>
          <div className="mt-4 hidden overflow-hidden rounded-lg bg-[var(--background)]/40 sm:block">
            <svg
              viewBox={`0 0 1100 ${chartHeight}`}
              role="img"
              aria-label={`Diagramme de flux : ${formatCAD(incomeTotal)} d'entrées, ${formatCAD(expensesTotal)} de sorties`}
              className="block h-auto w-full"
            >
              <text
                x="160"
                y="16"
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="var(--success)"
              >
                ENTRÉES
              </text>
              <text
                x="880"
                y="16"
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="var(--destructive)"
              >
                SORTIES
              </text>
              <defs>
                {links.map((link) => (
                  <linearGradient
                    key={`gradient-${link.index}`}
                    id={`cashflow-gradient-${link.index}`}
                    x1="174"
                    y1="0"
                    x2="880"
                    y2="0"
                    gradientUnits="userSpaceOnUse"
                  >
                    <stop offset="0%" stopColor={link.source?.color ?? "#22c55e"} />
                    <stop offset="100%" stopColor={link.target?.color ?? "#ef4444"} />
                  </linearGradient>
                ))}
              </defs>
              {links.map((link) => (
                <path
                  key={`${link.sourceId}-${link.targetId}`}
                  d={link.path}
                  fill={`url(#cashflow-gradient-${link.index})`}
                  fillOpacity="0.46"
                >
                  <title>
                    {link.source?.label} → {link.target?.label} : {formatCAD(link.value)}
                  </title>
                </path>
              ))}
              {sourceNodes.map((node) => (
                <g
                  key={node.id}
                  className={node.categoryId != null ? "cursor-pointer" : ""}
                  onClick={() => drillIncome(node.categoryId)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      drillIncome(node.categoryId);
                    }
                  }}
                  tabIndex={node.categoryId != null ? 0 : undefined}
                  role={node.categoryId != null ? "button" : undefined}
                  aria-label={
                    node.categoryId != null
                      ? `Détailler les revenus par ${node.label}, ${formatCAD(node.value)}`
                      : undefined
                  }
                >
                  <title>
                    {node.label} : {formatCAD(node.value)}
                  </title>
                  <rect
                    x={node.x}
                    y={node.y}
                    width="14"
                    height={Math.max(1, node.height)}
                    rx="3"
                    fill={node.color}
                  />
                  <text
                    x="148"
                    y={node.y + node.height / 2 + 4}
                    textAnchor="end"
                    fontSize="12"
                    fill="var(--foreground)"
                  >
                    {node.label}
                  </text>
                </g>
              ))}
              {targetNodes.map((node) => (
                <g
                  key={node.id}
                  className={node.categoryId != null ? "cursor-pointer" : ""}
                  onClick={() => drillExpense(node.categoryId)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      drillExpense(node.categoryId);
                    }
                  }}
                  tabIndex={node.categoryId != null ? 0 : undefined}
                  role={node.categoryId != null ? "button" : undefined}
                  aria-label={
                    node.categoryId != null
                      ? `Détailler ${node.label}, ${formatCAD(node.value)}`
                      : undefined
                  }
                >
                  <title>
                    {node.label} : {formatCAD(node.value)}
                    {node.categoryId != null ? " — cliquer pour détailler" : ""}
                  </title>
                  <rect
                    x={node.x}
                    y={node.y}
                    width="14"
                    height={Math.max(1, node.height)}
                    rx="3"
                    fill={node.color}
                  />
                  <text
                    x="905"
                    y={node.y + node.height / 2 + 4}
                    textAnchor="start"
                    fontSize="12"
                    fill="var(--foreground)"
                  >
                    {node.label}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          <div className="mt-4 space-y-4 sm:hidden">
            <FlowBucketList
              title="Entrées d'argent"
              buckets={flow.sources}
              color="var(--success)"
              onSelect={drillIncome}
            />
            <FlowBucketList
              title="Sorties d'argent"
              buckets={flow.targets}
              color="var(--destructive)"
              onSelect={drillExpense}
            />
          </div>

          <details className="mt-3 rounded-lg border border-[var(--border)] px-3 py-2">
            <summary className="cursor-pointer text-xs font-medium text-[var(--muted-foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]">
              Afficher le détail des flux en tableau
            </summary>
            <div className="mt-2 max-h-64 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-[var(--card)] text-[var(--muted-foreground)]">
                  <tr>
                    <th className="px-2 py-1.5">Origine</th>
                    <th className="px-2 py-1.5">Destination</th>
                    <th className="px-2 py-1.5 text-right">Flux réparti</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {links.map((link) => (
                    <tr key={`${link.sourceId}-${link.targetId}`}>
                      <td className="px-2 py-1.5">{link.source?.label}</td>
                      <td className="px-2 py-1.5">{link.target?.label}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">
                        {formatCAD(link.value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}

function FlowBucketList({
  title,
  buckets,
  color,
  onSelect,
}: {
  title: string;
  buckets: FlowBucket[];
  color: string;
  onSelect?: (categoryId: number | null | undefined) => void;
}) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color }}>
        {title}
      </h3>
      <ul className="space-y-1.5">
        {buckets.map((bucket) => (
          <li key={bucket.id}>
            <button
              type="button"
              onClick={() => onSelect?.(bucket.categoryId)}
              disabled={!onSelect || bucket.categoryId == null}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-[var(--muted)] disabled:cursor-default disabled:hover:bg-transparent"
            >
              <span className="min-w-0 flex-1 truncate">{bucket.label}</span>
              <span className="tabular-nums text-[var(--muted-foreground)]">
                {formatCAD(bucket.value)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
