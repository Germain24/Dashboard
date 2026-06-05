"use client";
import { useEffect, useState } from "react";
import { fetchSessions, createSession, deleteSession, fetchCours, type SessionEtude, type Cours } from "@/lib/etudes";
import { planFocus } from "@/lib/agenda";
import { PomodoroTimer } from "./PomodoroTimer";

export function SessionsTab() {
  const [sessions, setSessions] = useState<SessionEtude[]>([]);
  const [cours, setCours] = useState<Cours[]>([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ cours_id: "", duree_min: "25", sujet: "", note: "" });
  const [focusMsg, setFocusMsg] = useState<string | null>(null);
  const [planning, setPlanning] = useState(false);

  const load = async () => {
    const [s, c] = await Promise.all([fetchSessions(), fetchCours()]);
    setSessions(s);
    setCours(c);
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!form.duree_min) return;
    await createSession({
      cours_id: form.cours_id ? Number(form.cours_id) : undefined,
      duree_min: Number(form.duree_min),
      sujet: form.sujet || undefined,
      note: form.note || undefined,
    });
    setForm({ cours_id: "", duree_min: "25", sujet: "", note: "" });
    setAdding(false);
    load();
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

      <PomodoroTimer cours={cours} onLogged={load} />

      {adding && (
        <div className="border rounded p-3 space-y-2 text-sm bg-[var(--card)]">
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Cours</label>
            <select className="flex-1 border rounded px-2 py-1 bg-[var(--card)]"
              value={form.cours_id} onChange={e => setForm(f => ({ ...f, cours_id: e.target.value }))}>
              <option value="">— libre —</option>
              {cours.map(c => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Durée (min)</label>
            <input type="number" className="w-20 border rounded px-2 py-1 bg-transparent"
              value={form.duree_min} onChange={e => setForm(f => ({ ...f, duree_min: e.target.value }))} />
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Sujet</label>
            <input list="sujets-reutilisables" className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ex: Révision Ch.3"
              value={form.sujet} onChange={e => setForm(f => ({ ...f, sujet: e.target.value }))} />
            <datalist id="sujets-reutilisables">
              {sujetsReutilisables.map(s => <option key={s} value={s} />)}
            </datalist>
          </div>
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Note</label>
            <input className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder="ressenti, bilan..."
              value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Enregistrer</button>
        </div>
      )}

      <div className="space-y-2">
        {sessions.length === 0 && <p className="text-[var(--muted-foreground)] text-sm">Aucune session enregistrée.</p>}
        {sessions.map(se => (
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
            <button onClick={async () => { await deleteSession(se.id); load(); }}
              aria-label="Supprimer la session"
              className="shrink-0 text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
