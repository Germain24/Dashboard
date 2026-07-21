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

import { useId, useMemo, useState, type Key, type ReactNode } from "react";
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

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  searchKeys = [],
  pageSize = 20,
  emptyLabel = "Aucune donnée",
  ariaLabel = "Tableau de données",
  getRowId,
}: Props<T>) {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!query || searchKeys.length === 0) return data;
    const q = query.toLowerCase();
    return data.filter((row) =>
      searchKeys.some((k) =>
        String(row[k] ?? "")
          .toLowerCase()
          .includes(q),
      ),
    );
  }, [data, query, searchKeys]);

  const sorted = useMemo(() => {
    if (!sortKey) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = a[sortKey as keyof T];
      const bv = b[sortKey as keyof T];
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const normalizedPageSize = Math.max(1, pageSize);
  const pageCount = Math.max(1, Math.ceil(sorted.length / normalizedPageSize));
  const safePage = Math.min(page, pageCount - 1);
  const rows = sorted.slice(
    safePage * normalizedPageSize,
    safePage * normalizedPageSize + normalizedPageSize,
  );

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  return (
    <div className="space-y-3">
      {searchKeys.length > 0 && (
        <div>
          <label htmlFor={searchId} className="sr-only">
            Rechercher dans le tableau
          </label>
          <input
            id={searchId}
            data-ui-control
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder="Rechercher…"
            className="h-9 w-full max-w-xs rounded-[var(--radius)] border border-[var(--border)] bg-[var(--field)] px-3 text-sm transition-[border-color,box-shadow] duration-200 focus:border-[var(--ring)] focus:outline-none focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--ring)_12%,transparent)]"
          />
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{ariaLabel}</caption>
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={
                    c.sortable && sortKey === c.key
                      ? sortDir === "asc"
                        ? "ascending"
                        : "descending"
                      : undefined
                  }
                  className={`pb-1.5 pr-3 ${c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : ""}`}
                >
                  {c.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(c.key)}
                      className={`inline-flex w-full items-center gap-1 rounded-[var(--radius-sm)] py-1 hover:text-[var(--foreground)] ${
                        c.align === "right"
                          ? "justify-end"
                          : c.align === "center"
                            ? "justify-center"
                            : "justify-start"
                      }`}
                    >
                      <span>{c.header}</span>
                      {sortKey !== c.key ? (
                        <ArrowUpDown className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : sortDir === "asc" ? (
                        <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-6 text-center text-[var(--muted-foreground)]"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr
                  key={
                    getRowId?.(row, safePage * normalizedPageSize + i) ??
                    (typeof row.id === "string" || typeof row.id === "number" ? row.id : i)
                  }
                  className="border-b border-[var(--border)] hover:bg-[var(--muted)]"
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={`py-1.5 pr-3 ${c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : ""}`}
                    >
                      {c.render ? c.render(row) : String(row[c.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
          <span>{sorted.length} éléments</span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={safePage === 0}
              aria-label="Page précédente"
              title="Page précédente"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <span aria-live="polite">
              {safePage + 1} / {pageCount}
            </span>
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              disabled={safePage >= pageCount - 1}
              aria-label="Page suivante"
              title="Page suivante"
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
