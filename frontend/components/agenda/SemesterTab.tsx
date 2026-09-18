"use client";

/**
 * Onglet « Cours du semestre » — gère les récurrences de cours
 * (non-déplaçables dans le planificateur). CRUD via l'API /agenda/recurrences.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Trash2, Clock, MapPin } from "lucide-react";
import {
  fetchRecurrences,
  createRecurrence,
  deleteRecurrence,
} from "@/lib/agenda";
import type { RegleRecurrence } from "@/lib/agenda";
import { Skeleton } from "@/components/ui/skeleton";
import { CHART_SERIES } from "@/lib/design/colors";

const WEEKDAYS = [
  { value: 0, label: "Lundi" },
  { value: 1, label: "Mardi" },
  { value: 2, label: "Mercredi" },
  { value: 3, label: "Jeudi" },
  { value: 4, label: "Vendredi" },
  { value: 5, label: "Samedi" },
  { value: 6, label: "Dimanche" },
];

const COLORS = [
  { value: CHART_SERIES[0], label: "Bleu" },
  { value: CHART_SERIES[1], label: "Or" },
  { value: CHART_SERIES[2], label: "Vert" },
  { value: CHART_SERIES[3], label: "Bordeaux" },
  { value: CHART_SERIES[4], label: "Ardoise" },
  { value: CHART_SERIES[5], label: "Ocre" },
];

function CourseList({ loading, rules, onDelete }: { loading: boolean; rules: RegleRecurrence[]; onDelete: (id: number) => void }) {
  if (loading) return <Skeleton lines={3} />;
  if (rules.length === 0) return <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">Aucun cours enregistré. Ajoute ton premier cours du semestre ci-dessus.</p>;
  return <ul className="space-y-2">{rules.map((rule) => <CourseRow key={rule.id} rule={rule} onDelete={onDelete} />)}</ul>;
}

function CourseRow({ rule, onDelete }: { rule: RegleRecurrence; onDelete: (id: number) => void }) {
  const weekday = WEEKDAYS.find((day) => day.value === rule.weekdays[0])?.label;
  return <li className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5"><span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: rule.couleur || CHART_SERIES[0] }} aria-hidden="true" title={rule.couleur || ""} /><span className="flex-1 text-sm font-medium">{rule.titre}</span><span className="text-xs text-[var(--muted-foreground)]">{weekday}</span><span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]"><Clock className="h-3 w-3" aria-hidden="true" />{rule.start_time} – {rule.end_time}</span><CoursePlace lieu={rule.lieu} /><CourseEnd until={rule.until} /><button type="button" onClick={() => onDelete(rule.id)} aria-label={`Supprimer ${rule.titre}`} className="shrink-0 rounded p-1 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"><Trash2 className="h-4 w-4" aria-hidden="true" /></button></li>;
}

function CoursePlace({ lieu }: { lieu: string | null }) {
  if (!lieu) return null;
  return <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]"><MapPin className="h-3 w-3" aria-hidden="true" />{lieu}</span>;
}

function CourseEnd({ until }: { until: string | null }) {
  if (!until) return null;
  return <span className="text-xs text-[var(--muted-foreground)]">Jusqu'au {until}</span>;
}

export default function SemesterTab() {
  const qc = useQueryClient();
  const { data: rules, isLoading } = useQuery({
    queryKey: ["agenda", "recurrences"],
    queryFn: fetchRecurrences,
  });

  const createMut = useMutation({
    mutationFn: createRecurrence,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agenda", "recurrences"] });
      toast.success("Cours ajouté.");
    },
    onError: () => toast.error("Échec de l'ajout."),
  });

  const deleteMut = useMutation({
    mutationFn: deleteRecurrence,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agenda", "recurrences"] });
      toast.success("Cours supprimé.");
    },
    onError: () => toast.error("Échec de la suppression."),
  });

  const [form, setForm] = useState({
    titre: "",
    day: 0,
    start: "09:00",
    end: "11:00",
    lieu: "",
    couleur: CHART_SERIES[0],
    until: "",
  });

  const coursRules = (rules ?? []).filter((r) => r.categorie === "cours");

  function submit() {
    if (!form.titre.trim()) return;
    createMut.mutate({
      titre: form.titre.trim(),
      weekdays: [form.day],
      start_time: form.start,
      end_time: form.end,
      lieu: form.lieu.trim() || null,
      categorie: "cours",
      couleur: form.couleur,
      until: form.until || null,
    });
    setForm((f) => ({ ...f, titre: "", lieu: "" }));
  }

  const inputCls =
    "rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]";

  return (
    <div className="space-y-6">
      <p className="text-sm text-[var(--muted-foreground)]">
        Les cours sont des plages <strong>non-déplaçables</strong> dans le
        planificateur. Ajoute chaque cours du semestre (un par ligne).
      </p>

      {/* Formulaire rapide */}
      <div className="flex flex-wrap items-end gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <label className="flex-1 min-w-[140px]">
          <span className="text-xs text-[var(--muted-foreground)]">Nom</span>
          <input
            value={form.titre}
            onChange={(e) => setForm((f) => ({ ...f, titre: e.target.value }))}
            placeholder="Mathématiques"
            className={`${inputCls} w-full`}
          />
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Jour</span>
          <select
            value={form.day}
            onChange={(e) => setForm((f) => ({ ...f, day: Number(e.target.value) }))}
            className={`${inputCls} w-full`}
          >
            {WEEKDAYS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Début</span>
          <input
            type="time"
            value={form.start}
            onChange={(e) => setForm((f) => ({ ...f, start: e.target.value }))}
            className={`${inputCls} w-full`}
          />
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Fin</span>
          <input
            type="time"
            value={form.end}
            onChange={(e) => setForm((f) => ({ ...f, end: e.target.value }))}
            className={`${inputCls} w-full`}
          />
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Lieu</span>
          <input
            value={form.lieu}
            onChange={(e) => setForm((f) => ({ ...f, lieu: e.target.value }))}
            placeholder="Salle B-12"
            className={`${inputCls} w-[100px]`}
          />
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Couleur</span>
          <select
            value={form.couleur}
            onChange={(e) => setForm((f) => ({ ...f, couleur: e.target.value }))}
            className={`${inputCls} w-full`}
          >
            {COLORS.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="text-xs text-[var(--muted-foreground)]">Fin semestre</span>
          <input
            type="date"
            value={form.until}
            onChange={(e) => setForm((f) => ({ ...f, until: e.target.value }))}
            className={`${inputCls} w-full`}
          />
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={createMut.isPending || !form.titre.trim()}
          className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          <Plus className="mr-1 inline h-3.5 w-3.5" />
          Ajouter
        </button>
      </div>

      <CourseList loading={isLoading} rules={coursRules} onDelete={(id) => deleteMut.mutate(id)} />
    </div>
  );
}
