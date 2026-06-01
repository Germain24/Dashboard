'use client'

import { useState } from 'react'

type Item = {
  id: number
  nom: string
  quantite: string
  rayon: string
}

const MOCK_COURSES: Item[] = [
  // Fruits & légumes
  { id: 1, nom: 'Carottes', quantite: '500 g', rayon: 'Fruits & légumes' },
  { id: 2, nom: 'Courgettes', quantite: '2', rayon: 'Fruits & légumes' },
  { id: 3, nom: 'Épinards', quantite: '300 g', rayon: 'Fruits & légumes' },
  { id: 4, nom: 'Citron', quantite: '2', rayon: 'Fruits & légumes' },
  // Viandes
  { id: 5, nom: 'Poitrine de poulet', quantite: '600 g', rayon: 'Viandes' },
  { id: 6, nom: 'Bacon', quantite: '200 g', rayon: 'Viandes' },
  // Produits laitiers
  { id: 7, nom: 'Parmesan', quantite: '100 g', rayon: 'Produits laitiers' },
  { id: 8, nom: 'Crème fraîche', quantite: '250 ml', rayon: 'Produits laitiers' },
  { id: 9, nom: 'Oeufs', quantite: '12', rayon: 'Produits laitiers' },
  // Épicerie
  { id: 10, nom: 'Pâtes linguine', quantite: '500 g', rayon: 'Épicerie' },
  { id: 11, nom: 'Riz à risotto', quantite: '500 g', rayon: 'Épicerie' },
  { id: 12, nom: 'Miso blanc', quantite: '200 g', rayon: 'Épicerie' },
  { id: 13, nom: 'Quinoa', quantite: '400 g', rayon: 'Épicerie' },
]

// Grouper par rayon
function groupByRayon(items: Item[]): Record<string, Item[]> {
  const groups: Record<string, Item[]> = {}
  for (const item of items) {
    if (!groups[item.rayon]) groups[item.rayon] = []
    groups[item.rayon].push(item)
  }
  return groups
}

export default function CoursesTab() {
  const [checked, setChecked] = useState<Set<number>>(new Set())

  const toggle = (id: number) => {
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const groups = groupByRayon(MOCK_COURSES)
  const rayons = Object.keys(groups)

  const totalItems = MOCK_COURSES.length
  const checkedCount = checked.size
  const pct = Math.round((checkedCount / totalItems) * 100)

  return (
    <div className="space-y-6">
      {/* Progression */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 animate-fade-in-up">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-semibold">Courses</p>
            <p className="text-xs text-[var(--muted-foreground)]">{checkedCount} / {totalItems} articles cochés</p>
          </div>
          <span className="text-2xl font-bold font-mono" style={{ color: pct === 100 ? 'var(--success)' : 'var(--ring)' }}>
            {pct}%
          </span>
        </div>
        <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: pct === 100 ? 'var(--success)' : 'var(--ring)',
            }}
          />
        </div>
      </div>

      {/* Items groupés par rayon */}
      <div className="space-y-5 stagger">
        {rayons.map(rayon => (
          <div key={rayon} className="animate-fade-in-up">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
              {rayon}
            </h3>
            <div className="space-y-1.5">
              {groups[rayon].map(item => {
                const isChecked = checked.has(item.id)
                return (
                  <button
                    key={item.id}
                    onClick={() => toggle(item.id)}
                    className={`w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all duration-200 text-left cursor-pointer group ${
                      isChecked
                        ? 'border-[var(--success)] bg-[color-mix(in_srgb,var(--success)_8%,transparent)]'
                        : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)] hover:bg-[var(--muted)]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-all duration-200 ${
                        isChecked ? 'bg-[var(--success)] border-[var(--success)]' : 'border-[var(--border)] group-hover:border-[var(--muted-foreground)]'
                      }`}>
                        {isChecked && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <span className={`text-sm font-medium transition-all duration-200 ${isChecked ? 'line-through text-[var(--muted-foreground)]' : ''}`}>
                        {item.nom}
                      </span>
                    </div>
                    <span className={`text-xs text-[var(--muted-foreground)] transition-all duration-200 ${isChecked ? 'opacity-50' : ''}`}>
                      {item.quantite}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
        <p className="text-sm text-[var(--muted-foreground)]">
          La liste sera générée automatiquement depuis le plan de la semaine.
        </p>
      </div>
    </div>
  )
}
