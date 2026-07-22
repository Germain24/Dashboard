"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertTriangle,
  BarChart3,
  CreditCard,
  Landmark,
  LayoutGrid,
  Pencil,
  Receipt,
  RefreshCw,
  Star,
  Target,
  TrendingUp,
} from "lucide-react";
import { ModuleHeader } from "@/components/layout";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { TabLoading } from "@/components/ui/tab-loading";
import { SuiviTab } from "./SuiviTab";
import { JapanGoalWidget } from "./JapanGoalWidget";
import { useObjectifPatrimoine, useSetObjectifPatrimoine } from "@/lib/queries/finance";

const PortefeuilleTab = dynamic(
  () => import("./PortefeuilleTab").then((module) => module.PortefeuilleTab),
  { loading: TabLoading },
);
const CompositionTab = dynamic(
  () => import("./CompositionTab").then((module) => module.CompositionTab),
  { loading: TabLoading },
);
const BuffettTab = dynamic(
  () => import("./BuffettTab").then((module) => module.BuffettTab),
  { loading: TabLoading },
);
const RebalancingTab = dynamic(
  () => import("./RebalancingTab").then((module) => module.RebalancingTab),
  { loading: TabLoading },
);
const TransactionsTab = dynamic(
  () => import("./TransactionsTab").then((module) => module.TransactionsTab),
  { loading: TabLoading },
);
const PatrimoineTab = dynamic(
  () => import("./PatrimoineTab").then((module) => module.PatrimoineTab),
  { loading: TabLoading },
);
const ImpotsTab = dynamic(
  () => import("./ImpotsTab").then((module) => module.ImpotsTab),
  { loading: TabLoading },
);

function ObjectifWidget() {
  const { data, isLoading, isError, refetch } = useObjectifPatrimoine();
  const setObjectif = useSetObjectifPatrimoine();
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState("");
  const [inputError, setInputError] = useState<string>();

  if (isLoading) {
    return (
      <div
        className="skeleton-shimmer h-[70px] rounded-lg"
        aria-label="Chargement de l'objectif patrimoine"
      />
    );
  }

  if (isError || !data) {
    return (
      <div
        role="alert"
        className="flex min-h-[70px] flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--destructive)]/30 px-3 py-2 text-sm"
      >
        <span className="flex items-center gap-2 text-[var(--destructive)]">
          <AlertTriangle className="h-4 w-4" aria-hidden />
          Objectif patrimonial indisponible.
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            void refetch();
          }}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Réessayer
        </Button>
      </div>
    );
  }

  const pct = Math.min(Math.max(data.progression_pct, 0), 100);
  const color = data.atteint ? "var(--success)" : pct >= 75 ? "var(--warning)" : "var(--ring)";

  const fmt = (n: number) =>
    new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

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
        <div
          className="mt-1 h-1.5 bg-[var(--border)] rounded-full overflow-hidden"
          role="progressbar"
          aria-label="Progression de l'objectif patrimoine"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
        >
          <div
            className="h-full rounded-full bar-fill"
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
          {data.atteint && (
            <span className="text-xs font-medium" style={{ color }}>
              Objectif atteint !
            </span>
          )}
        </div>
      </div>
      <Button
        type="button"
        size="icon"
        variant="ghost"
        onClick={() => {
          setEditing(true);
          setVal(String(data.objectif_eur));
          setInputError(undefined);
        }}
        aria-label="Modifier l'objectif patrimoine"
        title="Modifier l'objectif"
      >
        <Pencil className="h-3.5 w-3.5" aria-hidden />
      </Button>
      <Dialog open={editing} onClose={() => setEditing(false)} className="max-w-sm">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const objectif = Number(val);
            if (!Number.isFinite(objectif) || objectif <= 0) {
              setInputError("Saisissez un montant supérieur à zéro.");
              return;
            }
            setObjectif.mutate(objectif, {
              onSuccess: () => setEditing(false),
            });
          }}
        >
          <DialogHeader onClose={() => setEditing(false)}>
            <DialogTitle>Objectif patrimoine</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <Input
              label="Montant cible"
              type="number"
              min="1"
              step="1000"
              value={val}
              onChange={(event) => {
                setVal(event.target.value);
                setInputError(undefined);
              }}
              error={inputError}
            />
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
              Annuler
            </Button>
            <Button type="submit" loading={setObjectif.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}

type Tab =
  | "suivi"
  | "portefeuille"
  | "composition"
  | "rebalancing"
  | "buffett"
  | "transactions"
  | "patrimoine"
  | "impots";

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "suivi", label: "Suivi", icon: TrendingUp },
  { id: "portefeuille", label: "Portefeuille", icon: BarChart3 },
  { id: "composition", label: "Composition", icon: LayoutGrid },
  { id: "rebalancing", label: "Rebalancing", icon: RefreshCw },
  { id: "buffett", label: "Buffett", icon: Star },
  { id: "transactions", label: "Transactions", icon: CreditCard },
  { id: "patrimoine", label: "Patrimoine", icon: Landmark },
  { id: "impots", label: "Impôts", icon: Receipt },
];

export function Finance() {
  const [active, setActive] = useState<Tab>("suivi");

  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Finance"
        subtitle="Investissements, patrimoine & objectifs"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={active}
        onChange={(id) => setActive(id as Tab)}
      />

      <div className="grid gap-3 px-6 pt-6 lg:grid-cols-2">
        <ObjectifWidget />
        <JapanGoalWidget />
      </div>

      {/* Content — re-mounts on tab change for fade-in-up */}
      <div key={active} className="p-6 animate-fade-in-up">
        {active === "suivi" && <SuiviTab />}
        {active === "portefeuille" && <PortefeuilleTab />}
        {active === "composition" && <CompositionTab />}
        {active === "rebalancing" && <RebalancingTab />}
        {active === "buffett" && <BuffettTab />}
        {active === "transactions" && <TransactionsTab />}
        {active === "patrimoine" && <PatrimoineTab />}
        {active === "impots" && <ImpotsTab />}
      </div>
    </div>
  );
}
