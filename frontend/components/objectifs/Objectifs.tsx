"use client";

import { useState } from "react";
import { ExternalLink, Target, Trash2 } from "lucide-react";
import type { LongTermGoal } from "@/lib/objectifs";
import { useCreateGoal, useDeleteGoal, useGoals, useUpdateGoal } from "@/lib/queries/objectifs";
import { ModuleHeader } from "@/components/layout";
import { EmptyState } from "@/components/ui/empty-state";

const inputCls =
  "w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";

const CATEGORIES: Record<LongTermGoal["categorie"], string> = {
  master: "Master",
  concours: "Concours",
  carriere: "Carrière",
  autre: "Autre",
};

const STATUTS: Record<LongTermGoal["statut"], string> = {
  veille: "Veille",
  preparation: "Préparation",
  candidature: "Candidature",
  obtenu: "Obtenu",
  abandonne: "Abandonné",
};

export function Objectifs() {
  const goalsQ = useGoals();
  const createM = useCreateGoal();
  const updateM = useUpdateGoal();
  const deleteM = useDeleteGoal();

  const [form, setForm] = useState({ titre: "", categorie: "autre", echeance: "", description: "" });

  if (goalsQ.isLoading) {
    return (
      <div className="p-6 space-y-4 animate-fade-in">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />
        ))}
      </div>
    );
  }
  if (goalsQ.isError) return <div className="p-6 text-[var(--destructive)]">⚠ {(goalsQ.error).message}</div>;

  const goals = goalsQ.data ?? [];
  const actifs = goals.filter((g) => g.statut !== "obtenu" && g.statut !== "abandonne");
  const clos = goals.filter((g) => g.statut === "obtenu" || g.statut === "abandonne");

  const submit = () => {
    if (!form.titre.trim()) return;
    createM.mutate(
      {
        titre: form.titre.trim(),
        categorie: form.categorie as LongTermGoal["categorie"],
        echeance: form.echeance || null,
        description: form.description.trim() || null,
      },
      { onSuccess: () => setForm({ titre: "", categorie: "autre", echeance: "", description: "" }) },
    );
  };

  const renderGoal = (g: LongTermGoal) => (
    <li key={g.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-2 card-hover">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{g.titre}</span>
        <span className="rounded-md bg-[var(--muted)] px-2 py-0.5 text-xs">{CATEGORIES[g.categorie]}</span>
        {g.echeance && <span className="text-xs text-[var(--muted-foreground)] tabular-nums">Échéance {g.echeance}</span>}
        {g.lien && (
          <a href={g.lien} target="_blank" rel="noreferrer" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]" aria-label="Ouvrir le lien">
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        )}
        <select
          value={g.statut}
          onChange={(e) => updateM.mutate({ id: g.id, patch: { statut: e.target.value as LongTermGoal["statut"] } })}
          className="ml-auto rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
        >
          {Object.entries(STATUTS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => deleteM.mutate(g.id)}
          aria-label="Supprimer l'objectif"
          className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"
        >
          <Trash2 className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      {g.description && <p className="text-sm text-[var(--muted-foreground)]">{g.description}</p>}
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          defaultValue={g.progression}
          onMouseUp={(e) => updateM.mutate({ id: g.id, patch: { progression: parseInt((e.target as HTMLInputElement).value, 10) } })}
          onTouchEnd={(e) => updateM.mutate({ id: g.id, patch: { progression: parseInt((e.target as HTMLInputElement).value, 10) } })}
          className="flex-1 accent-[var(--ring)]"
          aria-label="Progression"
        />
        <span className="w-10 text-right text-xs tabular-nums text-[var(--muted-foreground)]">{g.progression}%</span>
      </div>
    </li>
  );

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Objectifs long terme" subtitle="Masters, concours, opportunités en gestion d'actifs" />

      <div className="p-6 space-y-6 animate-fade-in-up">
        {/* Nouvel objectif */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <p className="text-sm font-semibold">Nouvel objectif</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="block sm:col-span-1">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Titre</span>
              <input value={form.titre} onChange={(e) => setForm({ ...form, titre: e.target.value })} placeholder="Master finance, gendarmerie…" className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Catégorie</span>
              <select value={form.categorie} onChange={(e) => setForm({ ...form, categorie: e.target.value })} className={inputCls}>
                {Object.entries(CATEGORIES).map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Échéance</span>
              <input type="date" value={form.echeance} onChange={(e) => setForm({ ...form, echeance: e.target.value })} className={inputCls} />
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Notes</span>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Dossier, prérequis, veille…" className={inputCls} />
          </label>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={submit}
              disabled={!form.titre.trim() || createM.isPending}
              className="rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] disabled:opacity-50"
            >
              Ajouter
            </button>
          </div>
        </div>

        {goals.length === 0 ? (
          <EmptyState
            icon={<Target className="h-6 w-6" />}
            title="Aucun objectif"
            description="Ajoute tes projets long terme : programmes de Master, concours, opportunités."
          />
        ) : (
          <>
            <ul className="space-y-2">{actifs.map(renderGoal)}</ul>
            {clos.length > 0 && (
              <details>
                <summary className="cursor-pointer text-sm text-[var(--muted-foreground)]">
                  Clos ({clos.length})
                </summary>
                <ul className="mt-2 space-y-2 opacity-70">{clos.map(renderGoal)}</ul>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  );
}
