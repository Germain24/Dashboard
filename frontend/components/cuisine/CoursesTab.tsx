'use client'

/** Onglet Courses — liste agrégée depuis le plan repas. */

import { useState } from 'react'
import type { ShoppingItem } from '@/lib/cuisine'
import { useMealPlan, useShoppingPreview } from '@/lib/queries/cuisine'
import { RestaurantCreditSummary, ShoppingContent, ShoppingHeader, type ShoppingGroups } from './CoursesParts'

function currentMonday(): string {
  const date = new Date()
  date.setDate(date.getDate() + ((date.getDay() === 0 ? -6 : 1) - date.getDay()))
  return date.toISOString().slice(0, 10)
}

function cycleJours(): number[] {
  const today = (new Date().getDay() + 6) % 7
  const end = today <= 3 ? 3 : 6
  const days: number[] = []
  for (let day = today; day <= end; day++) days.push(day)
  return days
}

function groupByRayon(items: ShoppingItem[]): ShoppingGroups {
  const groups: ShoppingGroups = {}
  for (const item of items) (groups[item.rayon] ??= []).push(item)
  return groups
}

function resolveItems(query: { isError: boolean; data?: ShoppingItem[] }): ShoppingItem[] | null {
  return query.isError ? [] : query.data ?? null
}

function countDone(items: ShoppingItem[] | null, checked: Set<string>): number {
  return items?.filter((item) => checked.has(item.ingredient + item.unite)).length ?? 0
}

function summarize(items: ShoppingItem[] | null, checked: Set<string>) {
  if (!items) return { groups: {}, total: 0, done: 0 }
  return { groups: groupByRayon(items), total: items.length, done: countDone(items, checked) }
}

export default function CoursesTab() {
  const semaine = currentMonday()
  const [mode, setMode] = useState<'cycle' | 'semaine'>('cycle')
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const previewQ = useShoppingPreview(semaine, mode === 'cycle' ? cycleJours() : undefined)
  const planQ = useMealPlan(semaine)
  const items = resolveItems(previewQ)
  const summary = summarize(items, checked)
  const scopeDays = mode === 'cycle' ? new Set(cycleJours()) : null
  const restaurantMeals = planQ.data?.filter((entry) => entry.restaurant && (!scopeDays || scopeDays.has(entry.jour))) ?? null
  const toggle = (key: string) => setChecked((current) => {
    const next = new Set(current)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
  })

  return <div className="space-y-4"><ShoppingHeader mode={mode} setMode={setMode} total={summary.total} done={summary.done} /><RestaurantCreditSummary meals={restaurantMeals} loading={planQ.isLoading} /><ShoppingContent items={items} groups={summary.groups} checked={checked} toggle={toggle} /></div>
}
