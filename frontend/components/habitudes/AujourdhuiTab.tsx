'use client'
import { useEffect, useState } from 'react'
import { fetchToday, fetchStreaks, checkEntry } from '@/lib/habitudes'

export function AujourdhuiTab() {
  const [items, setItems] = useState<any[]>([])
  const [streaks, setStreaks] = useState<any[]>([])
  const today = new Date().toISOString().slice(0, 10)

  useEffect(() => {
    fetchToday().then(setItems)
    fetchStreaks().then(setStreaks)
  }, [])

  const streakFor = (id: number) => streaks.find(s => s.habit_id === id)?.streak ?? 0

  const toggle = async (item: any) => {
    if (item.entry) {
      await fetch(`/api/habitudes/entries/${item.entry.id}`, { method: 'DELETE' })
    } else {
      await checkEntry(item.habit.id, today)
    }
    fetchToday().then(setItems)
    fetchStreaks().then(setStreaks)
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">Aucune habitude configurée pour aujourd&apos;hui.</p>
    )
  }

  return (
    <div className="space-y-2 max-w-lg">
      {items.map((item: any) => (
        <button
          key={item.habit.id}
          onClick={() => toggle(item)}
          className={`w-full flex items-center justify-between px-4 py-3 rounded-lg border transition-colors text-left ${
            item.entry
              ? 'bg-[var(--accent)] border-[var(--accent)] text-[var(--accent-foreground)]'
              : 'border-[var(--border)] hover:bg-[var(--muted)]'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 ${
              item.entry ? 'bg-[var(--primary)] border-[var(--primary)]' : 'border-[var(--muted-foreground)]'
            }`}>
              {item.entry && (
                <svg className="w-3 h-3 text-[var(--primary-foreground)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <span className="font-medium text-sm">{item.habit.nom}</span>
          </div>
          {streakFor(item.habit.id) > 0 && (
            <span className="text-xs rounded-full bg-[var(--muted)] px-2 py-0.5 font-mono text-[var(--muted-foreground)]">
              {streakFor(item.habit.id)} 🔥
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
