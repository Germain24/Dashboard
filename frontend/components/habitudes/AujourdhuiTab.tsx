'use client'
import { useCheckEntry, useDeleteEntry, useStreaks, useToday } from '@/lib/queries/habitudes'

const today = new Date().toISOString().slice(0, 10)

export default function AujourdhuiTab() {
  const todayQ = useToday()
  const streaksQ = useStreaks()
  const checkEntry = useCheckEntry()
  const deleteEntry = useDeleteEntry()

  const items: any[] = Array.isArray(todayQ.data) ? todayQ.data : []
  const streaks: any[] = Array.isArray(streaksQ.data) ? streaksQ.data : []
  const loading = todayQ.isLoading || streaksQ.isLoading

  const streakFor = (id: number) => streaks.find(s => s.habit_id === id)?.streak ?? 0

  const toggle = (item: any) => {
    if (item.entry) {
      deleteEntry.mutate(item.entry.id)
    } else {
      checkEntry.mutate({ habit_id: item.habit.id, date: today })
    }
  }

  if (loading) {
    return (
      <div className="space-y-3 max-w-sm">
        {[0, 1, 2, 3, 4, 5].map(i => (
          <div key={i} className="h-14 rounded-xl skeleton-shimmer" />
        ))}
      </div>
    )
  }

  const checked = items.filter((i: any) => !!i.entry).length
  const total = items.length
  const pct = total > 0 ? Math.round((checked / total) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Progression du jour */}
      {total > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm font-semibold">Progression du jour</p>
              <p className="text-xs text-[var(--muted-foreground)]">{checked} / {total} habitudes</p>
            </div>
            <span className="text-2xl font-bold font-mono" style={{ color: pct === 100 ? 'var(--success)' : 'var(--ring)' }}>
              {pct}%
            </span>
          </div>
          <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, background: pct === 100 ? 'var(--success)' : 'var(--ring)' }}
            />
          </div>
        </div>
      )}

      {/* Checklist */}
      <div className="space-y-2 max-w-sm stagger">
        {items.map((item: any) => {
          const ischecked = !!item.entry
          const streak = streakFor(item.habit.id)
          return (
            <button
              key={item.habit.id}
              onClick={() => toggle(item)}
              className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl border transition-all duration-200 text-left group cursor-pointer animate-fade-in-up ${
                ischecked
                  ? 'border-[var(--success)] bg-[color-mix(in_srgb,var(--success)_8%,transparent)]'
                  : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)] hover:bg-[var(--muted)]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all duration-200 ${
                  ischecked ? 'bg-[var(--success)] border-[var(--success)]' : 'border-[var(--border)] group-hover:border-[var(--muted-foreground)]'
                }`}>
                  {ischecked && (
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <span className="text-sm font-medium">{item.habit.nom}</span>
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

      {items.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
          <p className="text-sm text-[var(--muted-foreground)]">Aucune habitude configurée.</p>
        </div>
      )}
    </div>
  )
}
