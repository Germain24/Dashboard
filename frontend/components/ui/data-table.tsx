"use client";

/**
 * DataTable générique réutilisable : tri par colonne, recherche plein-texte
 * et pagination côté client. Sans dépendance externe.
 *
 * Usage :
 *   <DataTable
 *     data={transactions}
 *     columns={[
 *       { key: "ticker", header: "Ticker" },
 *       { key: "quantite", header: "Qté", align: "right", sortable: true },
 *       { key: "date", header: "Date", render: (r) => fmtDate(r.date) },
 *     ]}
 *     searchKeys={["ticker", "broker"]}
 *   />
 */

import {
  useId,
  useMemo,
  useState,
  type Dispatch,
  type Key,
  type ReactNode,
  type SetStateAction,
} from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./button";

export type Column<T> = {
  key: keyof T & string;
  header: string;
  align?: "left" | "right" | "center";
  sortable?: boolean;
  render?: (row: T) => ReactNode;
};

type Props<T> = {
  data: T[];
  columns: Column<T>[];
  searchKeys?: (keyof T & string)[];
  pageSize?: number;
  emptyLabel?: string;
  ariaLabel?: string;
  getRowId?: (row: T, index: number) => Key;
};

function alignClass(align?: Column<Record<string, unknown>>["align"]): string {
  return align === "right" ? "text-right" : align === "center" ? "text-center" : "";
}

function justifyClass(align?: Column<Record<string, unknown>>["align"]): string {
  return align === "right"
    ? "justify-end"
    : align === "center"
      ? "justify-center"
      : "justify-start";
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) return <ArrowUpDown className="h-3.5 w-3.5" aria-hidden="true" />;
  return direction === "asc" ? (
    <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
  ) : (
    <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
  );
}

function SearchBox({
  searchId,
  query,
  onQueryChange,
}: {
  searchId: string;
  query: string;
  onQueryChange: (value: string) => void;
}) {
  return (
    <div>
      <label htmlFor={searchId} className="sr-only">
        Rechercher dans le tableau
      </label>
      <input
        id={searchId}
        data-ui-control
        type="search"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Rechercher…"
        className="h-9 w-full max-w-xs rounded-[var(--radius)] border border-[var(--border)] bg-[var(--field)] px-3 text-sm transition-[border-color,box-shadow] duration-200 focus:border-[var(--ring)] focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--ring)_12%,transparent)]"
      />
    </div>
  );
}

function HeaderCell<T extends Record<string, unknown>>({
  column,
  sortKey,
  sortDir,
  onSort,
}: {
  column: Column<T>;
  sortKey: string | null;
  sortDir: "asc" | "desc";
  onSort: (key: string) => void;
}) {
  const active = sortKey === column.key;
  const sortableContent = (
    <button
      type="button"
      onClick={() => onSort(column.key)}
      className={`inline-flex w-full items-center gap-1 rounded-[var(--radius-sm)] py-1 hover:text-[var(--foreground)] ${justifyClass(column.align)}`}
    >
      <span>{column.header}</span>
      <SortIcon active={active} direction={sortDir} />
    </button>
  );
  return (
    <th
      key={column.key}
      scope="col"
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
      className={`pb-1.5 pr-3 ${alignClass(column.align)}`}
    >
      {column.sortable ? sortableContent : column.header}
    </th>
  );
}

function DataTableHeader<T extends Record<string, unknown>>({
  columns,
  sortKey,
  sortDir,
  onSort,
}: {
  columns: Column<T>[];
  sortKey: string | null;
  sortDir: "asc" | "desc";
  onSort: (key: string) => void;
}) {
  return (
    <thead>
      <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
        {columns.map((column) => (
          <HeaderCell key={column.key} column={column} sortKey={sortKey} sortDir={sortDir} onSort={onSort} />
        ))}
      </tr>
    </thead>
  );
}

function DataCell<T extends Record<string, unknown>>({ row, column }: { row: T; column: Column<T> }) {
  return (
    <td key={column.key} className={`py-1.5 pr-3 ${alignClass(column.align)}`}>
      {column.render ? column.render(row) : String(row[column.key] ?? "—")}
    </td>
  );
}

function DataRow<T extends Record<string, unknown>>({
  row,
  columns,
  rowId,
}: {
  row: T;
  columns: Column<T>[];
  rowId: Key;
}) {
  return (
    <tr key={rowId} className="border-b border-[var(--border)] hover:bg-[var(--muted)]">
      {columns.map((column) => (
        <DataCell key={column.key} row={row} column={column} />
      ))}
    </tr>
  );
}

function DataTableBody<T extends Record<string, unknown>>({
  rows,
  columns,
  emptyLabel,
  getRowId,
  safePage,
  pageSize,
}: {
  rows: T[];
  columns: Column<T>[];
  emptyLabel: string;
  getRowId?: (row: T, index: number) => Key;
  safePage: number;
  pageSize: number;
}) {
  if (rows.length === 0) {
    return (
      <tbody>
        <tr>
          <td colSpan={columns.length} className="py-6 text-center text-[var(--muted-foreground)]">
            {emptyLabel}
          </td>
        </tr>
      </tbody>
    );
  }
  return (
    <tbody>
      {rows.map((row, index) => (
        <DataRow
          key={rowKey(row, safePage * pageSize + index, getRowId)}
          row={row}
          columns={columns}
          rowId={rowKey(row, safePage * pageSize + index, getRowId)}
        />
      ))}
    </tbody>
  );
}

function fallbackRowId<T extends Record<string, unknown>>(row: T, index: number): Key {
  return typeof row.id === "string" || typeof row.id === "number" ? row.id : index;
}

