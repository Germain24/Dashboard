'use client'

import { useEffect, useState } from 'react'
import { fetchHabits, fetchHeatmap } from '@/lib/habitudes'
import { Skeleton } from '@/components/ui/skeleton'

type HabitRow = { id: number; nom: string; days: Map<string, number> }

const MONTH_LABELS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

function buildWeeks(year: number): string[][] {
  const weeks: string[][] = []
  let week: string[] = []
  const start = new Date(year, 0, 1)
  // pad so week starts on Sunday
  for (let i = 0; i < start.getDay(); i++) week.push('')
  const end = new Date(year, 11, 31)
  const cur = new Date(start)
  while (cur <= end) {
    week.push(cur.toISOString().slice(0, 10))
    if (week.length === 7) { weeks.push(week); week = [] }
    cur.setDate(cur.getDate() + 1)
  }
  if (week.length > 0) { while (week.length < 7) week.push(''); weeks.push(week) }
  return weeks
}

function monthPositions(year: number, weeks: string[][]): { label: string; col: number }[] {
  const seen = new Set<number>()
  const positions: { label: string; col: number }[] = []
  weeks.forEach((week, wi) => {
    for (const d of week) {
      if (!d) continue
      const m = new Date(d).getMonth()
      if (!seen.has(m)) { seen.add(m); positions.push({ label: MONTH_LABELS[m], col: wi }) }
    }
  })
  return positions
}

function intensity(val: number): string {
  if (val === 0) return 'bg-[var(--muted)]'
  if (val < 0.5) return 'bg-[color-mix(in_srgb,var(--success)_35%,transparent)]'
  if (val < 1) return 'bg-[color-mix(in_srgb,var(--success)_65%,transparent)]'
  return 'bg-[var(--success)] opacity-80'
}

export default function HeatmapTab() {
  const year = new Date().getFullYear()
  const weeks = buildWeeks(year)
  const monthPos = monthPositions(year, weeks)

  const [rows, setRows] = useState<HabitRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchHabits()
      .then(async (habits: { id: number; nom: string }[]) => {
        const loaded = await Promise.all(
          habits.map(async (h) => {
            const data: { date: string; valeur: number }[] = await fetchHeatmap(h.id, year)
            const days = new Map(data.map((d) => [d.date, d.valeur]))
            return { id: h.id, nom: h.nom, days }
          })
        )
        if (!cancelled) setRows(loaded)
      })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [year])

  if (error) return <p className="text-sm text-[var(--destructive)]">Heatmap indisponible.</p>
  if (rows === null) return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => <Skeleton key={i} className="h-8" />)}
    </div>
  )
  if (rows.length === 0) return (
    <p className="text-sm text-[var(--muted-foreground)]">Aucune habitude configurée.</p>
  )

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 overflow-x-auto">
        <h2 className="text-sm font-semibold mb-1">Heatmap {year}</h2>
        <p className="text-xs text-[var(--muted-foreground)] mb-4">Régularité par habitude</p>

        {/* Month labels */}
        <div className="flex gap-0.5 mb-1 ml-[7rem]">
          {monthPos.map(({ label, col }) => (
            <div
              key={col}
              className="text-[10px] text-[var(--muted-foreground)] whitespace-nowrap"
              style={{ gridColumn: col + 1, minWidth: '1.5rem' }}
            >
              {label}
            </div>
          ))}
        </div>

        <div className="space-y-1">
          {/* Day-of-week labels on the left */}
          <div className="flex gap-0.5">
            <div className="w-28 shrink-0" />
            {weeks.map((_, wi) => (
              <div key={wi} className="w-[1.15rem] h-[1.15rem]" />
            ))}
          </div>
          {[1, 3, 5].map((dow) => (
            <div key={dow} className="flex items-center gap-0.5">
              <div className="w-28 shrink-0 text-[10px] text-[var(--muted-foreground)] text-right pr-2">
                {dow === 1 ? 'L' : dow === 3 ? 'M' : 'V'}
              </div>
              {weeks.map((week, wi) => {
                const d = week[dow]
                return (
                  <div
                    key={wi}
                    className={`w-[1.15rem] h-[1.15rem] rounded-sm ${d ? intensity(0) : ''}`}
                  />
                )
              })}
            </div>
          ))}
        </div>

        <div className="mt-3 space-y-1.5">
          {rows.map((row) => (
            <div key={row.id} className="flex items-center gap-0.5">
              <div className="w-28 shrink-0 text-xs text-[var(--muted-foreground)] truncate pr-2">{row.nom}</div>
              {weeks.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-0.5">
                  {week.map((d, di) => (
                    <div
                      key={di}
                      title={d ? `${row.nom} — ${d}` : ''}
                      className={`w-[1.15rem] h-[1.15rem] rounded-sm ${
                        d ? intensity(row.days.get(d) ?? 0) : ''
                      }`}
                    />
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2 mt-4 text-xs text-[var(--muted-foreground)]">
          <div className="w-3.5 h-3.5 rounded-sm bg-[var(--muted)]" />
          <span>Non fait</span>
          <div className="w-3.5 h-3.5 rounded-sm bg-[var(--success)] opacity-80 ml-3" />
          <span>Complété</span>
        </div>
      </div>
    </div>
  )
}
