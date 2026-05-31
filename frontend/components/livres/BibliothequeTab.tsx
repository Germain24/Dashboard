'use client'
import { useEffect, useState } from 'react'
import { fetchBooks, updateBook } from '@/lib/livres'

const STATUTS = [
  { key: 'a_lire', label: 'À lire' },
  { key: 'en_cours', label: 'En cours' },
  { key: 'lu', label: 'Lu' },
]

export function BibliothequeTab() {
  const [books, setBooks] = useState<any[]>([])

  useEffect(() => { fetchBooks().then(setBooks) }, [])

  const byStatut = (s: string) => books.filter(b => b.statut === s)

  const move = async (book: any, newStatut: string) => {
    await updateBook(book.id, { statut: newStatut })
    fetchBooks().then(setBooks)
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {STATUTS.map(s => (
        <div key={s.key} className="space-y-3">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">{s.label}</h3>
            <span className="text-xs rounded-full bg-[var(--muted)] px-2 py-0.5 text-[var(--muted-foreground)] font-mono">
              {byStatut(s.key).length}
            </span>
          </div>
          {byStatut(s.key).map((book: any) => (
            <div key={book.id} className="rounded-lg border border-[var(--border)] p-3 space-y-2">
              {book.couverture_url && (
                <img
                  src={book.couverture_url}
                  alt={book.titre}
                  className="w-full h-32 object-cover rounded-md"
                />
              )}
              <div className="text-sm font-medium leading-tight">{book.titre}</div>
              <div className="text-xs text-[var(--muted-foreground)]">{book.auteur}</div>
              <div className="flex gap-1 flex-wrap">
                {STATUTS.filter(st => st.key !== s.key).map(st => (
                  <button
                    key={st.key}
                    onClick={() => move(book, st.key)}
                    className="text-xs rounded border border-[var(--border)] px-2 py-1 hover:bg-[var(--accent)] transition-colors"
                  >
                    → {st.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {byStatut(s.key).length === 0 && (
            <div className="rounded-lg border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--muted-foreground)]">
              Aucun livre
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
