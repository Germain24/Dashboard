'use client'

/** Détail recette : échelle de portions (#126) + minuteurs (#131) + notes (#128).
 *  Extrait de RecettesTab.tsx (#520). */

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Clock, X } from 'lucide-react'
import { useRecipe, useRecipeNote, useSetRecipeNote } from '@/lib/queries/cuisine'
import { Skeleton } from '@/components/ui/skeleton'

export default function RecipeDetailModal({ id, onClose }: { id: number; onClose: () => void }) {
  const recQ = useRecipe(id)
  const rec = recQ.data ?? null
  const err = recQ.isError
  const noteQ = useRecipeNote(id)
  const noteMutation = useSetRecipeNote()
  const [portions, setPortions] = useState(1)
  const [note, setNote] = useState('')

  useEffect(() => {
    if (rec) setPortions(rec.portions || 1)
  }, [rec])
  useEffect(() => {
    if (noteQ.data !== undefined) setNote(noteQ.data)
  }, [noteQ.data])

  const saveNote = () => {
    noteMutation.mutate(
      { id, note },
      {
        onSuccess: () => toast.success('Note enregistrée.'),
        onError: () => toast.error("Impossible d'enregistrer la note."),
      },
    )
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const base = rec?.portions || 1
  const scale = portions / base
  const fmtQ = (q: number) => {
    const v = Math.round(q * scale * 100) / 100
    return Number.isInteger(v) ? String(v) : String(v)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[6vh]">
      <div
        role="dialog" aria-modal="true" aria-label={rec?.titre ?? 'Recette'}
        className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 className="font-display text-base font-semibold">{rec?.titre ?? 'Recette'}</h2>
          <button type="button" onClick={onClose} aria-label="Fermer"
            className="rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {err && <p className="text-sm text-[var(--destructive)]">Recette indisponible.</p>}
          {!rec && !err && <Skeleton className="h-40" />}

          {rec && (
            <>
              {/* Échelle de portions (#126) */}
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-[var(--muted-foreground)]">Portions</span>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => setPortions((p) => Math.max(1, p - 1))}
                    aria-label="Moins de portions"
                    className="h-7 w-7 rounded-md border border-[var(--border)] hover:bg-[var(--muted)]">−</button>
                  <span className="w-8 text-center tabular-nums font-semibold">{portions}</span>
                  <button type="button" onClick={() => setPortions((p) => p + 1)}
                    aria-label="Plus de portions"
                    className="h-7 w-7 rounded-md border border-[var(--border)] hover:bg-[var(--muted)]">+</button>
                  {portions !== base && (
                    <span className="text-xs text-[var(--muted-foreground)]">(base {base})</span>
                  )}
                </div>
              </div>

              {/* Ingrédients (quantités recalculées) */}
              {rec.ingredients.length > 0 ? (
                <ul className="space-y-1 text-sm">
                  {rec.ingredients.map((ing, i) => (
                    <li key={i} className="flex justify-between gap-2 border-b border-[var(--border)] py-1 last:border-0">
                      <span>{ing.nom_libre}</span>
                      <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
                        {ing.quantite ? `${fmtQ(ing.quantite)} ${ing.unite}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-[var(--muted-foreground)]">Aucun ingrédient.</p>
              )}

              {/* Minuteurs (#131) */}
              {(rec.temps_prep > 0 || rec.temps_cuisson > 0) && (
                <div className="flex flex-wrap gap-3 rounded-md border border-[var(--border)] p-2.5">
                  {rec.temps_prep > 0 && <CookTimer minutes={rec.temps_prep} label="Prép." />}
                  {rec.temps_cuisson > 0 && <CookTimer minutes={rec.temps_cuisson} label="Cuisson" />}
                </div>
              )}

              {rec.instructions && (
                <div>
                  <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Instructions</p>
                  <p className="whitespace-pre-wrap text-sm">{rec.instructions}</p>
                </div>
              )}

              {/* Notes personnelles (#128) */}
              <div>
                <p className="mb-1 text-xs font-medium text-[var(--muted-foreground)]">Notes personnelles</p>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="Tes remarques, variantes, astuces…"
                  className="w-full resize-none rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
                <button
                  type="button"
                  onClick={saveNote}
                  disabled={noteMutation.isPending}
                  className="mt-1.5 rounded-md bg-[var(--primary)] px-3 py-1 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-60"
                >
                  {noteMutation.isPending ? 'Enregistrement…' : 'Enregistrer la note'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function CookTimer({ minutes, label }: { minutes: number; label: string }) {
  const [endsAt, setEndsAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (endsAt === null) return
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [endsAt])

  const remainingMs = endsAt !== null ? endsAt - now : minutes * 60 * 1000
  const remaining = Math.max(0, Math.ceil(remainingMs / 1000))
  const running = endsAt !== null && remainingMs > 0
  const done = endsAt !== null && remainingMs <= 0
  const mmss = `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-2 text-sm">
      <Clock size={14} className="text-[var(--muted-foreground)]" aria-hidden="true" />
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className={`font-mono tabular-nums ${done ? 'text-[var(--success)]' : ''}`}>{mmss}</span>
      {running ? (
        <button type="button" onClick={() => setEndsAt(null)}
          className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)]">Arrêter</button>
      ) : (
        <button type="button" onClick={() => setEndsAt(Date.now() + minutes * 60 * 1000)}
          className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--muted)]">
          {done ? 'Relancer' : 'Démarrer'}
        </button>
      )}
    </div>
  )
}
