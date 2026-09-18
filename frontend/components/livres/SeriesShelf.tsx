'use client'

import type { ReactNode } from 'react'
import { Layers } from 'lucide-react'
import type { Book } from '@/lib/livres'

/** Regroupe les tomes par série (même contrat que GET /livres/series).
 *  Les livres sans `serie` sont ignorés : ils gardent leur rendu individuel. */
export function groupBySerie(books: Book[]) {
  const parSerie = new Map<string, Book[]>()
  for (const b of books) {
    const nom = (b.serie ?? '').trim()
    if (!nom) continue
    const acc = parSerie.get(nom)
    if (acc) acc.push(b)
    else parSerie.set(nom, [b])
  }
  return Array.from(parSerie.entries())
    .sort((a, b) => a[0].localeCompare(b[0], 'fr'))
    .map(([serie, tomes]) => {
      // Un tome sans numéro (hors-série) passe en fin de liste.
      const ordonnes = [...tomes].sort(
        (a, b) => (a.tome ?? Infinity) - (b.tome ?? Infinity),
      )
      const lus = ordonnes.filter((b) => b.statut === 'lu').length
      return { serie, tomes: ordonnes, total: ordonnes.length, lus }
    })
}

export function SeriesShelf({
  books,
  renderBook,
}: {
  books: Book[]
  renderBook: (b: Book) => ReactNode
}) {
  const groupes = groupBySerie(books)
  if (groupes.length === 0) return null

  return (
    <div className="space-y-4">
      {groupes.map(({ serie, tomes, total, lus }) => {
        const pct = Math.round((lus / total) * 100)
        return (
          <section key={serie} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3">
            <div className="mb-2 flex items-center gap-2">
              <Layers size={14} className="shrink-0 text-[var(--muted-foreground)]" aria-hidden />
              <p className="min-w-0 flex-1 truncate text-sm font-semibold">{serie}</p>
              <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                {lus}/{total} tomes lus
              </span>
            </div>
            <div className="mb-3 h-1 overflow-hidden rounded-full bg-[var(--muted)]">
              <div className="h-full rounded-full bar-fill" style={{ width: `${pct}%`, background: 'var(--success)' }} />
            </div>
            <ul className="space-y-2">
              {tomes.map((b) => (
                <li key={b.id} className="flex items-start gap-2">
                  <span className="mt-1 shrink-0 rounded bg-[var(--muted)] px-1.5 py-0.5 text-[10px] font-medium tabular-nums text-[var(--muted-foreground)]">
                    T{b.tome ?? '?'}
                  </span>
                  <div className="min-w-0 flex-1">{renderBook(b)}</div>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
