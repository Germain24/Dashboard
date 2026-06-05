"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { fetchCours, createCours, patchCours, deleteCours, type Cours } from "@/lib/etudes";
import { Skeleton } from "@/components/ui/skeleton";

const LETTRE_COLOR: Record<string, string> = {
  "A+": "text-[var(--success)]", A: "text-[var(--success)]", "A-": "text-[var(--success)]",
  "B+": "text-[var(--info)]", B: "text-[var(--info)]", "B-": "text-[var(--info)]",
  "C+": "text-[var(--warning)]", C: "text-[var(--warning)]", "C-": "text-[var(--warning)]",
  "D+": "text-[var(--warning)]", D: "text-[var(--warning)]", E: "text-[var(--destructive)]",
};

export function CoursTab() {
  const [cours, setCours] = useState<Cours[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [semestre, setSemestre] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [editNote, setEditNote] = useState("");
  const [form, setForm] = useState({ code: "", nom: "", semestre: "", credits: "3", prof: "", local: "" });
  const [adding, setAdding] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const load = useCallback(() => {
    let active = true;
    fetchCours(semestre ? { semestre } : undefined)
      .then((data) => { if (active) { setCours(data); setStatus("ready"); } })
      .catch(() => active && setStatus("error"));
    return () => { active = false; };
  }, [semestre]);
  useEffect(() => load(), [load]);

  const handleAdd = async () => {
    if (!form.code || !form.nom || !form.semestre) return;
    try {
      await createCours({ ...form, credits: Number(form.credits) });
      setForm({ code: "", nom: "", semestre: "", credits: "3", prof: "", local: "" });
      setAdding(false);
      load();
    } catch {
      toast.error("Impossible de créer le cours.");
    }
  };

  const handleNoteFinale = async (id: number) => {
    const n = parseFloat(editNote);
    if (isNaN(n) || n < 0 || n > 100) return;
    try {
      await patchCours(id, { note_finale: n });
      setEditId(null);
      load();
    } catch {
      toast.error("Impossible d'enregistrer la note.");
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteCours(id);
      load();
    } catch {
      setConfirmId(null);
      toast.error("Suppression impossible.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <input className="border rounded px-2 py-1 text-sm bg-transparent" placeholder="Semestre (ex: A2026)"
          aria-label="Filtrer par semestre"
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
              <label htmlFor={`cours-${key}`} className="w-24 shrink-0 text-[var(--muted-foreground)]">{label}</label>
              <input id={`cours-${key}`} className="flex-1 border rounded px-2 py-1 bg-transparent" placeholder={ph}
                value={(form as any)[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
            </div>
          ))}
          <div className="flex gap-2 items-center">
            <label htmlFor="cours-credits" className="w-24 shrink-0 text-[var(--muted-foreground)]">Crédits</label>
            <input id="cours-credits" type="number" className="w-20 border rounded px-2 py-1 bg-transparent" value={form.credits}
              onChange={e => setForm(f => ({ ...f, credits: e.target.value }))} />
          </div>
          <button onClick={handleAdd} className="px-3 py-1 bg-[var(--primary)] text-[var(--primary-foreground)] rounded text-sm hover:opacity-90">Créer</button>
        </div>
      )}

      <div className="space-y-2">
        {status === "loading" && <Skeleton lines={5} />}

        {status === "error" && (
          <div className="flex flex-col items-start gap-2 py-2">
            <p className="text-sm text-[var(--muted-foreground)]">Cours indisponibles pour le moment.</p>
            <button onClick={() => { setStatus("loading"); load(); }}
              className="rounded border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--accent)]">
              Réessayer
            </button>
          </div>
        )}

        {status === "ready" && cours.length === 0 && (
          <p className="text-[var(--muted-foreground)] text-sm">Aucun cours.</p>
        )}

        {status === "ready" && cours.map(c => (
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
                    aria-label="Note finale sur 100"
                    value={editNote} onChange={e => setEditNote(e.target.value)} />
                  <button onClick={() => handleNoteFinale(c.id)} aria-label="Valider la note" className="text-xs text-[var(--success)]">✓</button>
                  <button onClick={() => setEditId(null)} aria-label="Annuler la saisie" className="text-xs text-[var(--muted-foreground)]">✕</button>
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
            {confirmId === c.id ? (
              <span className="flex shrink-0 items-center gap-1">
                <button onClick={() => void remove(c.id)} aria-label="Confirmer la suppression"
                  className="text-xs font-medium text-[var(--destructive)]">Supprimer</button>
                <button onClick={() => setConfirmId(null)} aria-label="Annuler"
                  className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">✕</button>
              </span>
            ) : (
              <button onClick={() => setConfirmId(c.id)}
                aria-label={`Supprimer ${c.code}`}
                className="shrink-0 text-xs text-[var(--muted-foreground)] hover:text-[var(--destructive)]">✕</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
