'use client'

import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useHabits, useHeatmap } from '@/lib/queries/habitudes'
import { Skeleton } from '@/components/ui/skeleton'

const MOIS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
const JOURS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Cases du mois alignées lundi→dimanche (null = padding). */
function monthCells(year: number, month: number): (Date | null)[] {
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7 // lundi = 0
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: (Date | null)[] = []
  for (let i = 0; i < offset; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d))
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

export default function MoisTab() {
  const [habitId, setHabitId] = useState<number | null>(null)
  const [cursor, setCursor] = useState(() => { const n = new Date(); return { year: n.getFullYear(), month: n.getMonth() } })

  const habitsQ = useHabits()
  const habits = habitsQ.isError ? [] : habitsQ.data ?? null

  useEffect(() => {
    if (habitId == null && habits && habits.length > 0) setHabitId(habits[0].id)
  }, [habits, habitId])

  const heatmapQ = useHeatmap(habitId, cursor.year)
  const loading = habitId != null && heatmapQ.isFetching
  const done = useMemo(() => {
    const data: { date: string; valeur: number }[] = Array.isArray(heatmapQ.data) ? heatmapQ.data : []
    return new Set(data.filter((d) => d.valeur > 0).map((d) => d.date))
  }, [heatmapQ.data])

  const cells = useMemo(() => monthCells(cursor.year, cursor.month), [cursor])
  const todayStr = ymd(new Date())

  const monthDoneCount = cells.filter((c) => c && done.has(ymd(c))).length
  const habit = habits?.find((h) => h.id === habitId)
  const accent = habit?.couleur || 'var(--success)'

  const shift = (delta: number) => setCursor((c) => {
    const m = c.month + delta
    return { year: c.year + Math.floor(m / 12), month: ((m % 12) + 12) % 12 }
  })

  if (habits === null) return (
    <div className="space-y-3 max-w-sm">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-8" />)}</div>
  )
  if (habits.length === 0) return (
    <p className="text-sm text-[var(--muted-foreground)]">Aucune habitude configurée.</p>
  )

  return (
    <div className="max-w-sm space-y-4 animate-fade-in-up">
      <select
        value={habitId ?? ''}
        onChange={(e) => setHabitId(Number(e.target.value))}
        aria-label="Habitude"
        className="w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
      >
        {habits.map((h) => (
          <option key={h.id} value={h.id}>{h.icone ? `${h.icone} ` : ''}{h.nom}</option>
        ))}
      </select>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <button type="button" onClick={() => shift(-1)} aria-label="Mois précédent"
            className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]">
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <p className="text-sm font-semibold">{MOIS[cursor.month]} {cursor.year}</p>
          <button type="button" onClick={() => shift(1)} aria-label="Mois suivant"
            className="rounded p-1 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]">
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1">
          {JOURS.map((j, i) => (
            <div key={i} className="text-center text-[10px] font-medium text-[var(--muted-foreground)]">{j}</div>
          ))}
          {cells.map((c, i) => {
            if (!c) return <div key={i} />
            const s = ymd(c)
            const isDone = done.has(s)
            const isToday = s === todayStr
            return (
              <div
                key={i}
                title={s}
                className={`flex aspect-square items-center justify-center rounded-md text-xs transition-colors ${
                  isToday ? 'ring-1 ring-[var(--ring)]' : ''
                }`}
                style={isDone
                  ? { background: accent, color: '#fff', fontWeight: 600 }
                  : { background: 'var(--muted)', color: 'var(--muted-foreground)' }}
              >
                {c.getDate()}
              </div>
            )
          })}
        </div>

        <p className="mt-3 text-xs text-[var(--muted-foreground)]">
          {loading ? 'Chargement…' : `${monthDoneCount} jour${monthDoneCount > 1 ? 's' : ''} complété${monthDoneCount > 1 ? 's' : ''} ce mois`}
        </p>
      </div>
    </div>
  )
}
