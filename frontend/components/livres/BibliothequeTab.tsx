'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { BookOpen, Clock, CheckCircle2, Bookmark, XCircle, Plus, Search, X } from 'lucide-react'
import {
  fetchBooks, updateBook, createBook, searchBooks,
  type Book, type Statut, type SearchResult,
} from '@/lib/livres'
import { Skeleton } from '@/components/ui/skeleton'
import BookDetailModal from '@/components/livres/BookDetailModal'

const STATUT_CONFIG: Record<Statut, { label: string; icon: typeof BookOpen; color: string; bg: string }> = {
  en_cours: { label: 'En cours', icon: Clock, color: '#f59e0b', bg: 'color-mix(in_srgb,#f59e0b_12%,transparent)' },
  a_lire: { label: 'À lire', icon: Bookmark, color: 'var(--ring)', bg: 'color-mix(in_srgb,var(--ring)_10%,transparent)' },
  lu: { label: 'Lu', icon: CheckCircle2, color: 'var(--success)', bg: 'color-mix(in_srgb,var(--success)_10%,transparent)' },
  abandonne: { label: 'Abandonné', icon: XCircle, color: 'var(--muted-foreground)', bg: 'var(--muted)' },
}

const ALL_STATUTS: Statut[] = ['en_cours', 'a_lire', 'lu', 'abandonne']