function rowKey<T extends Record<string, unknown>>(
  row: T,
  index: number,
  getRowId?: (row: T, index: number) => Key,
): Key {
  return getRowId?.(row, index) ?? fallbackRowId(row, index);
}

function Pagination({
  count,
  page,
  pageCount,
  onPageChange,
}: {
  count: number;
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
}) {
  if (pageCount <= 1) return null;
  return (
    <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
      <span>{count} éléments</span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0}
          aria-label="Page précédente"
          title="Page précédente"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </Button>
        <span aria-live="polite">{page + 1} / {pageCount}</span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => onPageChange(Math.min(pageCount - 1, page + 1))}
          disabled={page >= pageCount - 1}
          aria-label="Page suivante"
          title="Page suivante"
        >
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}

function filterData<T extends Record<string, unknown>>(
  data: T[],
  query: string,
  searchKeys: (keyof T & string)[],
): T[] {
  if (!query || searchKeys.length === 0) return data;
  const normalized = query.toLowerCase();
  return data.filter((row) =>
    searchKeys.some((key) => String(row[key] ?? "").toLowerCase().includes(normalized)),
  );
}

function compareDefined(left: unknown, right: unknown): number {
  const leftValue = left as string | number | Date;
  const rightValue = right as string | number | Date;
  if (leftValue < rightValue) return -1;
  if (leftValue > rightValue) return 1;
  return 0;
}

function compareRows<T extends Record<string, unknown>>(
  left: T,
  right: T,
  sortKey: keyof T,
  sortDir: "asc" | "desc",
): number {
  const leftValue = left[sortKey];
  const rightValue = right[sortKey];
  if (leftValue == null) return 1;
  if (rightValue == null) return -1;
  const comparison = compareDefined(leftValue, rightValue);
  return sortDir === "asc" ? comparison : -comparison;
}

function sortData<T extends Record<string, unknown>>(
  rows: T[],
  sortKey: string | null,
  sortDir: "asc" | "desc",
): T[] {
  if (!sortKey) return rows;
  const copy = [...rows];
  copy.sort((left, right) => compareRows(left, right, sortKey as keyof T, sortDir));
  return copy;
}

function updateSort(
  key: string,
  currentKey: string | null,
  setKey: (value: string | null) => void,
  setDirection: Dispatch<SetStateAction<"asc" | "desc">>,
) {
  if (currentKey === key) {
    setDirection((direction) => (direction === "asc" ? "desc" : "asc"));
    return;
  }
  setKey(key);
  setDirection("asc");
}

function useDataTableModel<T extends Record<string, unknown>>(
  data: T[],
  searchKeys: (keyof T & string)[],
  pageSize: number,
) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);
  const filtered = useMemo(() => filterData(data, query, searchKeys), [data, query, searchKeys]);
  const sorted = useMemo(() => sortData(filtered, sortKey, sortDir), [filtered, sortKey, sortDir]);
  const normalizedPageSize = Math.max(1, pageSize);
  const pageCount = Math.max(1, Math.ceil(sorted.length / normalizedPageSize));
  const safePage = Math.min(page, pageCount - 1);
  const rows = sorted.slice(
    safePage * normalizedPageSize,
    safePage * normalizedPageSize + normalizedPageSize,
  );
  const onQueryChange = (value: string) => {
    setQuery(value);
    setPage(0);
  };
  const onSort = (key: string) => updateSort(key, sortKey, setSortKey, setSortDir);
  return {
    searchId,
    query,
    rows,
    sorted,
    sortKey,
    sortDir,
    safePage,
    normalizedPageSize,
    pageCount,
    onQueryChange,
    onSort,
    setPage,
  };
}

type NormalizedProps<T> = Omit<Props<T>, "searchKeys" | "pageSize" | "emptyLabel" | "ariaLabel"> & {
  searchKeys: (keyof T & string)[];
  pageSize: number;
  emptyLabel: string;
  ariaLabel: string;
};

function normalizeProps<T extends Record<string, unknown>>(props: Props<T>): NormalizedProps<T> {
  const defaults = {
    searchKeys: [] as (keyof T & string)[],
    pageSize: 20,
    emptyLabel: "Aucune donnée",
    ariaLabel: "Tableau de données",
  };
  return { ...defaults, ...props };
}

function DataTableView<T extends Record<string, unknown>>({
  data,
  columns,
  searchKeys,
  pageSize,
  emptyLabel,
  ariaLabel,
  getRowId,
}: NormalizedProps<T>) {
  const {
    searchId,
    query,
    rows,
    sorted,
    sortKey,
    sortDir,
    safePage,
    normalizedPageSize,
    pageCount,
    onQueryChange,
    onSort,
    setPage,
  } = useDataTableModel(data, searchKeys, pageSize);

  return (
    <div className="space-y-3">
      {searchKeys.length > 0 && (
        <SearchBox
          searchId={searchId}
          query={query}
          onQueryChange={onQueryChange}
        />
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{ariaLabel}</caption>
          <DataTableHeader
            columns={columns}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={onSort}
          />
          <DataTableBody
            rows={rows}
            columns={columns}
            emptyLabel={emptyLabel}
            getRowId={getRowId}
            safePage={safePage}
            pageSize={normalizedPageSize}
          />
        </table>
      </div>
      <Pagination
        count={sorted.length}
        page={safePage}
        pageCount={pageCount}
        onPageChange={setPage}
      />
    </div>
  );
}

export function DataTable<T extends Record<string, unknown>>(props: Props<T>) {
  return <DataTableView {...normalizeProps(props)} />;
}

export default DataTable;
