import { useState } from "react";
import { Plus, Target, Trash2, X } from "lucide-react";
import type { LifeGoal, LifeGoalMetric, LifeGoalSub } from "@/lib/routines";
import type { useCreateLifeGoal, useDeleteLifeGoal } from "@/lib/queries/routines";

export type Sub = { label: string; metric: string; baseline: string; cible: string; date: string };
type CreateMutation = ReturnType<typeof useCreateLifeGoal>;
type DeleteMutation = ReturnType<typeof useDeleteLifeGoal>;

const emptySub = (metric: string): Sub => ({ label: "", metric, baseline: "", cible: "", date: "" });

export function useLifeGoalForm(metrics: LifeGoalMetric[] | undefined, create: CreateMutation) {
  const [open, setOpen] = useState(false);
  const [titre, setTitre] = useState("");
  const [subs, setSubs] = useState<Sub[]>([emptySub(metrics?.[0]?.metric ?? "poids")]);
  const addSub = () => setSubs((previous) => [...previous, emptySub(metrics?.[0]?.metric ?? "poids")]);
  const setSub = (index: number, patch: Partial<Sub>) =>
    setSubs((previous) => previous.map((sub, current) => (current === index ? { ...sub, ...patch } : sub)));
  const removeSub = (index: number) => setSubs((previous) => previous.filter((_, current) => current !== index));
  const reset = () => {
    setOpen(false);
    setTitre("");
    setSubs([emptySub(metrics?.[0]?.metric ?? "poids")]);
  };
  const submit = () => {
    const objectifs = buildObjectives(subs);
    if (!isValidGoal(titre, objectifs)) return;
    create.mutate({ titre: titre.trim(), objectifs }, { onSuccess: reset });
  };
  return { open, setOpen, titre, setTitre, subs, metrics, addSub, setSub, removeSub, submit, reset, create };
}

function buildObjectives(subs: Sub[]) {
  return subs
    .filter((sub) => sub.label.trim() && sub.cible !== "")
    .map((sub) => ({
      label: sub.label.trim(),
      metric: sub.metric,
      baseline: Number(sub.baseline || 0),
      cible: Number(sub.cible),
      date: sub.date || null,
    }));
}

function isValidGoal(title: string, objectives: ReturnType<typeof buildObjectives>): boolean {
  return Boolean(title.trim()) && objectives.length > 0;
}

export function LifeGoalsSection({
  goals,
  del,
  form,
}: {
  goals: LifeGoal[] | undefined;
  del: DeleteMutation;
  form: ReturnType<typeof useLifeGoalForm>;
}) {
  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
      <LifeGoalsHeader onOpen={() => form.setOpen(true)} />
      <LifeGoalsList goals={goals} onDelete={(id) => del.mutate(id)} />
      {form.open && <LifeGoalModal form={form} />}
    </section>
  );
}

function LifeGoalsHeader({ onOpen }: { onOpen: () => void }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <Target size={13} /> Objectifs de vie
      </h2>
      <button onClick={onOpen} className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        <Plus size={13} /> Nouvel objectif
      </button>
    </div>
  );
}

function LifeGoalsList({ goals, onDelete }: { goals: LifeGoal[] | undefined; onDelete: (id: number) => void }) {
  if (!goals || goals.length === 0) {
    return <p className="text-sm text-[var(--muted-foreground)]">Aucun objectif. Crée-en un (ex. « −5 kg + 2000 € »).</p>;
  }
  return (
    <ul className="space-y-4">
      {goals.map((goal) => <LifeGoalItem key={goal.id} goal={goal} onDelete={onDelete} />)}
    </ul>
  );
}

