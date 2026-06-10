'use client'

/**
 * Onglet Plan semaine — génération branchée sur l'optimiseur de nutrition.
 *
 * « Générer » récupère les cibles macros du jour (Santé /targets/today), les
 * passe à la génération du plan (recettes scorées sur ces cibles), puis affiche
 * le plan (7 jours × 3 repas). Convention semaine = date du lundi.
 */

import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Wand2 } from 'lucide-react'
import { fetchDailyTargets } from '@/lib/cuisine'
import { useGenerateMealPlan, useMealPlan, useRecipes } from '@/lib/queries/cuisine'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

type Entry = { id: number; semaine: string; jour: number; repas: string; recipe_id: number | null }

const JOURS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const REPAS: { key: string; label: string }[] = [
  { key: 'petit_dejeuner', label: 'Petit-déj' },
  { key: 'dejeuner', label: 'Déjeuner' },
  { key: 'souper', label: 'Souper' },
]

function currentMonday(): string {
  const d = new Date()
  const day = d.getDay() // 0=dim … 6=sam
  d.setDate(d.getDate() + ((day === 0 ? -6 : 1) - day))
  return d.toISOString().slice(0, 10)
}

export default function PlanSemaineTab() {
  const semaine = currentMonday()
  const [generating, setGenerating] = useState(false)
  const [cibles, setCibles] = useState<Record<string, number> | null>(null)

  const planQ = useMealPlan(semaine)
  const plan: Entry[] | null = planQ.isError ? [] : planQ.data ?? null
  const recipesQ = useRecipes()
  const recipes = useMemo(
    () => new Map((recipesQ.data ?? []).map((r) => [r.id, r.titre])),
    [recipesQ.data],
  )
  const generateMutation = useGenerateMealPlan()

  async function generate() {
    setGenerating(true)
    try {
      const t = await fetchDailyTargets()
      const c = {
        calories: t.Calories ?? 0,
        proteines: t.Proteines ?? 0,
        glucides: t.Glucides ?? 0,
        lipides: t.Lipides ?? 0,
      }
      setCibles(c)
      const entries = await generateMutation.mutateAsync({ semaine, cibles: c })
      if (Array.isArray(entries) && entries.length === 0) {
        toast.error('Aucune recette : ajoute des recettes avant de générer.')
      } else {
        toast.success('Plan généré depuis tes cibles nutrition.')
      }
    } catch {
      toast.error('Génération impossible (cibles nutrition manquantes dans Santé ?).')
    } finally {
      setGenerating(false)
    }
  }

  const cell = (jour: number, repas: string): string => {
    const e = (plan ?? []).find((x) => x.jour === jour && x.repas === repas)
    if (!e?.recipe_id) return '—'
    return recipes.get(e.recipe_id) ?? `Recette #${e.recipe_id}`
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-[var(--muted-foreground)]">Semaine du {semaine}</p>
          {cibles && (
            <p className="text-xs tabular-nums text-[var(--muted-foreground)]">
              Cibles : {Math.round(cibles.calories)} kcal · {Math.round(cibles.proteines)}P ·{' '}
              {Math.round(cibles.glucides)}G · {Math.round(cibles.lipides)}L
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void generate()}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          <Wand2 className="h-4 w-4" aria-hidden="true" />
          {generating ? 'Génération…' : 'Générer depuis mes cibles'}
        </button>
      </div>

      {plan === null && <Skeleton className="h-64" />}

      {plan !== null && plan.length === 0 && (
        <EmptyState
          title="Aucun plan cette semaine"
          description="Génère un plan : tes recettes seront choisies pour coller à tes cibles nutrition du jour."
        />
      )}

      {plan !== null && plan.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
          <table className="w-full min-w-[34rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--muted)]">
                <th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">Jour</th>
                {REPAS.map((r) => (
                  <th key={r.key} className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">
                    {r.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {JOURS.map((jourLabel, jour) => (
                <tr key={jour} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-3 py-2 font-medium text-[var(--muted-foreground)]">{jourLabel}</td>
                  {REPAS.map((r) => (
                    <td key={r.key} className="px-3 py-2">
                      {cell(jour, r.key)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
