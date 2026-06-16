"use client";

import { useState } from "react";
import { Briefcase, Trash2 } from "lucide-react";
import type { WorkShift } from "@/lib/travail";
import {
  useCreateShift,
  useDeleteShift,
  useSetTauxHoraire,
  useShifts,
  useTravailSettings,
  useTravailSummary,
  useUpdateShift,
} from "@/lib/queries/travail";
import { ModuleHeader } from "@/components/layout";
import { EmptyState } from "@/components/ui/empty-state";

const inputCls =
  "w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";

const STATUT_LABELS: Record<WorkShift["statut"], string> = {
  prevu: "Prévu",
  fait: "Fait",
  annule: "Annulé",
};

function moisCourant(): string {
  return new Date().toISOString().slice(0, 7);
}

export function Travail() {
  const [mois, setMois] = useState(moisCourant());
  const shiftsQ = useShifts(mois);
  const summaryQ = useTravailSummary(mois);
  const settingsQ = useTravailSettings();
  const createM = useCreateShift();
  const updateM = useUpdateShift();
  const deleteM = useDeleteShift();
  const tauxM = useSetTauxHoraire();

  const [form, setForm] = useState({ date_jour: "", heure_debut: "09:00", heure_fin: "17:00", pause_min: 0 });

  const loading = shiftsQ.isLoading || summaryQ.isLoading;
  if (loading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (shiftsQ.isError) return <div className="p-6 text-[var(--destructive)]">⚠ {(shiftsQ.error).message}</div>;

  const shifts = shiftsQ.data ?? [];
  const s = summaryQ.data;

  const submit = () => {
    if (!form.date_jour) return;
    createM.mutate(form, { onSuccess: () => setForm((f) => ({ ...f, date_jour: "" })) });
  };

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Travail" subtitle="Shifts, validation d'heures & revenus à venir" />

      <div className="p-6 space-y-6 animate-fade-in-up">
        {/* Sélecteur de mois + taux horaire */}
        <div className="flex flex-wrap items-end gap-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Mois</span>
            <input type="month" value={mois} onChange={(e) => setMois(e.target.value)} className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Taux horaire (€/h)</span>
            <input
              type="number"
              min={0}
              step={0.01}
              defaultValue={settingsQ.data?.taux_horaire ?? ""}
              key={settingsQ.data?.taux_horaire}
              onBlur={(e) => {
                const v = parseFloat(e.target.value);
                if (!Number.isNaN(v) && v >= 0 && v !== settingsQ.data?.taux_horaire) tauxM.mutate(v);
              }}
              className={inputCls}
            />
          </label>
        </div>

        {/* Résumé du mois */}
        {s && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "Heures faites", value: `${s.heures_faites} h` },
              { label: "Heures prévues", value: `${s.heures_prevues} h` },
              { label: "Revenu réalisé", value: `${s.revenu_realise.toFixed(2)} €` },
              { label: "Revenu à venir", value: `${s.revenu_prevu.toFixed(2)} €` },
            ].map((c) => (
              <div key={c.label} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
                <p className="text-xs text-[var(--muted-foreground)]">{c.label}</p>
                <p className="mt-1 text-lg font-semibold tabular-nums">{c.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Nouveau shift */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <p className="text-sm font-semibold">Nouveau shift</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Date</span>
              <input type="date" value={form.date_jour} onChange={(e) => setForm({ ...form, date_jour: e.target.value })} className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Début</span>
              <input type="time" value={form.heure_debut} onChange={(e) => setForm({ ...form, heure_debut: e.target.value })} className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Fin</span>
              <input type="time" value={form.heure_fin} onChange={(e) => setForm({ ...form, heure_fin: e.target.value })} className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Pause (min)</span>
              <input type="number" min={0} value={form.pause_min} onChange={(e) => setForm({ ...form, pause_min: parseInt(e.target.value || "0", 10) })} className={inputCls} />
            </label>
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={submit}
              disabled={!form.date_jour || createM.isPending}
              className="rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] disabled:opacity-50"
            >
              Ajouter
            </button>
          </div>
        </div>

        {/* Liste des shifts */}
        {shifts.length === 0 ? (
          <EmptyState
            icon={<Briefcase className="h-6 w-6" />}
            title="Aucun shift ce mois-ci"
            description="Ajoute tes shifts pour calculer tes heures et tes revenus à venir."
          />
        ) : (
          <ul className="space-y-1.5">
            {shifts.map((shift) => (
              <li
                key={shift.id}
                className="flex flex-wrap items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm card-hover"
              >
                <span className="font-medium tabular-nums">{shift.date_jour}</span>
                <span className="text-[var(--muted-foreground)] tabular-nums">
                  {shift.heure_debut}–{shift.heure_fin}
                  {shift.pause_min > 0 && ` (pause ${shift.pause_min} min)`}
                </span>
                <span className="tabular-nums">{shift.heures} h</span>
                <select
                  value={shift.statut}
                  onChange={(e) => updateM.mutate({ id: shift.id, patch: { statut: e.target.value as WorkShift["statut"] } })}
                  className="ml-auto rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
                >
                  {Object.entries(STATUT_LABELS).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => deleteM.mutate(shift.id)}
                  aria-label="Supprimer le shift"
                  className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
