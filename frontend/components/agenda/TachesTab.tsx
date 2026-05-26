"use client";
/**
 * TachesTab — liste des tâches triées par urgence + formulaire d'ajout.
 */

import { useEffect, useState } from "react";
import type { Tache, TacheCreate } from "@/lib/agenda";
import { createTask, deleteTask, fetchTasks, markTaskDone } from "@/lib/agenda";

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
  const overdue = t.deadline && t.deadline < new Date().toISOString().split("T")[0] && t.statut === "todo";
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${overdue ? "border-red-200 bg-red-50" : "border-gray-100 bg-white"} mb-2`}>
      <button
        onClick={() => onDone(t.id)}
        className={`mt-0.5 w-5 h-5 rounded-full border-2 flex-shrink-0 ${t.statut === "done" ? "bg-green-500 border-green-500" : "border-gray-400 hover:border-green-500"}`}
        title="Marquer comme fait"
      />
      <div className="flex-1 min-w-0">
        <div className={`font-medium text-sm ${t.statut === "done" ? "line-through text-gray-400" : ""}`}>
          {t.titre}
        </div>
        <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-500">
          <span>{PRIORITE_LABELS[t.priorite]}</span>
          {t.deadline && (
            <span className={overdue ? "text-red-600 font-semibold" : ""}>
              📅 {t.deadline}
            </span>
          )}
          {t.categorie && <span className="bg-gray-100 px-1 rounded">{t.categorie}</span>}
          {t.duree_estimee_min && <span>⏱ {t.duree_estimee_min} min</span>}
        </div>
        {t.note && <div className="text-xs text-gray-400 mt-1 italic">{t.note}</div>}
      </div>
      <button onClick={() => onDelete(t.id)} className="text-gray-300 hover:text-red-400 text-lg">×</button>
    </div>
  );
}

export default function TachesTab() {
  const [tasks, setTasks] = useState<Tache[]>([]);
  const [filter, setFilter] = useState<"todo" | "done" | "all">("todo");
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<TacheCreate>({ titre: "", priorite: 3 });

  function loadTasks() {
    setLoading(true);
    fetchTasks(filter === "all" ? undefined : filter)
      .then(setTasks)
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadTasks(); }, [filter]);

  async function handleCreate() {
    if (!form.titre.trim()) return;
    await createTask(form);
    setForm({ titre: "", priorite: 3 });
    setShowForm(false);
    loadTasks();
  }

  async function handleDone(id: number) {
    await markTaskDone(id);
    loadTasks();
  }

  async function handleDelete(id: number) {
    await deleteTask(id);
    loadTasks();
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex rounded border overflow-hidden text-sm">
          {(["todo", "done", "all"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 ${filter === f ? "bg-blue-600 text-white" : "bg-white hover:bg-gray-50"}`}
            >
              {f === "todo" ? "À faire" : f === "done" ? "Fait" : "Tout"}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowForm(f => !f)}
          className="ml-auto px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
        >
          + Ajouter
        </button>
      </div>

      {/* Formulaire d'ajout */}
      {showForm && (
        <div className="mb-4 p-4 border rounded-lg bg-gray-50 space-y-3">
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Titre de la tâche *"
            value={form.titre}
            onChange={e => setForm(f => ({ ...f, titre: e.target.value }))}
          />
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-gray-500">Deadline</label>
              <input type="date" className="w-full border rounded px-2 py-1 text-sm mt-0.5"
                value={form.deadline || ""} onChange={e => setForm(f => ({ ...f, deadline: e.target.value || null }))} />
            </div>
            <div>
              <label className="text-xs text-gray-500">Priorité</label>
              <select className="w-full border rounded px-2 py-1 text-sm mt-0.5"
                value={form.priorite} onChange={e => setForm(f => ({ ...f, priorite: +e.target.value }))}>
                {[1,2,3,4,5].map(p => <option key={p} value={p}>{PRIORITE_LABELS[p]}</option>)}
              </select>
            </div>
          </div>
          <input className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Catégorie (ex: etudes, courses…)"
            value={form.categorie || ""} onChange={e => setForm(f => ({ ...f, categorie: e.target.value || null }))} />
          <textarea className="w-full border rounded px-3 py-2 text-sm" rows={2}
            placeholder="Note (optionnel)"
            value={form.note || ""} onChange={e => setForm(f => ({ ...f, note: e.target.value || null }))} />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Créer</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-1.5 border rounded text-sm hover:bg-gray-50">Annuler</button>
          </div>
        </div>
      )}

      {loading && <div className="text-sm text-gray-400">Chargement…</div>}
      {!loading && tasks.length === 0 && (
        <div className="text-center text-gray-400 py-12 text-sm">Aucune tâche {filter === "todo" ? "à faire" : ""}</div>
      )}
      {tasks.map(t => <TacheRow key={t.id} t={t} onDone={handleDone} onDelete={handleDelete} />)}
    </div>
  );
}