function LifeGoalItem({ goal, onDelete }: { goal: LifeGoal; onDelete: (id: number) => void }) {
  return (
    <li>
      <div className="flex items-center gap-2">
        <span className="flex-1 font-medium text-[var(--foreground)]">{goal.titre}</span>
        {goal.jalons_en_retard > 0 && <LateMilestones count={goal.jalons_en_retard} />}
        {goal.pct_global != null && <span className="tabular-nums text-sm text-[var(--muted-foreground)]">{goal.pct_global}%</span>}
        <button onClick={() => onDelete(goal.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={14} /></button>
      </div>
      {goal.pct_global != null && <ProgressBar value={goal.pct_global} />}
      <ul className="mt-2 space-y-1.5 pl-1">
        {goal.objectifs.map((objective, index) => <LifeGoalSubItem key={index} objective={objective} />)}
      </ul>
    </li>
  );
}

function LateMilestones({ count }: { count: number }) {
  return <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-700 dark:text-amber-300">{count} jalon{count > 1 ? "s" : ""} en retard</span>;
}

function ProgressBar({ value }: { value: number }) {
  return <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]"><div className="h-full rounded-full bg-[var(--ring)] bar-fill" style={{ width: `${value}%` }} /></div>;
}

const STATUS_BADGE: Record<LifeGoalSub["statut"], { label: string; cls: string } | null> = {
  atteint: { label: "Atteint", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  en_retard: { label: "En retard", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  a_venir: null,
};

function LifeGoalSubItem({ objective }: { objective: LifeGoalSub }) {
  const badge = STATUS_BADGE[objective.statut];
  return (
    <li className="text-xs">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-[var(--muted-foreground)]">
        <span className="flex flex-wrap items-center gap-1.5">
          {objective.label}
          {objective.date && <span className="tabular-nums opacity-75">{objective.date}</span>}
          {badge && <span className={`rounded-full px-1.5 py-0.5 ${badge.cls}`}>{badge.label}</span>}
        </span>
        <span className="tabular-nums">{objective.courant ?? "—"} / {objective.cible} {objective.pct != null && `(${objective.pct}%)`}</span>
      </div>
    </li>
  );
}

function LifeGoalModal({ form }: { form: ReturnType<typeof useLifeGoalForm> }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-xl">
        <ModalHeader onClose={() => form.setOpen(false)} />
        <input value={form.titre} onChange={(event) => form.setTitre(event.target.value)} placeholder="Titre (ex. Forme & épargne T3)" className="mb-3 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
        <div className="space-y-2">
          {form.subs.map((sub, index) => <SubGoalRow key={index} sub={sub} index={index} metrics={form.metrics} canRemove={form.subs.length > 1} setSub={form.setSub} removeSub={form.removeSub} />)}
          <button onClick={form.addSub} className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><Plus size={12} /> Ajouter un sous-objectif</button>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => form.setOpen(false)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">Annuler</button>
          <button onClick={form.submit} disabled={form.create?.isPending} className="rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">Créer</button>
        </div>
      </div>
    </div>
  );
}

function ModalHeader({ onClose }: { onClose: () => void }) {
  return <div className="mb-3 flex items-center justify-between"><h3 className="font-semibold">Nouvel objectif de vie</h3><button onClick={onClose} aria-label="Fermer"><X size={16} /></button></div>;
}

function SubGoalRow({ sub, index, metrics, canRemove, setSub, removeSub }: { sub: Sub; index: number; metrics: LifeGoalMetric[] | undefined; canRemove: boolean; setSub: (index: number, patch: Partial<Sub>) => void; removeSub: (index: number) => void }) {
  const update = (patch: Partial<Sub>) => setSub(index, patch);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <input value={sub.label} onChange={(event) => update({ label: event.target.value })} placeholder="Sous-objectif" className="min-w-28 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
      <select value={sub.metric} onChange={(event) => update({ metric: event.target.value })} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
        {metrics?.map((metric) => <option key={metric.metric} value={metric.metric}>{metric.label}</option>)}
      </select>
      <input type="number" value={sub.baseline} onChange={(event) => update({ baseline: event.target.value })} placeholder="départ" className="w-20 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
      <input type="number" value={sub.cible} onChange={(event) => update({ cible: event.target.value })} placeholder="cible" className="w-20 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
      <input type="date" value={sub.date} onChange={(event) => update({ date: event.target.value })} aria-label="Échéance du jalon (optionnelle)" className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
      {canRemove && <button onClick={() => removeSub(index)} aria-label="Retirer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={13} /></button>}
    </div>
  );
}
