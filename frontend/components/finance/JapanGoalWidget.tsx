"use client";

import { useState } from "react";
import { AlertTriangle, CalendarDays, Pencil, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useObjectifJapon, useSetObjectifJapon } from "@/lib/queries/finance";

const cad = (value: number) =>
  new Intl.NumberFormat("fr-CA", {
    style: "currency",
    currency: "CAD",
    currencyDisplay: "code",
    maximumFractionDigits: 0,
  }).format(value);

const shortDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

export function JapanGoalWidget() {
  const { data, isLoading, isError, refetch } = useObjectifJapon();
  const setGoal = useSetObjectifJapon();
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState("");
  const [daily, setDaily] = useState("");
  const [inputError, setInputError] = useState<string>();

  if (isLoading) {
    return (
      <div
        className="skeleton-shimmer h-[92px] rounded-lg"
        aria-label="Chargement de l'objectif Japon"
      />
    );
  }

  if (isError || !data) {
    return (
      <div
        role="alert"
        className="flex min-h-[92px] flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--destructive)]/30 px-3 py-2 text-sm"
      >
        <span className="flex items-center gap-2 text-[var(--destructive)]">
          <AlertTriangle className="h-4 w-4" aria-hidden />
          Objectif Japon indisponible.
        </span>
        <Button size="sm" variant="ghost" onClick={() => void refetch()}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          Réessayer
        </Button>
      </div>
    );
  }

  const pct = Math.min(Math.max(data.progression_pct, 0), 100);
  const color = data.atteint ? "var(--success)" : pct >= 75 ? "var(--warning)" : "var(--ring)";
  const gap = Math.abs(data.ecart_cad);

  return (
    <div className="flex min-h-[92px] items-start gap-3 rounded-lg bg-[var(--muted)] px-3 py-2 text-sm">
      <CalendarDays className="mt-0.5 h-4 w-4 shrink-0" style={{ color }} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <span className="text-[var(--muted-foreground)]">Réserve Japon &amp; études</span>
          <span className="font-semibold tabular-nums" style={{ color }}>
            {cad(data.liquidites_cad)} / {cad(data.objectif_restant_cad)}
          </span>
        </div>
        <div
          className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--border)]"
          role="progressbar"
          aria-label="Progression de la réserve Japon et études"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
        >
          <div
            className="bar-fill h-full rounded-full"
            style={{ width: `${pct}%`, background: color }}
          />
        </div>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-x-3 text-xs text-[var(--muted-foreground)]">
          <span>
            {cad(data.budget_quotidien_cad)}/jour · {data.jours_restants.toLocaleString("fr-FR")} jours
          </span>
          <span className="tabular-nums">
            {data.atteint ? `Marge ${cad(gap)}` : `Manque ${cad(gap)}`}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
          Jusqu&apos;au {shortDate(data.date_cible)} · {data.n_comptes} compte{data.n_comptes > 1 ? "s" : ""} bancaire{data.n_comptes > 1 ? "s" : ""}
        </p>
      </div>
      <Button
        type="button"
        size="icon"
        variant="ghost"
        onClick={() => {
          setEditing(true);
          setDate(data.date_cible);
          setDaily(String(data.budget_quotidien_cad));
          setInputError(undefined);
        }}
        aria-label="Modifier l'objectif Japon"
        title="Modifier l'objectif Japon"
      >
        <Pencil className="h-3.5 w-3.5" aria-hidden />
      </Button>

      <Dialog open={editing} onClose={() => setEditing(false)} className="max-w-sm">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const budget = Number(daily);
            if (!date || !Number.isFinite(budget) || budget <= 0) {
              setInputError("Saisissez une date et un budget quotidien supérieur à zéro.");
              return;
            }
            setGoal.mutate(
              { date_cible: date, budget_quotidien_cad: budget },
              { onSuccess: () => setEditing(false) },
            );
          }}
        >
          <DialogHeader onClose={() => setEditing(false)}>
            <DialogTitle>Réserve Japon &amp; études</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <div className="space-y-3">
              <Input
                label="Date de fin"
                type="date"
                value={date}
                onChange={(event) => {
                  setDate(event.target.value);
                  setInputError(undefined);
                }}
              />
              <Input
                label="Budget quotidien (CAD)"
                type="number"
                min="0.01"
                step="0.01"
                value={daily}
                onChange={(event) => {
                  setDaily(event.target.value);
                  setInputError(undefined);
                }}
                error={inputError}
              />
              <p className="text-xs text-[var(--muted-foreground)]">
                La cible diminue automatiquement chaque jour. Seuls les actifs classés
                « liquidités » ou « compte en banque » sont comptés.
              </p>
            </div>
          </DialogBody>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
              Annuler
            </Button>
            <Button type="submit" loading={setGoal.isPending}>
              Enregistrer
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
