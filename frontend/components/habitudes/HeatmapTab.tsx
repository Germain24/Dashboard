'use client'
import { useEffect, useState } from 'react'
import { fetchHabits, fetchHeatmap } from '@/lib/habitudes'

export function HeatmapTab() {
  const [habits, setHabits] = useState<any[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [data, setData] = useState<any[]>([])
  const year = new Date().getFullYear()

  useEffect(() => {
    fetchHabits().then(h => {
      setHabits(h)
      if (h.length) setSelectedId(h[0].id)
    })
  }, [])

  useEffect(() => {
    if (selectedId) fetchHeatmap(selectedId, year).then(setData)
  }, [selectedId, year])

  // Group by week (7 days each)
  const weeks: any[][] = []
  let week: any[] = []
  data.forEach(d => {
    week.push(d)
    if (week.length === 7) { weeks.push(week); week = [] }
  })
  if (week.length) weeks.push(week)

  const cellColor = (val: number) => {
    if (!val) return 'bg-[var(--muted)]'
    return 'bg-emerald-500'
  }

  return (
    <div className="space-y-4">
      {habits.length > 0 && (
        <select
          value={String(selectedId)}
          onChange={e => setSelectedId(Number(e.target.value))}
          className="rounded-lg border border-[var(--border)] bg-transparent px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        >
          {habits.map(h => (
            <option key={h.id} value={String(h.id)}>{h.nom}</option>
          ))}
        </select>
      )}

      {data.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune donnée pour cette habitude.</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="flex gap-1 min-w-max">
            {weeks.map((w, wi) => (
              <div key={wi} className="flex flex-col gap-1">
                {w.map((d: any, di: number) => (
                  <div
                    key={di}
                    title={`${d.date}: ${d.valeur ?? 0}`}
                    className={`w-3 h-3 rounded-sm ${cellColor(d.valeur)}`}
                  />
                ))}
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 mt-3 text-xs text-[var(--muted-foreground)]">
            <div className="w-3 h-3 rounded-sm bg-[var(--muted)]" />
            <span>0</span>
            <div className="w-3 h-3 rounded-sm bg-emerald-500 ml-2" />
            <span>Complétée</span>
          </div>
        </div>
      )}
    </div>
  )
}
