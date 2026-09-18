'use client'

import type { MesureSante, NutritionGoal, NutritionGoalUpdate, ProjectionResponse } from '@/lib/sante'
import { SkeletonList, SkeletonStatRow } from '@/components/ui/skeleton'
import { FenetreTab } from './FenetreTab'
import { TendanceTab } from './TendanceTab'
import { CompositionTab } from './CompositionTab'
import { GoalTab } from './GoalTab'
import { ProgressionTab } from './ProgressionTab'

type Tab = 'fenetre' | 'tendance' | 'composition' | 'objectif' | 'progression'
type SaveMeasure = (measure: { date: string; poids?: number; photo_url?: string; note?: string }) => Promise<void>

export function GoalBadge({ goal }: { goal: NutritionGoal | null }) {
  if (!goal?.poids_cible) return null
  return <span className="rounded-[var(--radius-full)] bg-[var(--muted)] px-2.5 py-1 text-xs text-[var(--muted-foreground)]">Cible {goal.poids_cible.toFixed(1)} kg{goal.body_fat_target_pct ? ` · ${goal.body_fat_target_pct}% MG` : ''}</span>
}

export function SanteLoading() {
  return <div className="space-y-4 p-6"><SkeletonStatRow count={2} /><SkeletonList rows={3} /></div>
}

export function SanteError({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="p-6 text-[var(--destructive)]">⚠ {message}</div>
}

export function SanteTabs({ tab, goal, mesures, projection, lastWeight, onSaveMesure, onSaveGoal }: { tab: Tab; goal: NutritionGoal | null; mesures: MesureSante[]; projection: ProjectionResponse | null; lastWeight: number | null; onSaveMesure: SaveMeasure; onSaveGoal: (patch: NutritionGoalUpdate) => Promise<void> }) {
  const views: Record<Tab, React.ReactNode> = { fenetre: <FenetreTab goal={goal} onSaveMesure={onSaveMesure} lastWeight={lastWeight} />, tendance: <TendanceTab mesures={mesures} projection={projection} goal={goal} />, composition: <CompositionTab mesures={mesures} onSave={onSaveMesure} />, progression: <ProgressionTab />, objectif: goal ? <GoalTab goal={goal} onSave={onSaveGoal} /> : null }
  return views[tab]
}