function Stars({ note, onSet }: { note: number | null; onSet?: (n: number) => void }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <button
          key={i}
          type="button"
          disabled={!onSet}
          onClick={(e) => { e.stopPropagation(); onSet?.(i + 1) }}
          className={`text-sm ${onSet ? 'cursor-pointer' : 'cursor-default'} ${i < (note ?? 0) ? 'text-[#f59e0b]' : 'text-[var(--border)]'}`}
          aria-label={`Note ${i + 1}`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export default function BibliothequeTab() {
  const [livres, setLivres] = useState<Book[] | null>(null)
  const [filtre, setFiltre] = useState<Statut | 'tous'>('tous')
  const [sort, setSort] = useState<'recent' | 'note'>('recent')
  const [selected, setSelected] = useState<Book | null>(null)
  const [showAdd, setShowAdd] = useState(false)

  const load = useCallback(() => {
    fetchBooks({ sort: sort === 'note' ? 'note' : undefined })
      .then((d) => setLivres(Array.isArray(d) ? d : []))
      .catch(() => setLivres([]))
  }, [sort])

  useEffect(() => load(), [load])

  const setNote = async (b: Book, note: number) => {
    setLivres((prev) => prev?.map((x) => (x.id === b.id ? { ...x, note } : x)) ?? prev)
    try { await updateBook(b.id, { note }) } catch { toast.error('Note non sauvegardée.'); load() }
  }

  if (livres === null) {
    return <div className="space-y-2 max-w-xl">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
  }

  const counts = Object.fromEntries(
    ALL_STATUTS.map((s) => [s, livres.filter((l) => l.statut === s).length]),
  ) as Record<Statut, number>

  const livresFiltres = filtre === 'tous' ? livres : livres.filter((l) => l.statut === filtre)

  return (
    <div className="max-w-xl space-y-6">
      {/* Étagères (#145) */}
      <div className="grid grid-cols-4 gap-3 stagger">
        {ALL_STATUTS.map((s) => {
          const cfg = STATUT_CONFIG[s]
          const Icon = cfg.icon
          return (
            <button
              key={s}
              onClick={() => setFiltre((f) => (f === s ? 'tous' : s))}
              className={`rounded-xl border bg-[var(--card)] p-3 text-center transition-all animate-fade-in-up ${
                filtre === s ? 'border-[var(--ring)]' : 'border-[var(--border)] hover:border-[var(--muted-foreground)]'
              }`}
            >
              <Icon size={18} className="mx-auto mb-1" style={{ color: cfg.color }} />
              <p className="text-2xl font-bold font-mono">{counts[s]}</p>
              <p className="text-[11px] text-[var(--muted-foreground)]">{cfg.label}</p>
            </button>
          )
        })}
      </div>

      {/* Barre d'actions */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {filtre !== 'tous' && (
            <button onClick={() => setFiltre('tous')} className="text-xs text-[var(--ring)] hover:underline">
              ✕ {STATUT_CONFIG[filtre].label}
            </button>
          )}
          <label className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
            Tri
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as 'recent' | 'note')}
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
            >
              <option value="recent">Récent</option>
              <option value="note">Note ★</option>
            </select>
          </label>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden="true" /> Ajouter
        </button>
      </div>

      {/* Liste */}
      {livresFiltres.length === 0 ? (
        <p className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--muted-foreground)]">
          Aucun livre {filtre !== 'tous' ? `« ${STATUT_CONFIG[filtre].label} »` : ''}. Ajoute-en un !
        </p>
      ) : (
        <div className="space-y-2 stagger">
          {livresFiltres.map((livre) => {
            const cfg = STATUT_CONFIG[livre.statut] ?? STATUT_CONFIG.a_lire
            const total = livre.pages ?? 0
            const current = livre.page_courante ?? 0
            const pct = total > 0 ? Math.round((Math.min(current, total) / total) * 100) : 0
            return (
              <button
                key={livre.id}
                onClick={() => setSelected(livre)}
                className="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-left card-hover animate-fade-in-up"
              >
                <div className="flex items-start gap-3">
                  {livre.couverture_url ? (
                    <img src={livre.couverture_url} alt="" className="h-14 w-10 shrink-0 rounded object-cover" />
                  ) : (
                    <div className="flex h-14 w-10 shrink-0 items-center justify-center rounded" style={{ background: cfg.bg }}>
                      <BookOpen size={16} style={{ color: cfg.color }} />
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold leading-tight">{livre.titre}</p>
                        <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">{livre.auteur || '—'}</p>
                      </div>
                      <Stars note={livre.note} onSet={(n) => void setNote(livre, n)} />
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium" style={{ background: cfg.bg, color: cfg.color }}>
                        {cfg.label}
                      </span>
                      {livre.genre && (
                        <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]">{livre.genre}</span>
                      )}
                      {total > 0 && <span className="text-xs text-[var(--muted-foreground)]">{total} p.</span>}
                    </div>
                    {livre.statut === 'en_cours' && total > 0 && (
                      <div className="mt-2">
                        <div className="mb-1 flex justify-between text-[10px] text-[var(--muted-foreground)]">
                          <span>Page {current}</span><span>{pct}%</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: cfg.color }} />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {showAdd && (
        <AddBookDialog
          onClose={() => setShowAdd(false)}
          onAdded={() => { setShowAdd(false); load() }}
        />
      )}

      {selected && (
        <BookDetailModal
          book={selected}
          onClose={() => setSelected(null)}
          onChanged={() => { load() }}
          onDeleted={() => { setSelected(null); load() }}
        />
      )}
    </div>
  )
}

function AddBookDialog({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)

  const runSearch = async () => {
    if (!q.trim()) return
    setSearching(true)
    try {
      setResults(await searchBooks(q.trim()))
    } catch {
      toast.error('Recherche indisponible.')
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const add = async (r: SearchResult) => {
    try {
      await createBook({
        titre: r.titre, auteur: r.auteur, pages: r.pages, isbn: r.isbn,
        couverture_url: r.couverture_url, statut: 'a_lire',
      })
      toast.success(`« ${r.titre} » ajouté à « À lire ».`)
      onAdded()
    } catch {
      toast.error('Ajout impossible.')
    }
  }

  const addManual = async () => {
    if (!q.trim()) return
    try {
      await createBook({ titre: q.trim(), statut: 'a_lire' })
      toast.success(`« ${q.trim()} » ajouté.`)
      onAdded()
    } catch { toast.error('Ajout impossible.') }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-20">
      <div role="dialog" aria-modal="true" aria-label="Ajouter un livre"
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold">Ajouter un livre</p>
          <button onClick={onClose} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X className="h-4 w-4" /></button>
        </div>
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void runSearch() }}
            placeholder="Titre ou auteur…"
            className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <button onClick={() => void runSearch()} disabled={searching}
            className="flex items-center gap-1 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-60">
            <Search className="h-4 w-4" /> {searching ? '…' : 'OK'}
          </button>
        </div>

        <div className="mt-3 max-h-72 space-y-1.5 overflow-y-auto">
          {results !== null && results.length === 0 && (
            <div className="text-center text-xs text-[var(--muted-foreground)]">
              Aucun résultat.{' '}
              <button onClick={() => void addManual()} className="text-[var(--ring)] hover:underline">Ajouter « {q} » manuellement</button>
            </div>
          )}
          {results?.map((r, i) => (
            <button key={i} onClick={() => void add(r)}
              className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] p-2 text-left hover:bg-[var(--muted)]">
              {r.couverture_url ? (
                <img src={r.couverture_url} alt="" className="h-12 w-8 shrink-0 rounded object-cover" />
              ) : (
                <div className="flex h-12 w-8 shrink-0 items-center justify-center rounded bg-[var(--muted)]"><BookOpen size={14} /></div>
              )}
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{r.titre}</p>
                <p className="truncate text-xs text-[var(--muted-foreground)]">{r.auteur || '—'}{r.annee ? ` · ${r.annee}` : ''}{r.pages ? ` · ${r.pages} p.` : ''}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
