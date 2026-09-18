"use client";
import { useState } from "react";
import { toast } from "sonner";
import type { Cours, SessionEtude } from "@/lib/etudes";
import { useCours, useCreateEtudesSession, useDeleteEtudesSession, useEtudesSessions } from "@/lib/queries/etudes";
import { planFocus } from "@/lib/agenda";
import { Skeleton } from "@/components/ui/skeleton";
import { PomodoroTimer } from "./PomodoroTimer";

export function SessionsTab() {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ cours_id: "", duree_min: "25", sujet: "", note: "" });
  const [focusMsg, setFocusMsg] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const sessionsQ = useEtudesSessions();
  const coursQ = useCours();
  const sessions: SessionEtude[] = sessionsQ.data ?? [];
  const cours: Cours[] = coursQ.data ?? [];
  const status: "loading" | "error" | "ready" =
    sessionsQ.isLoading || coursQ.isLoading ? "loading"
    : sessionsQ.isError || coursQ.isError ? "error" : "ready";
  const createMutation = useCreateEtudesSession();
  const deleteMutation = useDeleteEtudesSession();

  const handleAdd = () => {
    if (!form.duree_min) return;
    createMutation.mutate(
      {
        cours_id: form.cours_id ? Number(form.cours_id) : undefined,
        duree_min: Number(form.duree_min),
        sujet: form.sujet || undefined,
        note: form.note || undefined,
      },
      {
        onSuccess: () => {
          setForm({ cours_id: "", duree_min: "25", sujet: "", note: "" });
          setAdding(false);
        },
        onError: () => toast.error("Impossible d'enregistrer la session."),
      },
    );
  };

  const remove = (id: number) => {
    deleteMutation.mutate(id, {
      onError: () => {
        setConfirmId(null);
        toast.error("Suppression impossible.");
      },
    });
  };

  const handlePlanFocus = async () => {
    setPlanning(true);
    setFocusMsg(null);
    try {
      const coursCode = form.cours_id ? cours.find(c => String(c.id) === form.cours_id)?.code : undefined;
      const ev = await planFocus({ duree_min: Number(form.duree_min) || 60, cours: coursCode });
      const h = new Date(ev.debut).toLocaleTimeString("fr-CA", { hour: "2-digit", minute: "2-digit" });
      setFocusMsg(`✓ Bloc focus planifié à ${h} dans l'agenda.`);
    } catch {
      setFocusMsg("Aucun créneau libre suffisant aujourd'hui.");
    } finally {
      setPlanning(false);
    }
  };

  const coursMap = Object.fromEntries(cours.map(c => [c.id, c.code]));
  const sujetsReutilisables = Array.from(
    new Set(sessions.map(s => s.sujet).filter((x): x is string => !!x)),
  ).slice(0, 30);
  const totalMin = sessions.reduce((s, se) => s + se.duree_min, 0);
  const totalH = Math.floor(totalMin / 60);
  const totalRem = totalMin % 60;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-sm text-[var(--muted-foreground)]">
          Total : <span className="text-[var(--foreground)] font-semibold">{totalH}h{totalRem > 0 ? `${totalRem}min` : ""}</span>
        </div>
        <div className="flex gap-2">
          <button onClick={handlePlanFocus} disabled={planning}
            title="Planifie un bloc focus dans le prochain créneau libre de l'agenda"
            className="px-3 py-1 border border-[var(--border)] text-[var(--foreground)] rounded text-sm hover:bg-[var(--accent)] disabled:opacity-50">
            {planning ? "…" : "📅 Planifier un focus"}
          </button>
          <button onClick={() => setAdding(a => !a)}
            className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">
            {adding ? "Annuler" : "+ Session"}
          </button>
        </div>
      </div>
      {focusMsg && <div className="text-xs text-[var(--muted-foreground)]">{focusMsg}</div>}

      <PomodoroTimer cours={cours} onLogged={() => {}} />

      {adding && (
        <div className="border rounded p-3 space-y-2 text-sm bg-[var(--card)]">
          <div className="flex gap-2 items-center">
            <label htmlFor="sess-cours" className="w-24 shrink-0 text-[var(--muted-foreground)]">Cours</label>
            <select id="sess-cours" className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.cours_id} onChange={e => setForm(f => ({ ...f, cours_id: e.target.value }))}>
              <option value="">— libre —</option>
              {cours.map(c => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="sess-duree" className="w-24 shrink-0 text-[var(--muted-foreground)]">Durée (min)</label>
            <input id="sess-duree" type="number" className="w-20 border rounded px-2 py-1 bg-transparent"
              value={form.duree_min} onChange={e => setForm(f => ({ ...f, duree_min: e.target.value }))} />
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="sess-sujet" className="w-24 shrink-0 text-[var(--muted-foreground)]">Sujet</label>
            <input id="sess-sujet" list="sujets-reutilisables" className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ex: Révision Ch.3"
              value={form.sujet} onChange={e => setForm(f => ({ ...f, sujet: e.target.value }))} />
            <datalist id="sujets-reutilisables">
              {sujetsReutilisables.map(s => <option key={s} value={s} />)}
            </datalist>
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="sess-note" className="w-24 shrink-0 text-[var(--muted-foreground)]">Note</label>
            <input id="sess-note" className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ressenti, bilan..."
              value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Enregistrer</button>
        </div>
      )}

      <div className="space-y-2">
        {status === "loading" && <Skeleton lines={4} />}

        {status === "error" && (
          <div className="flex flex-col items-start gap-2 py-2">
            <p className="text-sm text-[var(--muted-foreground)]">Sessions indisponibles pour le moment.</p>
            <button onClick={() => { void sessionsQ.refetch(); void coursQ.refetch(); }}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--accent)]">
              Réessayer
            </button>
          </div>
        )}

        {status === "ready" && sessions.length === 0 && (
          <p className="text-[var(--muted-foreground)] text-sm">Aucune session enregistrée.</p>
        )}

        {status === "ready" && sessions.map(se => (
          <div key={se.id} className="border rounded p-3 flex items-start gap-3 bg-[var(--card)]">
            <div className="text-[var(--ring)] font-mono text-sm shrink-0 pt-0.5">
              {se.duree_min >= 60
                ? `${Math.floor(se.duree_min/60)}h${se.duree_min%60 > 0 ? (se.duree_min%60)+"'" : ""}`
                : `${se.duree_min}'`}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">
                {se.cours_id ? coursMap[se.cours_id] ?? `Cours #${se.cours_id}` : "Session libre"}
                {se.sujet && <span className="text-[var(--muted-foreground)] font-normal"> — {se.sujet}</span>}
              </div>
              <div className="text-xs text-[var(--muted-foreground)]">{se.date}</div>
              {se.note && <div className="text-xs text-[var(--muted-foreground)] mt-0.5 italic">{se.note}</div>}
            </div>
            {confirmId === se.id ? (
              <span className="flex shrink-0 items-center gap-1">
                <button onClick={() => void remove(se.id)} aria-label="Confirmer la suppression"
                  className="text-xs font-medium text-[var(--destructive)]">Supprimer</button>
                <button onClick={() => setConfirmId(null)} aria-label="Annuler"
                  className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">✕</button>
              </span>
            ) : (
              <button onClick={() => setConfirmId(se.id)} aria-label="Supprimer la session"
                className="shrink-0 text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
