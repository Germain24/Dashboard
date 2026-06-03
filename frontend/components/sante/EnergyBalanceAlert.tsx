"use client";

/** Alerte déficit/surplus calorique trop agressif sur 7 jours (#70). */

import { useEffect, useState } from "react";
import { santeApi, type EnergyBalance } from "@/lib/sante";

export function EnergyBalanceAlert() {
  const [bal, setBal] = useState<EnergyBalance | null>(null);

  useEffect(() => {
    santeApi.energyBalance(7).then(setBal).catch(() => {});
  }, []);

  // On n'affiche que si le rythme mérite une alerte.
  if (!bal || bal.level === "ok" || bal.avg_balance == null) return null;

  const isAlert = bal.level === "alert";
  const color = isAlert ? "var(--destructive)" : "var(--warning)";
  const bg = isAlert ? "var(--destructive-muted, var(--warning-muted))" : "var(--warning-muted)";

  return (
    <div
      className="rounded-lg border px-3 py-2 text-sm flex flex-wrap items-center gap-x-2 gap-y-1"
      style={{ borderColor: `color-mix(in srgb, ${color} 40%, transparent)`, background: bg, color }}
    >
      <span>{isAlert ? "🚨" : "⚠"}</span>
      <span className="font-medium">{bal.message}</span>
      <span className="text-xs opacity-80 tabular-nums">
        ({bal.avg_consumed} kcal/j vs maintenance {bal.avg_maintenance} kcal · {bal.days} j)
      </span>
    </div>
  );
}
