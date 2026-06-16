"use client";

import { useState } from "react";
import { TrendingUp, BarChart3, RefreshCw, Star, LayoutGrid, CreditCard, Target, Landmark } from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import { PortefeuilleTab } from "./PortefeuilleTab";
import { SuiviTab } from "./SuiviTab";
import { CompositionTab } from "./CompositionTab";
import { BuffettTab } from "./BuffettTab";
import { RebalancingTab } from "./RebalancingTab";
import { TransactionsTab } from "./TransactionsTab";
import { PatrimoineTab } from "./PatrimoineTab";
import { useObjectifPatrimoine, useSetObjectifPatrimoine } from "@/lib/queries/finance";

function ObjectifWidget() {
  const { data, isLoading } = useObjectifPatrimoine();
  const setObjectif = useSetObjectifPatrimoine();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState("");

  if (isLoading || !data) return null;

  const pct = Math.min(data.progression_pct, 100);
  const color = data.atteint ? "var(--success, #22c55e)" : pct >= 75 ? "#f59e0b" : "var(--ring)";

  const fmt = (n: number) =>
    new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

  return (
    <div className="flex items-center gap-3 text-sm bg-[var(--muted)] rounded-lg px-3 py-2">
      <Target size={15} style={{ color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[var(--muted-foreground)]">Objectif patrimoine</span>
          <span className="font-semibold tabular-nums" style={{ color }}>
            {fmt(data.valeur_eur)} / {fmt(data.objectif_eur)}
          </span>
        </div>
        <div className="mt-1 h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, background: color }}
          />
        </div>
        <div className="flex items-center justify-between mt-0.5">
          <span className="text-[var(--muted-foreground)] text-xs">{pct.toFixed(1)} %</span>
          {!data.atteint && (
            <span className="text-[var(--muted-foreground)] text-xs">
              Reste {fmt(data.restant_eur)}
            </span>
          )}
          {data.atteint && <span className="text-xs font-medium" style={{ color }}>Objectif atteint !</span>}
        </div>
      </div>
      <button
        onClick={() => { setEditing(true); setVal(String(data.objectif_eur)); }}
        className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] px-1"
        title="Modifier l'objectif"
      >
        ✏
      </button>
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditing(false)}>
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-5 w-72 shadow-xl" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold mb-3">Objectif patrimoine</h3>
            <input
              type="number"
              value={val}
              onChange={e => setVal(e.target.value)}
              className="w-full border border-[var(--border)] rounded-lg px-3 py-2 text-sm bg-[var(--background)] mb-3"
              placeholder="300000"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(false)} className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)]">Annuler</button>
              <button
                onClick={() => { setObjectif.mutate(Number(val)); setEditing(false); }}
                className="px-3 py-1.5 text-sm rounded-lg bg-[var(--ring)] text-white"
              >Enregistrer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

type Tab = "suivi" | "portefeuille" | "composition" | "rebalancing" | "buffett" | "transactions" | "patrimoine";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "suivi",        label: "Suivi",        icon: TrendingUp },
  { id: "portefeuille", label: "Portefeuille",  icon: BarChart3 },
  { id: "composition",  label: "Composition",   icon: LayoutGrid },
  { id: "rebalancing",  label: "Rebalancing",   icon: RefreshCw },
  { id: "buffett",      label: "Buffett",       icon: Star },
  { id: "transactions", label: "Transactions",  icon: CreditCard },
  { id: "patrimoine",   label: "Patrimoine",    icon: Landmark },
];

export function Finance() {
  const [active, setActive] = useState<Tab>("suivi");

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Finance"
        subtitle="Portefeuille long terme"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={active}
        onChange={(id) => setActive(id as Tab)}
      />

      <div className="px-6 pt-6">
        <ObjectifWidget />
      </div>

      {/* Content — re-mounts on tab change for fade-in-up */}
      <div key={active} className="p-6 animate-fade-in-up">
        {active === "suivi"        && <SuiviTab />}
        {active === "portefeuille" && <PortefeuilleTab />}
        {active === "composition"  && <CompositionTab />}
        {active === "rebalancing"  && <RebalancingTab />}
        {active === "buffett"      && <BuffettTab />}
        {active === "transactions" && <TransactionsTab />}
        {active === "patrimoine"   && <PatrimoineTab />}
      </div>
    </div>
  );
}
