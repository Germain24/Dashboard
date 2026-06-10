"use client";
/**
 * TachesTab — liste des tâches triées par urgence + formulaire d'ajout.
 */

import { useState } from "react";
import type { Tache, TacheCreate } from "@/lib/agenda";
import { useAgendaTasks, useCreateTask, useDeleteTask, useMarkTaskDone } from "@/lib/queries/agenda";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

const PRIORITE_LABELS: Record<number, string> = {
  1: "🔴 Très haute",
  2: "🟠 Haute",
  3: "🟡 Normale",
  4: "🟢 Basse",
  5: "⚪ Très basse",
};

function TacheRow({ t, onDone, onDelete }: {
  t: Tache;
  onDone: (id: number) => void;
  onDelete: (id: number) => void;
}) {
  const overdue =
    t.deadline &&
    t.deadline < new Date().toISOString().split("T")[0] &&
    t.statut === "todo";

  return (
    <div
      className={cn(
        "flex items-start gap-3 p-3 rounded-[var(--radius)] border mb-2",
        overdue
          ? "border-[var(--destructive-muted)] bg-[var(--destructive-muted)]"
          : "border-[var(--border)] bg-[var(--card)]",
      )}
    >
      <button
        onClick={() => onDone(t.id)}
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0 rounded-full border-2 transition-colors",
          t.statut === "done"
            ? "bg-[var(--success)] border-[var(--success)]"
            : "border-[var(--muted-foreground)] hover:border-[var(--success)]",
        )}
        title="Marquer comme fait"
      />
      <div className="flex-1 min-w-0">
        <div
          className={cn(
            "text-sm font-medium",
            t.statut === "done" ? "line-through text-[var(--muted-foreground)]" : "text-[var(--foreground)]",
          )}
        >
          {t.titre}
        </div>
        <div className="flex flex-wrap gap-2 mt-1 text-xs text-[var(--muted-foreground)]">
          <span>{PRIORITE_LABELS[t.priorite]}</span>
          {t.deadline && (
            <span className={overdue ? "text-[var(--destructive)] font-semibold" : ""}>
              📅 {t.deadline}
            </span>
          )}
          {t.categorie && (
            <span className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-1.5 py-0.5">
              {t.categorie}
            </span>
          )}
          {t.duree_estimee_min && <span>⏱ {t.duree_estimee_min} min</span>}
        </div>
        {t.note && (
          <p className="text-xs text-[var(--muted-foreground)] mt-1 italic">{t.note}</p>
        )}
      </div>
      <button
        onClick={() => onDelete(t.id)}
        className="text-[var(--border)] hover:text-[var(--destructive)] text-lg leading-none transition-colors"
        aria-label="Supprimer"
      >
        ×
      </button>
    </div>
  );
}

export default function TachesTab() {
  const [filter, setFilter] = useState<"todo" | "done" | "all">("todo");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TacheCreate>({ titre: "", priorite: 3 });

  const tasksQ = useAgendaTasks(filter === "all" ? undefined : filter);
  const tasks: Tache[] = tasksQ.data ?? [];
  const loading = tasksQ.isLoading;
  const createMutation = useCreateTask();
  const doneMutation = useMarkTaskDone();
  const deleteMutation = useDeleteTask();

  function handleCreate() {
    if (!form.titre.trim()) return;
    createMutation.mutate(form, {
      onSuccess: () => {
        setForm({ titre: "", priorite: 3 });
        setShowForm(false);
      },
    });
  }

  function handleDone(id: number) {
    doneMutation.mutate(id);
  }

  function handleDelete(id: number) {
    deleteMutation.mutate(id);
  }

  return (
    <div className="space-y-4">
      {/* Filtres + bouton ajouter */}
      <div className="flex items-center gap-2">
        <div className="flex rounded-[var(--radius)] border border-[var(--border)] overflow-hidden text-sm">
          {(["todo", "done", "all"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1.5 transition-colors",
                filter === f
                  ? "bg-[var(--primary)] text-[var(--primary-foreground)]"
                  : "bg-transparent text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]",
              )}
            >
              {f === "todo" ? "À faire" : f === "done" ? "Fait" : "Tout"}
            </button>
          ))}
        </div>
        <Button
          size="sm"
          className="ml-auto"
          onClick={() => setShowForm((f) => !f)}
        >
          + Ajouter
        </Button>
      </div>

      {/* Formulaire d'ajout */}
      {showForm && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--muted)] p-4 space-y-3">
          <Input
            placeholder="Titre de la tâche *"
            value={form.titre}
            onChange={(e) => setForm((f) => ({ ...f, titre: e.target.value }))}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Deadline"
              type="date"
              value={form.deadline || ""}
              onChange={(e) => setForm((f) => ({ ...f, deadline: e.target.value || null }))}
            />
            <Select
              label="Priorité"
              value={String(form.priorite)}
              onChange={(e) => setForm((f) => ({ ...f, priorite: +e.target.value }))}
            >
              {[1, 2, 3, 4, 5].map((p) => (
                <option key={p} value={p}>{PRIORITE_LABELS[p]}</option>
              ))}
            </Select>
          </div>
          <Input
            placeholder="Catégorie (ex: etudes, courses…)"
            value={form.categorie || ""}
            onChange={(e) => setForm((f) => ({ ...f, categorie: e.target.value || null }))}
          />
          <Textarea
            placeholder="Note (optionnel)"
            rows={2}
            value={form.note || ""}
            onChange={(e) => setForm((f) => ({ ...f, note: e.target.value || null }))}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreate}>Créer</Button>
            <Button variant="secondary" size="sm" onClick={() => setShowForm(false)}>Annuler</Button>
          </div>
        </div>
      )}

      {loading && <Spinner size="sm" label="Chargement…" />}

      {!loading && tasks.length === 0 && (
        <EmptyState
          title={`Aucune tâche ${filter === "todo" ? "à faire" : ""}`}
          description="Appuie sur + Ajouter pour en créer une."
        />
      )}

      {tasks.map((t) => (
        <TacheRow key={t.id} t={t} onDone={handleDone} onDelete={handleDelete} />
      ))}
    </div>
  );
}
