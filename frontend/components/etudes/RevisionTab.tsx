"use client";

/** Révision espacée (spaced repetition, SM-2) sur fiches (#99). */

import { useEffect, useState } from "react";
import {
  fetchRevisionCards, addRevisionCard, reviewRevisionCard, deleteRevisionCard,
  fetchCours, type RevisionCard, type Cours,
} from "@/lib/etudes";

const QUALITIES = [
  { q: 1, label: "Raté", color: "#ef4444" },
  { q: 3, label: "Difficile", color: "#f59e0b" },
  { q: 4, label: "Bien", color: "#10b981" },
  { q: 5, label: "Facile", color: "#3b82f6" },
];

export function RevisionTab() {
  const [cards, setCards] = useState<RevisionCard[]>([]);
  const [due, setDue] = useState<RevisionCard[]>([]);
  const [cours, setCours] = useState<Cours[]>([]);
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ recto: "", verso: "", cours_id: "" });

  const load = async () => {
    const [all, d, c] = await Promise.all([fetchRevisionCards(false), fetchRevisionCards(true), fetchCours()]);
    setCards(all); setDue(d); setCours(c); setIdx(0); setRevealed(false);
  };
  useEffect(() => { void load(); }, []);

  const current = due[idx];

  const grade = async (q: number) => {
    if (!current) return;
    await reviewRevisionCard(current.id, q);
    if (idx + 1 < due.length) { setIdx(idx + 1); setRevealed(false); }
    else { await load(); }
  };

  const add = async () => {
    if (!form.recto.trim() || !form.verso.trim()) return;
    await addRevisionCard(form.recto, form.verso, form.cours_id ? Number(form.cours_id) : undefined);
    setForm({ recto: "", verso: "", cours_id: "" });
    setAdding(false);
    await load();
  };

  const remove = async (id: number) => { await deleteRevisionCard(id); await load(); };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="text-sm text-[var(--muted)]">
          {due.length} à réviser aujourd&apos;hui · {cards.length} fiche{cards.length > 1 ? "s" : ""}
        </div>
        <button onClick={() => setAdding(a => !a)}
          className="px-3 py-1 bg-violet-600 text-white rounded text-sm hover:bg-violet-700">
          {adding ? "Annuler" : "+ Fiche"}
        </button>
      </div>

      {adding && (
        <div className="border rounded p-3 space-y-2 text-sm bg-[var(--card-bg)]">
          <input className="w-full border rounded px-2 py-1 bg-transparent" placeholder="Recto (question)"
            value={form.recto} onChange={e => setForm(f => ({ ...f, recto: e.target.value }))} />
          <textarea className="w-full border rounded px-2 py-1 bg-transparent" placeholder="Verso (réponse)" rows={2}
            value={form.verso} onChange={e => setForm(f => ({ ...f, verso: e.target.value }))} />
          <div className="flex gap-2">
            <select className="flex-1 border rounded px-2 py-1 bg-[var(--card-bg)]"
              value={form.cours_id} onChange={e => setForm(f => ({ ...f, cours_id: e.target.value }))}>
              <option value="">— cours (optionnel) —</option>
              {cours.map(c => <option key={c.id} value={c.id}>{c.code}</option>)}
            </select>
            <button onClick={() => void add()} className="px-3 py-1 bg-emerald-600 text-white rounded text-sm">Ajouter</button>
          </div>
        </div>
      )}

      {/* Mode révision */}
      {current ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card-bg)] p-6 text-center space-y-4">
          <div className="text-xs text-[var(--muted)]">Fiche {idx + 1} / {due.length}</div>
          <div className="text-lg font-medium min-h-[2rem]">{current.recto}</div>
          {revealed ? (
            <>
              <div className="border-t border-[var(--border)] pt-3 text-[var(--muted)]">{current.verso}</div>
              <div className="flex justify-center gap-2 flex-wrap">
                {QUALITIES.map(({ q, label, color }) => (
                  <button key={q} onClick={() => void grade(q)}
                    className="px-3 py-1.5 rounded text-sm text-white" style={{ backgroundColor: color }}>
                    {label}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <button onClick={() => setRevealed(true)}
              className="px-4 py-1.5 border border-[var(--border)] rounded text-sm hover:bg-[var(--muted)]">
              Révéler la réponse
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--card-bg)] p-6 text-center text-sm text-[var(--muted)]">
          {cards.length === 0 ? "Aucune fiche. Crée-en une pour commencer." : "🎉 Rien à réviser aujourd'hui !"}
        </div>
      )}

      {/* Liste des fiches */}
      {cards.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-xs font-semibold uppercase text-[var(--muted)]">Toutes les fiches</h3>
          {cards.map(c => (
            <div key={c.id} className="flex items-center gap-2 text-xs border rounded px-2 py-1 bg-[var(--card-bg)]">
              <span className="flex-1 truncate" title={c.recto}>{c.recto}</span>
              <span className="text-[var(--muted)]">⏱ {c.due}</span>
              <button onClick={() => void remove(c.id)} className="text-red-400 hover:text-red-300">✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
