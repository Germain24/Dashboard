"use client";

import { useState } from "react";
import { useTabParam } from "@/lib/useTabParam";
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
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";
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
import { useObjectifPatrimoine, useSetObjectifPatrimoine } from "@/lib/queries/finance";
import type { PatrimoineGoal } from "@/lib/finance";

const formatEuros = (value: number) =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);

const formatDeadline = (value: string) =>
  new Intl.DateTimeFormat("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));

const PortefeuilleTab = dynamic(
  () => import("./PortefeuilleTab").then((module) => module.PortefeuilleTab),
  { loading: TabLoading },
);
const CompositionTab = dynamic(
  () => import("./CompositionTab").then((module) => module.CompositionTab),
  { loading: TabLoading },
);
const BuffettTab = dynamic(() => import("./BuffettTab").then((module) => module.BuffettTab), {
  loading: TabLoading,
});
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
const ImpotsTab = dynamic(() => import("./ImpotsTab").then((module) => module.ImpotsTab), {
  loading: TabLoading,
});

export function ObjectifWidget() {
  const { data, isLoading, isError, refetch } = useObjectifPatrimoine();
  const setObjectif = useSetObjectifPatrimoine();
  const [editing, setEditing] = useState<PatrimoineGoal>();
  const [targetValue, setTargetValue] = useState("");
  const [deadline, setDeadline] = useState("");
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

  return (
    <>
      <div className="grid gap-3 md:grid-cols-2">
        {data.objectifs.map((goal) => {
          const pct = Math.min(Math.max(goal.progression_pct, 0), 100);
          const color = goal.atteint
            ? "var(--success)"
            : pct >= 75
              ? "var(--warning)"
              : "var(--ring)";
          const isConfigured = goal.objectif_eur > 0;

          return (
            <article
              key={goal.id}
              className="flex min-h-[112px] items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--muted)] px-4 py-3 text-sm"
            >
              <Target className="mt-0.5 h-4 w-4 shrink-0" style={{ color }} aria-hidden />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-medium">{goal.label}</h3>
                    <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                      {goal.echeance
                        ? `Échéance : ${formatDeadline(goal.echeance)} · cible ajustée chaque jour`
                        : "Horizon libre · sans limite de temps"}
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={() => {
                      setEditing(goal);
                      setTargetValue(goal.objectif_eur > 0 ? String(goal.objectif_eur) : "");
                      setDeadline(goal.echeance ?? "");
                      setInputError(undefined);
                    }}
                    aria-label={`Modifier l'objectif ${goal.label}`}
                    title={`Modifier ${goal.label}`}
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>

                {isConfigured ? (
                  <>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="font-semibold tabular-nums" style={{ color }}>
                        {formatEuros(goal.valeur_eur)} / {formatEuros(goal.objectif_eur)}
                      </span>
                      <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
                        {pct.toFixed(1)} %
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--border)]">
                      <div
                        className="bar-fill h-full rounded-full"
                        style={{ width: `${pct}%`, background: color }}
                      />
                    </div>
                    <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                      {goal.atteint
                        ? "Objectif atteint !"
                        : goal.id === "japon" && goal.epargne_journaliere_eur != null
                          ? `Reste ${formatEuros(goal.restant_eur)} · ${goal.jours_restants ?? 0} jours · ${formatEuros(goal.epargne_journaliere_eur)} à mettre de côté par jour`
                          : `Reste ${formatEuros(goal.restant_eur)}`}
                    </p>
                  </>
                ) : (
                  <p className="mt-3 text-xs text-[var(--muted-foreground)]">
                    Définissez le budget du voyage pour commencer son suivi séparé.
                  </p>
                )}
              </div>
            </article>
          );
        })}
      </div>

      <Dialog open={Boolean(editing)} onClose={() => setEditing(undefined)} className="max-w-sm">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!editing) return;
            const objectif = Number(targetValue);
            if (!Number.isFinite(objectif) || objectif <= 0) {
              setInputError("Saisissez un montant supérieur à zéro.");
              return;
            }
            setObjectif.mutate(
              {
                id: editing.id,
                objectif_eur: objectif,
                ...(editing.id === "japon" ? { ...(deadline ? { echeance: deadline } : {}) } : {}),
              },
              {
                onSuccess: () => setEditing(undefined),
              },
            );
          }}
        >
          <DialogHeader onClose={() => setEditing(undefined)}>
            <DialogTitle>{editing?.label ?? "Objectif patrimonial"}</DialogTitle>
          </DialogHeader>
          <DialogBody className="space-y-4">
            <Input
              label="Montant cible"
              type="number"
              min="1"
              step="100"
              value={targetValue}
              onChange={(event) => {
                setTargetValue(event.target.value);
                setInputError(undefined);
              }}
              error={inputError}
            />
            {editing?.id === "japon" && (
              <Input
                label="Date prévue du voyage"
                type="date"
                value={deadline}
                onChange={(event) => setDeadline(event.target.value)}
              />
            )}
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setEditing(undefined)}>
              Annuler
            </Button>
            <Button type="submit" loading={setObjectif.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </>
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
  { id: "suivi", label: "Vue d’ensemble", icon: TrendingUp },
  { id: "portefeuille", label: "Positions détenues", icon: BarChart3 },
  { id: "composition", label: "Exposition & composition", icon: LayoutGrid },
  { id: "rebalancing", label: "Ajuster les poids", icon: RefreshCw },
  { id: "buffett", label: "Optimiseur Buffett", icon: Star },
  { id: "transactions", label: "Mouvements & dépôts", icon: CreditCard },
  { id: "patrimoine", label: "Patrimoine net", icon: Landmark },
  { id: "impots", label: "Fiscalité", icon: Receipt },
];
const TAB_PANEL_ID = "finance-tab-panel";

export function Finance() {
  const [active, setActive] = useTabParam<Tab>("suivi");

  return (
    <div className="space-y-0">
      <ModuleHeader
        title="Finance"
        subtitle="Portefeuille long terme"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={active}
        onChange={(id) => setActive(id as Tab)}
        panelId={TAB_PANEL_ID}
      />

      <div className="px-6 pt-6">
        <ObjectifWidget />
      </div>

      {/* Content — re-mounts on tab change for fade-in-up */}
      <ModuleTabPanel
        key={active}
        panelId={TAB_PANEL_ID}
        activeTab={active}
        className="p-6 animate-fade-in-up"
      >
        {active === "suivi" && <SuiviTab />}
        {active === "portefeuille" && <PortefeuilleTab />}
        {active === "composition" && <CompositionTab />}
        {active === "rebalancing" && <RebalancingTab />}
        {active === "buffett" && <BuffettTab />}
        {active === "transactions" && <TransactionsTab />}
        {active === "patrimoine" && <PatrimoineTab />}
        {active === "impots" && <ImpotsTab />}
      </ModuleTabPanel>
    </div>
  );
}
