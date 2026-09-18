'use client'

import { Wand2 } from 'lucide-react'
import type { MealEntry, Recipe } from '@/lib/cuisine'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

export type MealTargets = Record<string, number>
export const DAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
export const MEALS: { key: string; label: string }[] = [
  { key: 'petit_dejeuner', label: 'Petit-déj' },
  { key: 'dejeuner', label: 'Déjeuner' },
  { key: 'souper', label: 'Souper' },
]

export function PlanHeader({ semaine, targets, generating, generate }: { semaine: string; targets: MealTargets | null; generating: boolean; generate: () => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-[var(--muted-foreground)]">Semaine du {semaine}</p>{targets && <p className="text-xs tabular-nums text-[var(--muted-foreground)]">Cibles : {Math.round(targets.calories)} kcal · {Math.round(targets.proteines)}P · {Math.round(targets.glucides)}G · {Math.round(targets.lipides)}L</p>}</div><button type="button" onClick={generate} disabled={generating} className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"><Wand2 className="h-4 w-4" aria-hidden="true" />{generating ? 'Génération…' : 'Générer depuis mes cibles'}</button></div>
}

function mealName(entry: MealEntry | undefined, recipes: Map<number, string>): string {
  if (!entry) return '—'
  if (entry.restaurant) return entry.restaurant.name
  if (!entry.recipe_id) return '—'
  return recipes.get(entry.recipe_id) ?? `Recette #${entry.recipe_id}`
}

function MealCell({ entry, recipes }: { entry?: MealEntry; recipes: Map<number, string> }) {
  const restaurant = entry?.restaurant
  if (!restaurant) return <td className="px-3 py-2">{mealName(entry, recipes)}</td>
  return <td className="px-3 py-2"><div className="font-medium">{restaurant.name} <span className="text-xs font-normal text-[var(--success)]">· crédit repas</span></div><p className="mt-0.5 text-[11px] text-[var(--muted-foreground)]">{restaurant.price.toFixed(2)} $ avant taxes · ~{restaurant.calories} kcal · {restaurant.proteines} P · {restaurant.glucides} G · {restaurant.lipides} L</p><a href={restaurant.menu_url} target="_blank" rel="noreferrer" className="mt-0.5 inline-block text-[11px] text-[var(--ring)] underline">Menu Crew</a></td>
}

function MealRow({ day, label, plan, recipes }: { day: number; label: string; plan: MealEntry[]; recipes: Map<number, string> }) {
  return <tr className="border-b border-[var(--border)] last:border-0"><td className="px-3 py-2 font-medium text-[var(--muted-foreground)]">{label}</td>{MEALS.map((meal) => <MealCell key={meal.key} entry={plan.find((item) => item.jour === day && item.repas === meal.key)} recipes={recipes} />)}</tr>
}

function MealTable({ plan, recipes }: { plan: MealEntry[]; recipes: Map<number, string> }) {
  return <div className="overflow-x-auto rounded-xl border border-[var(--border)]"><table className="w-full min-w-[34rem] border-collapse text-sm"><thead><tr className="border-b border-[var(--border)] bg-[var(--muted)]"><th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">Jour</th>{MEALS.map((meal) => <th key={meal.key} className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)]">{meal.label}</th>)}</tr></thead><tbody>{DAYS.map((label, day) => <MealRow key={day} day={day} label={label} plan={plan} recipes={recipes} />)}</tbody></table></div>
}

export function PlanContent({ plan, recipes }: { plan: MealEntry[] | null; recipes: Map<number, string> }) {
  if (plan === null) return <Skeleton className="h-64" />
  if (plan.length === 0) return <EmptyState title="Aucun plan cette semaine" description="Génère un plan : tes recettes seront choisies pour coller à tes cibles nutrition du jour. Les repas des jours de travail utilisent automatiquement le crédit Crew." />
  return <div className="space-y-2"><MealTable plan={plan} recipes={recipes} /><p className="text-xs text-[var(--muted-foreground)]">Les macros des plats Crew sont estimées à partir des ingrédients du menu; vérifie-les selon les portions réellement servies.</p></div>
}

export type RecipeMapSource = Pick<Recipe, 'id' | 'titre'>[]
