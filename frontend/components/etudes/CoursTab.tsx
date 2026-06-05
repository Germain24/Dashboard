"use client";
import { useEffect, useState } from "react";
import { fetchCours, createCours, patchCours, deleteCours, type Cours } from "@/lib/etudes";

const LETTRE_COLOR: Record<string, string> = {
  "A+": "text-[var(--success)]", A: "text-[var(--success)]", "A-": "text-[var(--success)]",
  "B+": "text-[var(--info)]", B: "text-[var(--info)]", "B-": "text-[var(--info)]",
  "C+": "text-[var(--warning)]", C: "text-[var(--warning)]", "C-": "text-[var(--warning)]",
  "D+": "text-[var(--warning)]", D: "text-[var(--warning)]", E: "text-[var(--destructive)]",
};

export function CoursTab() {
  const [cours, setCours] = useState<Cours[]>([]);
  const [semestre, setSemestre] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [editNote, setEditNote] = useState("");
  const [form, setForm] = useState({ code: "", nom: "", semestre: "", credits: "3", prof: "", local: "" });
  const [adding, setAdding] = useState(false);

  const load = async () => {
    const data = await fetchCours(semestre ? { semestre } : undefined);
    setCours(data);
  };

  useEffect(() => { load(); }, [semestre]);

  const handleAdd = async () => {
    if (!form.code || !form.nom || !form.semestre) return;
    await createCours({ ...form, credits: Number(form.credits) });
    setForm({ code: "", nom: "", semestre: "", credits: "3", prof: "", local: "" });
    setAdding(false);
    load();
  };

  const handleNoteFinale = async (id: number) => {
    const n = parseFloat(editNote);
    if (isNaN(n) || n < 0 || n > 100) return;
    await patchCours(id, { note_finale: n });
    setEditId(null);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <input className="border rounded px-2 py-1 text-sm bg-transparent" placeholder="Semestre (ex: A2026)"
          value={semestre} onChange={e => setSemestre(e.target.value)} />
        <button onClick={() => setAdding(a => !a)}
          className="ml-auto px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">
          {adding ? "Annuler" : "+ Ajouter un cours"}
        </button>
      </div>

      {adding && (
        <div className="border rounded p-3 space-y-2 text-sm bg-[var(--card)]">
          {[["Code", "code", "INF1000"], ["Nom", "nom", "Introduction à la programmation"],
            ["Semestre", "semestre", "A2026"], ["Professeur", "prof", ""], ["Local", "local", ""]].map(([label, key, ph]) => (
            <div key={key} className="flex gap-2 items-center">
              <label className="w-24 shrink-0 text-[var(--muted-foreground)]">{label}</label>
              <input className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder={ph}
                value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div className="flex gap-2 items-center">
            <label className="w-24 shrink-0 text-[var(--muted-foreground)]">Crédits</label>
            <input type="number" className="w-20 border rounded px-2 py-1 bg-transparent" value={form.credits}
              onChange={e => setForm(f => ({ ...f, credits: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Créer</button>
        </div>
      )}

      <div className="space-y-2">
        {cours.length === 0 && <p className="text-[var(--muted-foreground)] text-sm">Aucun cours.</p>}
        {cours.map(c => (
          <div key={c.id} className="border rounded p-3 flex items-center gap-3 bg-[var(--card)]">
            <div className="flex-1 min-w-0">
              <div className="font-medium">{c.code} <span className="text-[var(--muted-foreground)] text-sm">— {c.nom}</span></div>
              <div className="text-xs text-[var(--muted-foreground)]">{c.semestre}{c.prof ? ` · ${c.prof}` : ""}{c.local ? ` · ${c.local}` : ""}</div>
              <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{c.total_minutes_etude ? `${Math.round((c.total_minutes_etude||0)/60*10)/10}h étude` : "0h étude"}</div>
            </div>
            <div className="text-right shrink-0">
              {editId === c.id ? (
                <div className="flex gap-1 items-center">
                  <input type="number" className="w-16 border rounded px-1 py-0.5 text-sm bg-transparent" placeholder="/100"
                    value={editNote} onChange={e => setEditNote(e.target.value)} />
                  <button onClick={() => handleNoteFinale(c.id)} className="text-xs text-[var(--success)]">✓</button>
                  <button onClick={() => setEditId(null)} className="text-xs text-[var(--muted-foreground)]">✕</button>
                </div>
              ) : (
                <button onClick={() => { setEditId(c.id); setEditNote(String(c.note_finale ?? "")); }}
                  className="text-left">
                  {c.note_finale != null ? (
                    <div>
                      <span className={`text-lg font-bold ${LETTRE_COLOR[c.lettre||"E"] ?? ""}`}>{c.lettre}</span>
                      <span className="text-xs text-[var(--muted-foreground)] ml-1">{c.note_finale}/100</span>
                    </div>
                  ) : (
                    <span className="text-xs text-[var(--muted-foreground)] underline">Saisir note</span>
                  )}
                </button>
              )}
            </div>
            <button onClick={async () => { await deleteCours(c.id); load(); }}
              aria-label={`Supprimer ${c.code}`}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
