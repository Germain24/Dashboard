'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'
import type { WatchItem } from '@/lib/films'
import { useSerieProgress, useUpdateProgress } from '@/lib/queries/films'

export default function SeriesProgressModal({
  serie,
  onClose,
}: {
  serie: WatchItem
  onClose: () => void
}) {
  const progressQ = useSerieProgress(serie.id)
  const updateMutation = useUpdateProgress()

  const prog = progressQ.data && 'saison' in progressQ.data ? progressQ.data : null

  const [saison, setSaison] = useState(prog?.saison ?? 1)
  const [episode, setEpisode] = useState(prog?.episode_courant ?? 0)

  // Sync after load
  if (prog && saison === 1 && episode === 0 && (prog.saison !== 1 || prog.episode_courant !== 0)) {
    setSaison(prog.saison)
    setEpisode(prog.episode_courant)
  }

  const save = () => {
    updateMutation.mutate(
      [serie.id, { saison, episode_courant: episode }],
      {
        onSuccess: () => { toast.success('Progression sauvegardée.'); onClose() },
        onError: () => toast.error('Erreur lors de la sauvegarde.'),
      }
    )
  }

  const maxSaisons = serie.nb_saisons ?? 99

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] p-5 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-sm">Progression — {serie.titre}</h2>
          <button onClick={onClose} className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X size={18} /></button>
        </div>

        {progressQ.isLoading ? (
          <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">Saison</label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSaison(s => Math.max(1, s - 1))}
                  disabled={saison <= 1}
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                ><ChevronLeft size={16} /></button>
                <span className="text-lg font-bold w-8 text-center">{saison}</span>
                <button
                  onClick={() => setSaison(s => Math.min(maxSaisons, s + 1))}
                  disabled={saison >= maxSaisons}
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                ><ChevronRight size={16} /></button>
                {serie.nb_saisons && (
                  <span className="text-xs text-[var(--muted-foreground)]">/ {serie.nb_saisons}</span>
                )}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--muted-foreground)] block mb-1">Épisode</label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setEpisode(e => Math.max(0, e - 1))}
                  disabled={episode <= 0}
                  className="p-1 rounded hover:bg-[var(--muted)] disabled:opacity-40"
                ><ChevronLeft size={16} /></button>
                <span className="text-lg font-bold w-8 text-center">{episode}</span>
                <button
                  onClick={() => setEpisode(e => e + 1)}
                  className="p-1 rounded hover:bg-[var(--muted)]"
                ><ChevronRight size={16} /></button>
              </div>
            </div>

            <button
              onClick={save}
              disabled={updateMutation.isPending}
              className="w-full py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {updateMutation.isPending ? 'Sauvegarde…' : 'Sauvegarder'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
