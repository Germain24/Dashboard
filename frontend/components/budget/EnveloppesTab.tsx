'use client'
import { useEffect, useState } from 'react'
import { fetchEnvelopes, fetchCategories } from '@/lib/budget'

export function EnveloppesTab() {
  const [envelopes, setEnvelopes] = useState<any[]>([])
  const [cats, setCats] = useState<any[]>([])
  const month = new Date().toISOString().slice(0, 7)

  useEffect(() => {
    fetchEnvelopes(month).then(setEnvelopes)
    fetchCategories().then(setCats)
  }, [month])

  const catName = (id: number) => cats.find(c => c.id === id)?.nom ?? `#${id}`

  const barColor = (pct: number) => {
    if (pct > 100) return 'bg-red-500'
    if (pct > 80) return 'bg-yellow-500'
    return 'bg-emerald-500'
  }

  return (
    <div className="space-y-4">
      {envelopes.map((env: any) => (
        <div key={env.category_id} className="rounded-lg border border-[var(--border)] p-4">
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium">{catName(env.category_id)}</span>
            <span className="font-mono text-[var(--muted-foreground)]">
              {env.depense?.toFixed(0)} / {env.budget?.toFixed(0)} CAD
            </span>
          </div>
          <div className="h-2 bg-[var(--muted)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor(env.pct)}`}
              style={{ width: `${Math.min(env.pct, 100)}%` }}
            />
          </div>
          <div className="text-xs text-[var(--muted-foreground)] mt-1">
            {env.pct?.toFixed(0)}% utilisé — reste {env.reste?.toFixed(2)} CAD
          </div>
        </div>
      ))}
      {envelopes.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune enveloppe définie pour ce mois.</p>
      )}
    </div>
  )
}
