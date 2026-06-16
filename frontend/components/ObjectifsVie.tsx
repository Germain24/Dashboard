'use client'

import { useState } from 'react'
import { Target, Trash2, Plus, X } from 'lucide-react'
import {
  useLifeGoals, useLifeGoalMetrics, useCreateLifeGoal, useDeleteLifeGoal,
} from '@/lib/queries/routines'

type Sub = { label: string; metric: string; baseline: string; cible: string }

/** Objectifs de vie inter-modules (#226). */
export function ObjectifsVie() {
  const { data: goals } = useLifeGoals()
  const { data: metrics } = useLifeGoalMetrics()
  const create = useCreateLifeGoal()
  const del = useDeleteLifeGoal()
  const [open, setOpen] = useState(false)
  const [titre, setTitre] = useState('')
  const [subs, setSubs] = useState<Sub[]>([{ label: '', metric: metrics?.[0]?.metric ?? 'poids', baseline: '', cible: '' }])

  const addSub = () => setSubs((s) => [...s, { label: '', metric: metrics?.[0]?.metric ?? 'poids', baseline: '', cible: '' }])
  const setSub = (i: number, patch: Partial<Sub>) => setSubs((s) => s.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  const rmSub = (i: number) => setSubs((s) => s.filter((_, j) => j !== i))

  const submit = () => {
    const objectifs = subs
      .filter((s) => s.label.trim() && s.cible !== '')
      .map((s) => ({ label: s.label.trim(), metric: s.metric, baseline: Number(s.baseline || 0), cible: Number(s.cible) }))
    if (!titre.trim() || objectifs.length === 0) return
    create.mutate({ titre: titre.trim(), objectifs }, {
      onSuccess: () => { setOpen(false); setTitre(''); setSubs([{ label: '', metric: metrics?.[0]?.metric ?? 'poids', baseline: '', cible: '' }]) },
    })
  }

  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
          <Target size={13} /> Objectifs de vie
        </h2>
        <button onClick={() => setOpen(true)} className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <Plus size={13} /> Nouvel objectif
        </button>
      </div>

      {(!goals || goals.length === 0) ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucun objectif. Crée-en un (ex. « −5 kg + 2000 € »).</p>
      ) : (
        <ul className="space-y-4">
          {goals.map((g) => (
            <li key={g.id}>
              <div className="flex items-center gap-2">
                <span className="flex-1 font-medium text-[var(--foreground)]">{g.titre}</span>
                {g.pct_global != null && <span className="tabular-nums text-sm text-[var(--muted-foreground)]">{g.pct_global}%</span>}
                <button onClick={() => del.mutate(g.id)} aria-label="Supprimer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={14} /></button>
              </div>
              {g.pct_global != null && (
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                  <div className="h-full rounded-full bg-[var(--ring)]" style={{ width: `${g.pct_global}%` }} />
                </div>
              )}
              <ul className="mt-2 space-y-1.5 pl-1">
                {g.objectifs.map((o, i) => (
                  <li key={i} className="text-xs">
                    <div className="flex items-center justify-between gap-2 text-[var(--muted-foreground)]">
                      <span>{o.label}{o.atteint && ' ✓'}</span>
                      <span className="tabular-nums">{o.courant ?? '—'} / {o.cible} {o.pct != null && `(${o.pct}%)`}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-semibold">Nouvel objectif de vie</h3>
              <button onClick={() => setOpen(false)} aria-label="Fermer"><X size={16} /></button>
            </div>
            <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Titre (ex. Forme & épargne T3)" className="mb-3 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm" />
            <div className="space-y-2">
              {subs.map((s, i) => (
                <div key={i} className="flex flex-wrap items-center gap-1.5">
                  <input value={s.label} onChange={(e) => setSub(i, { label: e.target.value })} placeholder="Sous-objectif" className="min-w-28 flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
                  <select value={s.metric} onChange={(e) => setSub(i, { metric: e.target.value })} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm">
                    {metrics?.map((m) => <option key={m.metric} value={m.metric}>{m.label}</option>)}
                  </select>
                  <input type="number" value={s.baseline} onChange={(e) => setSub(i, { baseline: e.target.value })} placeholder="départ" className="w-20 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
                  <input type="number" value={s.cible} onChange={(e) => setSub(i, { cible: e.target.value })} placeholder="cible" className="w-20 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm tabular-nums" />
                  {subs.length > 1 && <button onClick={() => rmSub(i)} aria-label="Retirer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={13} /></button>}
                </div>
              ))}
              <button onClick={addSub} className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><Plus size={12} /> Ajouter un sous-objectif</button>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm">Annuler</button>
              <button onClick={submit} disabled={create.isPending} className="rounded-lg bg-[var(--ring)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50">Créer</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
