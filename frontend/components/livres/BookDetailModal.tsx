'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { X, Trash2, Quote as QuoteIcon, StickyNote, Clock } from 'lucide-react'
import type { Book, Statut, Estimate, BookNote, BookQuote } from '@/lib/livres'
import {
  useBookEstimate, useBookNotes, useBookQuotes, useCreateBookNote, useCreateBookQuote,
  useCreateReadingSession, useDeleteBook, useDeleteBookNote, useDeleteBookQuote, useUpdateBook,
} from '@/lib/queries/livres'

const STATUT_LABELS: Record<Statut, string> = {
  en_cours: 'En cours', a_lire: 'À lire', lu: 'Lu', abandonne: 'Abandonné',
}

function fmtMinutes(min: number | null): string {
  if (min == null) return '—'
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h} h ${m}` : `${h} h`
}

export default function BookDetailModal({
  book, onClose, onChanged, onDeleted,
}: {
  book: Book
  onClose: () => void
  onChanged: () => void
  onDeleted: () => void
}) {
  const [statut, setStatut] = useState<Statut>(book.statut)
  const [langue, setLangue] = useState(book.langue ?? '')
  const [newNote, setNewNote] = useState('')
  const [newQuote, setNewQuote] = useState('')
  const [pageFin, setPageFin] = useState('')
  const [duree, setDuree] = useState('')

  const estimate: Estimate | null = useBookEstimate(book.id).data ?? null
  const notesQ = useBookNotes(book.id)
  const quotesQ = useBookQuotes(book.id)
  const notes: BookNote[] = Array.isArray(notesQ.data) ? notesQ.data : []
  const quotes: BookQuote[] = Array.isArray(quotesQ.data) ? quotesQ.data : []

  const updateMutation = useUpdateBook()
  const deleteMutation = useDeleteBook()
  const sessionMutation = useCreateReadingSession()
  const noteMutation = useCreateBookNote()
  const deleteNoteMutation = useDeleteBookNote()
  const quoteMutation = useCreateBookQuote()
  const deleteQuoteMutation = useDeleteBookQuote()

  const changeStatut = (s: Statut) => {
    setStatut(s)
    const patch: Partial<Book> = { statut: s }
    if (s === 'lu' && !book.date_fin) patch.date_fin = new Date().toISOString().slice(0, 10)
    updateMutation.mutate({ id: book.id, patch }, {
      onSuccess: onChanged,
      onError: () => toast.error('Statut non sauvegardé.'),
    })
  }

  const saveLangue = () => {
    const v = langue.trim()
    if (v === (book.langue ?? '')) return
    updateMutation.mutate({ id: book.id, patch: { langue: v } }, {
      onSuccess: onChanged,
      onError: () => toast.error('Langue non sauvegardée.'),
    })
  }

  const logSession = () => {
    const d = parseInt(duree, 10)
    if (!d || d <= 0) { toast.error('Durée invalide.'); return }
    const pf = pageFin ? parseInt(pageFin, 10) : null
    sessionMutation.mutate(
      [book.id, {
        date: new Date().toISOString().slice(0, 10),
        duree_minutes: d,
        page_debut: book.page_courante ?? 0,
        page_fin: pf,
      }],
      {
        onSuccess: () => {
          toast.success('Session enregistrée.')
          setDuree(''); setPageFin('')
          onChanged()
        },
        onError: () => toast.error('Session non enregistrée.'),
      },
    )
  }

  const addNote = () => {
    if (!newNote.trim()) return
    noteMutation.mutate({ id: book.id, contenu: newNote.trim(), page: book.page_courante ?? null }, {
      onSuccess: () => setNewNote(''),
      onError: () => toast.error('Note non ajoutée.'),
    })
  }
  const addQuote = () => {
    if (!newQuote.trim()) return
    quoteMutation.mutate({ id: book.id, texte: newQuote.trim(), page: book.page_courante ?? null }, {
      onSuccess: () => setNewQuote(''),
      onError: () => toast.error('Citation non ajoutée.'),
    })
  }

  const remove = () => {
    if (!confirm(`Supprimer « ${book.titre} » ?`)) return
    deleteMutation.mutate(book.id, {
      onSuccess: () => { toast.success('Livre supprimé.'); onDeleted() },
      onError: () => toast.error('Suppression impossible.'),
    })
  }

  const inputCls = 'rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 py-12">
      <div role="dialog" aria-modal="true" aria-label={book.titre}
        className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-xl">
        <div className="mb-4 flex items-start gap-3">
          {book.couverture_url ? (
            <img src={book.couverture_url} alt="" className="h-20 w-14 shrink-0 rounded object-cover" />
          ) : null}
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold leading-tight">{book.titre}</h2>
            <p className="text-sm text-[var(--muted-foreground)]">{book.auteur || '—'}</p>
            {book.genre && <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">{book.genre}</p>}
          </div>
          <button onClick={onClose} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X className="h-4 w-4" /></button>
        </div>

        {/* Étagère / statut (#145) */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {(Object.keys(STATUT_LABELS) as Statut[]).map((s) => (
            <button key={s} onClick={() => void changeStatut(s)}
              className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                statut === s ? 'border-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_12%,transparent)] text-[var(--ring)]' : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]'
              }`}>
              {STATUT_LABELS[s]}
            </button>
          ))}
        </div>

        {/* Progression + estimation (#144 / #150) */}
        {estimate && estimate.pages > 0 && (
          <div className="mb-4 rounded-lg border border-[var(--border)] p-3">
            <div className="mb-1 flex justify-between text-xs text-[var(--muted-foreground)]">
              <span>Page {estimate.page_courante} / {estimate.pages}</span>
              <span>{estimate.pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--muted)]">
              <div className="h-full rounded-full bg-[var(--ring)] transition-all" style={{ width: `${estimate.pct}%` }} />
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
              <Clock className="h-3.5 w-3.5" />
              {estimate.remaining_minutes != null
                ? `Reste ~${fmtMinutes(estimate.remaining_minutes)} à ce rythme`
                : 'Rythme inconnu — enregistre une session'}
            </p>
          </div>
        )}

        {/* Langue (filtre sur l'onglet Livres) */}
        <div className="mb-4 flex items-center gap-2">
          <label htmlFor="book-langue" className="text-xs font-medium text-[var(--muted-foreground)]">Langue</label>
          <input
            id="book-langue"
            value={langue}
            onChange={(e) => setLangue(e.target.value)}
            onBlur={saveLangue}
            onKeyDown={(e) => { if (e.key === 'Enter') saveLangue() }}
            placeholder="ex. Français, Anglais…"
            className={`${inputCls} flex-1`}
          />
        </div>

        {/* Logger une session de lecture */}
        <div className="mb-4">
          <p className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">Enregistrer une session</p>
          <div className="flex gap-2">
            <input value={duree} onChange={(e) => setDuree(e.target.value)} inputMode="numeric" placeholder="min" className={`${inputCls} w-20`} />
            <input value={pageFin} onChange={(e) => setPageFin(e.target.value)} inputMode="numeric" placeholder="page actuelle" className={`${inputCls} flex-1`} />
            <button onClick={() => void logSession()} className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90">OK</button>
          </div>
        </div>

        {/* Notes (#147) */}
        <Section icon={<StickyNote className="h-3.5 w-3.5" />} title={`Notes (${notes.length})`}>
          <div className="flex gap-2">
            <input value={newNote} onChange={(e) => setNewNote(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void addNote() }} placeholder="Une note…" className={`${inputCls} flex-1`} />
            <button onClick={() => void addNote()} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)]">+</button>
          </div>
          {notes.map((n) => (
            <Row key={n.id} onDelete={() => deleteNoteMutation.mutate(n.id)}>
              {n.page != null && <span className="text-[var(--muted-foreground)]">p.{n.page} · </span>}{n.contenu}
            </Row>
          ))}
        </Section>

        {/* Citations (#147) */}
        <Section icon={<QuoteIcon className="h-3.5 w-3.5" />} title={`Citations (${quotes.length})`}>
          <div className="flex gap-2">
            <input value={newQuote} onChange={(e) => setNewQuote(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void addQuote() }} placeholder="Une citation…" className={`${inputCls} flex-1`} />
            <button onClick={() => void addQuote()} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)]">+</button>
          </div>
          {quotes.map((qt) => (
            <Row key={qt.id} onDelete={() => deleteQuoteMutation.mutate(qt.id)}>
              <span className="italic">« {qt.texte} »</span>
            </Row>
          ))}
        </Section>

        <div className="mt-4 flex justify-end">
          <button onClick={() => void remove()} className="flex items-center gap-1.5 text-xs text-[var(--destructive)] hover:underline">
            <Trash2 className="h-3.5 w-3.5" /> Supprimer ce livre
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 space-y-1.5">
      <p className="flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">{icon} {title}</p>
      {children}
    </div>
  )
}

function Row({ children, onDelete }: { children: React.ReactNode; onDelete: () => void }) {
  return (
    <div className="group flex items-start justify-between gap-2 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm">
      <span className="min-w-0 flex-1">{children}</span>
      <button onClick={onDelete} aria-label="Supprimer" className="shrink-0 text-[var(--muted-foreground)] opacity-0 transition-opacity hover:text-[var(--destructive)] group-hover:opacity-100">
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
