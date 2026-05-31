'use client'
import { useEffect, useState } from 'react'
import { fetchMealPlan, generateMealPlan } from '@/lib/cuisine'

const JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const REPAS = ['petit_dejeuner', 'dejeuner', 'souper']
const REPAS_LABELS: Record<string, string> = {
  petit_dejeuner: 'Matin',
  dejeuner: 'Midi',
  souper: 'Soir',
}

function getWeek() {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7)
  return `${now.getFullYear()}-W${String(week).padStart(2, '0')}`
}

export function PlanSemaineTab() {
  const [plan, setPlan] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const week = getWeek()

  useEffect(() => {
    fetchMealPlan(week).then(setPlan)
  }, [])

  const generate = async () => {
    setLoading(true)
    try {
      await generateMealPlan(week)
      const p = await fetchMealPlan(week)
      setPlan(p)
    } finally {
      setLoading(false)
    }
  }

  const entryFor = (jour: number, repas: string) =>
    plan.find(e => e.jour === jour && e.repas === repas)

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          onClick={generate}
          disabled={loading}
          className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Génération...' : 'Générer automatiquement'}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left py-2 pr-4 text-[var(--muted-foreground)] font-medium w-16">Repas</th>
              {JOURS.map(j => (
                <th key={j} className="text-center py-2 px-2 text-[var(--muted-foreground)] font-medium">
                  {j}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {REPAS.map(repas => (
              <tr key={repas} className="border-t border-[var(--border)]">
                <td className="py-3 pr-4 text-[var(--muted-foreground)] text-xs">{REPAS_LABELS[repas]}</td>
                {JOURS.map((_, ji) => {
                  const entry = entryFor(ji, repas)
                  return (
                    <td key={ji} className="py-3 px-2 text-center">
                      {entry?.recipe_id ? (
                        <span className="text-xs bg-[var(--muted)] px-2 py-1 rounded">#{entry.recipe_id}</span>
                      ) : (
                        <span className="text-xs text-[var(--muted-foreground)]">—</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
