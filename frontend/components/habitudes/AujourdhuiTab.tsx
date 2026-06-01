'use client'

import { useState } from 'react'

type Habitude = {
  id: number
  nom: string
  emoji: string
  frequence: 'quotidien' | 'hebdo'
}

type HabitEntry = {
  habit_id: number
  date: string
}

const HABITUDES: Habitude[] = [
  { id: 1, nom: 'Méditation', emoji: '🧘', frequence: 'quotidien' },
  { id: 2, nom: 'Lecture 30 min', emoji: '📖', frequence: 'quotidien' },
  { id: 3, nom: 'Sport', emoji: '🏋️', frequence: 'quotidien' },
  { id: 4, nom: 'Journaling', emoji: '📝', frequence: 'quotidien' },
  { id: 5, nom: 'Pleine nature', emoji: '🌿', frequence: 'hebdo' },
  { id: 6, nom: 'Appel famille', emoji: '📞', frequence: 'hebdo' },
]

const MOCK_STREAKS: Record<number, number> = {
  1: 7,
  2: 3,
  3: 14,
  4: 1,
  5: 2,
  6: 0,
}

const today = new Date().toISOString().slice(0, 10)

export default function AujourdhuiTab() {
  const [entries, setEntries] = useState<HabitEntry[]>([])

  const isChecked = (id: number) => entries.some(e => e.habit_id === id && e.date === today)

  const toggle = (habit: Habitude) => {
    if (isChecked(habit.id)) {
      setEntries(prev => prev.filter(e => !(e.habit_id === habit.id && e.date === today)))
    } else {
      setEntries(prev => [...prev, { habit_id: habit.id, date: today }])
    }
  }

  const streakFor = (id: number) => MOCK_STREAKS[id] ?? 0

  const checkedCount = HABITUDES.filter(h => isChecked(h.id)).length
  const total = HABITUDES.length
  const pct = Math.round((checkedCount / total) * 100)

  return (
    <div className="space-y-6">
      {/* Progression du jour */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold">Progression du jour</p>
            <p className="text-xs text-[var(--muted-foreground)]">{checkedCount} / {total} habitudes</p>
          </div>
          <span className="text-2xl font-bold font-mono" style={{ color: pct === 100 ? 'var(--success)' : 'var(--ring)' }}>
            {pct}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: pct === 100 ? 'var(--success)' : 'var(--ring)',
            }}
          />
        </div>
      </div>

      {/* Checklist */}
      <div className="space-y-2 max-w-sm stagger">
        {HABITUDES.map((habit) => {
          const checked = isChecked(habit.id)
          const streak = streakFor(habit.id)
          return (
            <button
              key={habit.id}
              onClick={() => toggle(habit)}
              className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl border transition-all duration-200 text-left animate-fade-in-up group cursor-pointer ${
                checked
                  ? 'border-[var(--success)] bg-[color-mix(in_srgb,var(--success)_8%,transparent)]'
                  : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)] hover:bg-[var(--muted)]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all duration-200 ${
                  checked ? 'bg-[var(--success)] border-[var(--success)]' : 'border-[var(--border)] group-hover:border-[var(--muted-foreground)]'
                }`}>
                  {checked && (
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <span className="text-sm font-medium">
                  {habit.nom}
                </span>
                {habit.frequence === 'hebdo' && (
                  <span className="text-xs text-[var(--muted-foreground)] bg-[var(--muted)] px-1.5 py-0.5 rounded">hebdo</span>
                )}
              </div>
              {streak > 0 && (
                <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-[color-mix(in_srgb,#f59e0b_15%,transparent)] text-[#d97706]">
                  {streak} 🔥
                </span>
              )}
            </button>
          )
        })}
      </div>

      <p className="text-xs text-[var(--muted-foreground)] animate-fade-in-up">
        Les streaks et entrées seront synchronisés avec le backend Habitudes.
      </p>
    </div>
  )
}
