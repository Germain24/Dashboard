"use client";
import { useEffect, useState } from "react";
import { fetchDeadlines, fetchCours, createEvaluation, deleteEvaluation, type Evaluation, type Cours } from "@/lib/etudes";

const URGENCE_COLOR = (j: number | undefined) => {
  if (j == null) return "text-[var(--muted-foreground)]";
  if (j <= 3) return "text-[var(--destructive)] font-semibold";
  if (j <= 7) return "text-[var(--warning)]";
  if (j <= 14) return "text-[var(--warning)]";
  return "text-[var(--muted-foreground)]";
};

export function DeadlinesTab() {
  const [deadlines, setDeadlines] = useState<Evaluation[]>([]);
  const [cours, setCours] = useState<Cours[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ cours_id: "", titre: "", type_eval: "devoir", date_limite: "" });

  const load = async () => {
    const [dl, cl] = await Promise.all([fetchDeadlines(90), fetchCours()]);
    setDeadlines(dl);
    setCours(cl);
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!form.cours_id || !form.titre) return;
    await createEvaluation({
      cours_id: Number(form.cours_id),
      titre: form.titre,
      type_eval: form.type_eval,
      date_limite: form.date_limite || undefined,
    });
    setForm({ cours_id: "", titre: "", type_eval: "devoir", date_limite: "" });
    setAdding(false);
    load();
  };

  const coursMap = Object.fromEntries(cours.map(c => [c.id, c.code]));

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-medium text-sm text-[var(--muted-foreground)]">Évaluations à venir (90 j)</h3>
        <button onClick={() => setAdding(a => !a)}
          className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">
          {adding ? "Annuler" : "+ Ajouter"}
        </button>
      </div>

      {adding && (
        <div className="border rounded p-3 space-y-2 text-sm bg-[var(--card)]">
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Cours</label>
            <select className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.cours_id} onChange={e => setForm(f => ({ ...f, cours_id: e.target.value }))}>
              <option value="">— choisir —</option>
              {cours.map(c => <option key={c.id} value={c.id}>{c.code} — {c.nom}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Titre</label>
            <input className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ex: Examen final"
              value={form.titre} onChange={e => setForm(f => ({ ...f, titre: e.target.value }))} />
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Type</label>
            <select className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.type_eval} onChange={e => setForm(f => ({ ...f, type_eval: e.target.value }))}>
              {["exam","devoir","quiz","projet","autre"].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Date limite</label>
            <input type="date" className="border rounded px-2 py-1 bg-transparent"
              value={form.date_limite} onChange={e => setForm(f => ({ ...f, date_limite: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Créer + tâche Agenda</button>
        </div>
      )}

      <div className="space-y-2">
        {deadlines.length === 0 && <p className="text-[var(--muted-foreground)] text-sm">Aucune deadline dans les 90 prochains jours.</p>}
        {deadlines.map(ev => (
          <div key={ev.id} className="border rounded p-3 flex items-center gap-3 bg-[var(--card)]">
            <div className="w-2 h-2 rounded-full bg-[var(--ring)] shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-medium text-sm">{coursMap[ev.cours_id] ?? `#${ev.cours_id}`} — {ev.titre}</div>
              <div className="text-xs text-[var(--muted-foreground)]">
                {ev.type_eval} · {ev.date_limite ?? "sans date"}
                {ev.note_obtenue != null && ` · ${ev.note_obtenue}/${ev.note_max ?? 100}`}
              </div>
            </div>
            <span className={`text-xs ${URGENCE_COLOR(ev.jours_restants)}`}>
              {ev.jours_restants != null ? (ev.jours_restants === 0 ? "Aujourd'hui" : `J-${ev.jours_restants}`) : "—"}
            </span>
            <button onClick={async () => { await deleteEvaluation(ev.id); load(); }}
              aria-label="Supprimer l'évaluation"
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
