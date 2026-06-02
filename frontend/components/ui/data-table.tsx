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

import { useMemo, useState, type ReactNode } from "react";

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
};

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  searchKeys = [],
  pageSize = 20,
  emptyLabel = "Aucune donnée",
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    if (!query || searchKeys.length === 0) return data;
    const q = query.toLowerCase();
    return data.filter((row) =>
      searchKeys.some((k) => String(row[k] ?? "").toLowerCase().includes(q)),
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

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const rows = sorted.slice(safePage * pageSize, safePage * pageSize + pageSize);

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
        <input
          value={query}
          onChange={(e) => { setQuery(e.target.value); setPage(0); }}
          placeholder="Rechercher…"
          className="w-full max-w-xs px-2.5 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)]"
        />
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`pb-1.5 pr-3 ${c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : ""} ${c.sortable ? "cursor-pointer select-none hover:text-[var(--foreground)]" : ""}`}
                  onClick={c.sortable ? () => toggleSort(c.key) : undefined}
                >
                  {c.header}
                  {c.sortable && sortKey === c.key && (sortDir === "asc" ? " ▲" : " ▼")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-6 text-center text-[var(--muted-foreground)]">
                  {emptyLabel}
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr key={i} className="border-b border-[var(--border)] hover:bg-[var(--muted)]">
                  {columns.map((c) => (
                    <td key={c.key} className={`py-1.5 pr-3 ${c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : ""}`}>
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
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={safePage === 0}
              className="rounded-md border border-[var(--border)] px-2 py-1 disabled:opacity-40 hover:bg-[var(--muted)]"
            >
              Précédent
            </button>
            <span>{safePage + 1} / {pageCount}</span>
            <button
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              disabled={safePage >= pageCount - 1}
              className="rounded-md border border-[var(--border)] px-2 py-1 disabled:opacity-40 hover:bg-[var(--muted)]"
            >
              Suivant
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default DataTable;
