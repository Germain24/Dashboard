'use client'
import { useEffect, useState } from 'react'
import { fetchShoppingList, markShoppingDone, toggleShoppingItem } from '@/lib/cuisine'

function getWeek() {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 1)
  const week = Math.ceil(((now.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7)
  return `${now.getFullYear()}-W${String(week).padStart(2, '0')}`
}

export function CoursesTab() {
  const [items, setItems] = useState<any[]>([])
  const week = getWeek()

  const load = () => fetchShoppingList(week).then(setItems)
  useEffect(() => { load() }, [])

  const toggle = async (item: any) => {
    await toggleShoppingItem(item.id, !item.achete)
    load()
  }

  const markDone = async () => {
    await markShoppingDone(week)
    load()
  }

  const byRayon = items.reduce((acc: any, item: any) => {
    if (!acc[item.rayon]) acc[item.rayon] = []
    acc[item.rayon].push(item)
    return acc
  }, {})

  const allDone = items.length > 0 && items.every(i => i.achete)

  return (
    <div className="space-y-6">
      {items.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune liste de courses pour cette semaine.</p>
      )}
      {Object.entries(byRayon).map(([rayon, rayonItems]: any) => (
        <div key={rayon} className="space-y-2">
          <h3 className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">{rayon}</h3>
          {rayonItems.map((item: any) => (
            <button
              key={item.id}
              onClick={() => toggle(item)}
              className={`w-full flex justify-between items-center px-4 py-2 rounded-md border text-left transition-colors ${
                item.achete
                  ? 'line-through text-[var(--muted-foreground)] bg-[var(--muted)] border-transparent'
                  : 'border-[var(--border)] hover:bg-[var(--muted)]'
              }`}
            >
              <span className="text-sm text-[var(--foreground)]">{item.ingredient}</span>
              <span className="text-sm font-mono text-[var(--muted-foreground)]">{item.quantite} {item.unite}</span>
            </button>
          ))}
        </div>
      ))}
      {items.length > 0 && !allDone && (
        <button
          onClick={markDone}
          className="rounded border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
        >
          Tout marquer comme acheté
        </button>
      )}
    </div>
  )
}
