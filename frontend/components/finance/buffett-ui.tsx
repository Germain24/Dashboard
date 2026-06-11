"use client";

/** Petits composants partagés de l'onglet Buffett (extraits de BuffettTab, #532). */

import { Badge } from "@/components/ui/badge";

export function fmt(n?: number, dec = 1) {
  return n != null ? n.toLocaleString("fr-FR", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : "—";
}

export function StatusBadge({ s }: { s: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "info"> = {
    termine: "success", en_cours: "info", interrompu: "warning", erreur: "destructive",
  };
  return <Badge variant={map[s] ?? "outline"}>{s}</Badge>;
}

export function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="w-full h-2 rounded-full bg-[var(--muted)] overflow-hidden">
      <div className="h-full rounded-full bg-[var(--ring)] transition-all"
        style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export function ScoreChip({ score }: { score?: number }) {
  if (score == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  const color = score >= 200
    ? "text-[var(--info)]"
    : score >= 80 ? "text-[var(--success)]" : "";
  const label = score >= 200 ? "ETF" : fmt(score);
  return <span className={`font-medium ${color}`}>{label}</span>;
}
