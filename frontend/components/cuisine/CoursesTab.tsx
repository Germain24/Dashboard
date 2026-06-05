'use client'

/**
 * Onglet Courses — liste de courses réelle, agrégée depuis le plan repas.
 *
 * Par défaut scopée sur le **cycle de cuisine** (d'aujourd'hui au prochain jour
 * de cuisine jeu/dim) ; bascule « Semaine entière » disponible. Calcul à la volée
 * côté backend (/shopping-list/preview), cases à cocher côté client.
 */

import { useCallback, useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { fetchShoppingPreview, type ShoppingItem } from '@/lib/cuisine'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

function currentMonday(): string {
  const d = new Date()
  d.setDate(d.getDate() + ((d.getDay() === 0 ? -6 : 1) - d.getDay()))
  return d.toISOString().slice(0, 10)
}

/** Jours (lundi=0..dim=6) d'aujourd'hui jusqu'au prochain jour de cuisine (jeu=3, dim=6). */
function cycleJours(): number[] {
  const today = (new Date().getDay() + 6) % 7 // JS dim=0 → lundi=0
  const end = today <= 3 ? 3 : 6
  const out: number[] = []
  for (let j = today; j <= end; j++) out.push(j)
  return out
}

function groupByRayon(items: ShoppingItem[]): Record<string, ShoppingItem[]> {
  const g: Record<string, ShoppingItem[]> = {}
  for (const it of items) (g[it.rayon] ??= []).push(it)
  return g
}

const fmtQte = (it: ShoppingItem) =>
  it.unite ? `${it.quantite} ${it.unite}` : `${it.quantite}`

export default function CoursesTab() {
  const semaine = currentMonday()
  const [mode, setMode] = useState<'cycle' | 'semaine'>('cycle')
  const [items, setItems] = useState<ShoppingItem[] | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())

  const load = useCallback(async () => {
    setItems(null)
    try {
      const jours = mode === 'cycle' ? cycleJours() : undefined
      setItems(await fetchShoppingPreview(semaine, jours))
    } catch {
      setItems([])
    }
  }, [semaine, mode])

  useEffect(() => {
    void load()
  }, [load])

  const toggle = (key: string) =>
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const groups = items ? groupByRayon(items) : {}
  const total = items?.length ?? 0
  const done = items ? items.filter((it) => checked.has(it.ingredient + it.unite)).length : 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-md border border-[var(--border)] p-0.5">
          {(['cycle', 'semaine'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                mode === m
                  ? 'bg-[var(--muted)] text-[var(--foreground)]'
                  : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              {m === 'cycle' ? 'Cycle de cuisine' : 'Semaine entière'}
            </button>
          ))}
        </div>
        {total > 0 && (
          <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
            {done}/{total} pris
          </span>
        )}
      </div>

      {items === null && <Skeleton lines={6} />}

      {items !== null && total === 0 && (
        <EmptyState
          title="Rien à acheter"
          description="Génère d'abord un plan dans l'onglet Plan ; la liste se remplit avec les ingrédients de tes recettes."
        />
      )}

      {total > 0 && (
        <div className="space-y-4">
          {Object.keys(groups)
            .sort()
            .map((rayon) => (
              <div key={rayon}>
                <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
                  {rayon}
                </h3>
                <div className="overflow-hidden rounded-lg border border-[var(--border)]">
                  {groups[rayon].map((it) => {
                    const key = it.ingredient + it.unite
                    const isChecked = checked.has(key)
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => toggle(key)}
                        className="flex w-full items-center gap-3 border-b border-[var(--border)] px-3 py-2 text-left transition-colors last:border-0 hover:bg-[var(--muted)]"
                      >
                        <span
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                            isChecked
                              ? 'border-[var(--ring)] bg-[var(--ring)] text-white'
                              : 'border-[var(--border)]'
                          }`}
                        >
                          {isChecked && <Check className="h-3 w-3" aria-hidden="true" />}
                        </span>
                        <span
                          className={`flex-1 text-sm ${isChecked ? 'text-[var(--muted-foreground)] line-through' : ''}`}
                        >
                          {it.ingredient}
                        </span>
                        <span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">
                          {fmtQte(it)}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
