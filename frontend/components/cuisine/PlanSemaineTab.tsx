'use client'

/** Onglet Plan semaine — génération branchée sur l'optimiseur de nutrition. */

import { useCallback, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { fetchDailyTargets, type MealEntry, type Recipe } from '@/lib/cuisine'
import { useGenerateMealPlan, useMealPlan, useRecipes } from '@/lib/queries/cuisine'
import { PlanContent, PlanHeader, type MealTargets } from './PlanSemaineParts'

function currentMonday(): string {
  const date = new Date()
  const day = date.getDay()
  date.setDate(date.getDate() + ((day === 0 ? -6 : 1) - day))
  return date.toISOString().slice(0, 10)
}

function resolvePlan(query: { isError: boolean; data?: MealEntry[] }): MealEntry[] | null {
  return query.isError ? [] : query.data ?? null
}

function recipeMap(recipes?: Recipe[]): Map<number, string> {
  return new Map((recipes ?? []).map((recipe) => [recipe.id, recipe.titre]))
}

const targetValue = (source: Record<string, number>, name: string) => source[name] ?? 0

function toTargets(source: Record<string, number>): MealTargets {
  return { calories: targetValue(source, 'Calories'), proteines: targetValue(source, 'Proteines'), glucides: targetValue(source, 'Glucides'), lipides: targetValue(source, 'Lipides') }
}

function notifyGeneration(entries: unknown) {
  if (Array.isArray(entries) && entries.length === 0) toast.error('Aucune recette : ajoute des recettes avant de générer.')
  else toast.success('Plan généré depuis tes cibles nutrition.')
}

async function createPlan(semaine: string, mutate: (params: { semaine: string; cibles: MealTargets }) => Promise<unknown>) {
  const targets = toTargets(await fetchDailyTargets())
  const entries = await mutate({ semaine, cibles: targets })
  return { targets, entries }
}

function usePlanGeneration(semaine: string) {
  const [generating, setGenerating] = useState(false)
  const [targets, setTargets] = useState<MealTargets | null>(null)
  const mutation = useGenerateMealPlan()
  const generate = useCallback(async () => {
    setGenerating(true)
    try {
      const result = await createPlan(semaine, mutation.mutateAsync)
      setTargets(result.targets)
      notifyGeneration(result.entries)
    } catch {
      toast.error('Génération impossible (cibles nutrition manquantes dans Santé ?).')
    } finally {
      setGenerating(false)
    }
  }, [mutation.mutateAsync, semaine])
  return { generating, targets, generate }
}

export default function PlanSemaineTab() {
  const semaine = currentMonday()
  const planQuery = useMealPlan(semaine)
  const recipesQuery = useRecipes()
  const plan = resolvePlan(planQuery)
  const recipes = useMemo(() => recipeMap(recipesQuery.data), [recipesQuery.data])
  const generation = usePlanGeneration(semaine)

  return <div className="space-y-4"><PlanHeader semaine={semaine} targets={generation.targets} generating={generation.generating} generate={() => void generation.generate()} /><PlanContent plan={plan} recipes={recipes} /></div>
}
