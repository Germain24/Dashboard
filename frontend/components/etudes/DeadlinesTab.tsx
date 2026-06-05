"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { fetchDeadlines, fetchCours, createEvaluation, deleteEvaluation, type Evaluation, type Cours } from "@/lib/etudes";
import { Skeleton } from "@/components/ui/skeleton";

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
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ cours_id: "", titre: "", type_eval: "devoir", date_limite: "" });
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const load = useCallback(() => {
    let active = true;
    Promise.all([fetchDeadlines(90), fetchCours()])
      .then(([dl, cl]) => { if (active) { setDeadlines(dl); setCours(cl); setStatus("ready"); } })
      .catch(() => active && setStatus("error"));
    return () => { active = false; };
  }, []);
  useEffect(() => load(), [load]);

  const handleAdd = async () => {
    if (!form.cours_id || !form.titre) return;
    try {
      await createEvaluation({
        cours_id: Number(form.cours_id),
        titre: form.titre,
        type_eval: form.type_eval,
        date_limite: form.date_limite || undefined,
      });
      setForm({ cours_id: "", titre: "", type_eval: "devoir", date_limite: "" });
      setAdding(false);
      load();
    } catch {
      toast.error("Impossible de créer l'évaluation.");
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteEvaluation(id);
      load();
    } catch {
      setConfirmId(null);
      toast.error("Suppression impossible.");
    }
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
            <label htmlFor="dl-cours" className="w-24 shrink-0 text-[var(--muted-foreground)]">Cours</label>
            <select id="dl-cours" className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.cours_id} onChange={e => setForm(f => ({ ...f, cours_id: e.target.value }))}>
              <option value="">— choisir —</option>
              {cours.map(c => <option key={c.id} value={c.id}>{c.code} — {c.nom}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="dl-titre" className="w-24 shrink-0 text-[var(--muted-foreground)]">Titre</label>
            <input id="dl-titre" className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ex: Examen final"
              value={form.titre} onChange={e => setForm(f => ({ ...f, titre: e.target.value }))} />
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="dl-type" className="w-24 shrink-0 text-[var(--muted-foreground)]">Type</label>
            <select id="dl-type" className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.type_eval} onChange={e => setForm(f => ({ ...f, type_eval: e.target.value }))}>
              {["exam","devoir","quiz","projet","autre"].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="dl-date" className="w-24 shrink-0 text-[var(--muted-foreground)]">Date limite</label>
            <input id="dl-date" type="date" className="border rounded px-2 py-1 bg-transparent"
              value={form.date_limite} onChange={e => setForm(f => ({ ...f, date_limite: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Créer + tâche Agenda</button>
        </div>
      )}

      <div className="space-y-2">
        {status === "loading" && <Skeleton lines={4} />}

        {status === "error" && (
          <div className="flex flex-col items-start gap-2 py-2">
            <p className="text-sm text-[var(--muted-foreground)]">Deadlines indisponibles pour le moment.</p>
            <button onClick={() => { setStatus("loading"); load(); }}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--accent)]">
              Réessayer
            </button>
          </div>
        )}

        {status === "ready" && deadlines.length === 0 && (
          <p className="text-[var(--muted-foreground)] text-sm">Aucune deadline dans les 90 prochains jours.</p>
        )}

        {status === "ready" && deadlines.map(ev => (
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
            {confirmId === ev.id ? (
              <span className="flex shrink-0 items-center gap-1">
                <button onClick={() => void remove(ev.id)} aria-label="Confirmer la suppression"
                  className="text-xs font-medium text-[var(--destructive)]">Supprimer</button>
                <button onClick={() => setConfirmId(null)} aria-label="Annuler"
                  className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">✕</button>
              </span>
            ) : (
              <button onClick={() => setConfirmId(ev.id)} aria-label="Supprimer l'évaluation"
                className="shrink-0 text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
