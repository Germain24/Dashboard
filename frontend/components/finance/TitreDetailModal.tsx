"use client";

/** Modal de détail d'un titre : cours, P/E, score Buffett, poids, performance. */

import { useEffect, useState } from "react";
import { financeApi, type TitreDetail } from "@/lib/finance";

function fmt(n: number | null | undefined, suffix = "") {
  if (n == null) return "—";
  return n.toLocaleString("fr-CA", { maximumFractionDigits: 2 }) + suffix;
}

export function TitreDetailModal({ ticker, onClose }: { ticker: string; onClose: () => void }) {
  const [detail, setDetail] = useState<TitreDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    financeApi
      .titreDetail(ticker)
      .then((d) => !cancelled && setDetail(d))
      .catch((e) => !cancelled && setError(e?.message ?? "Erreur"));
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  const rows: { label: string; value: string }[] = detail
    ? [
        { label: "Cours", value: fmt(detail.prix, " €") },
        { label: "Score Buffett", value: detail.score_buffett != null ? fmt(detail.score_buffett) : "—" },
        { label: "P/E", value: fmt(detail.per) },
        { label: "Secteur", value: detail.secteur ?? "—" },
        { label: "Quantité", value: fmt(detail.quantite) },
        { label: "PMU", value: fmt(detail.pmu, " €") },
        { label: "Valeur", value: fmt(detail.valeur, " €") },
        { label: "Poids", value: fmt(detail.poids_pct, " %") },
        { label: "Perf.", value: (detail.pl_pct >= 0 ? "+" : "") + fmt(detail.pl_pct, " %") },
      ]
    : [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Détail ${ticker}`}
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-[var(--border)] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{detail?.nom ?? ticker}</h2>
            <p className="font-mono text-xs text-[var(--muted-foreground)]">{ticker}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="rounded-md px-2 py-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
          >
            ✕
          </button>
        </div>
        <div className="p-5">
          {error ? (
            <p className="text-sm text-[var(--destructive)]">⚠ {error}</p>
          ) : !detail ? (
            <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>
          ) : (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
              {rows.map((r) => (
                <div key={r.label} className="flex flex-col">
                  <dt className="text-xs text-[var(--muted-foreground)]">{r.label}</dt>
                  <dd className="font-medium tabular-nums">{r.value}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>
    </div>
  );
}
