'use client'

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Target, BookMarked, Sparkles } from 'lucide-react'
import {
  fetchAnnualStats, fetchRecommendations, setReadingGoal,
  type AnnualStats, type Recommendation,
} from '@/lib/livres'
import { Skeleton } from '@/components/ui/skeleton'

export default function StatsTab() {
  const year = new Date().getFullYear()
  const [stats, setStats] = useState<AnnualStats | null>(null)
  const [reco, setReco] = useState<Recommendation[]>([])
  const [goalInput, setGoalInput] = useState('')
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    fetchAnnualStats(year)
      .then((s) => { setStats(s); setGoalInput(String(s.challenge.goal)) })
      .catch(() => setError(true))
    fetchRecommendations().then((d) => setReco(Array.isArray(d) ? d : [])).catch(() => setReco([]))
  }, [year])

  useEffect(() => load(), [load])

  const saveGoal = async () => {
    const g = parseInt(goalInput, 10)
    if (isNaN(g) || g < 0) { toast.error('Objectif invalide.'); return }
    try { await setReadingGoal(g); toast.success('Objectif mis à jour.'); load() }
    catch { toast.error('Objectif non sauvegardé.') }
  }

  if (error) return <p className="text-sm text-[var(--destructive)]">Statistiques indisponibles.</p>
  if (!stats) return <div className="max-w-xl space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>

  const ch = stats.challenge
  const genres = Object.entries(stats.par_genre)
  const maxGenre = Math.max(1, ...genres.map(([, n]) => n))

  return (
    <div className="max-w-xl space-y-6">
      {/* Challenge / objectif (#151) */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="flex items-center gap-1.5 text-sm font-semibold"><Target size={15} /> Challenge {year}</p>
          <span className="text-sm font-bold font-mono" style={{ color: ch.atteint ? 'var(--success)' : 'var(--ring)' }}>
            {ch.livres_lus} / {ch.goal}
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-[var(--muted)]">
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: `${ch.pct}%`, background: ch.atteint ? 'var(--success)' : 'var(--ring)' }} />
        </div>
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">
          {ch.atteint ? '🎉 Objectif atteint, bravo !' : `Encore ${ch.restant} livre${ch.restant > 1 ? 's' : ''} pour atteindre ton objectif.`}
        </p>
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-[var(--muted-foreground)]">Objectif annuel</span>
          <input value={goalInput} onChange={(e) => setGoalInput(e.target.value)} inputMode="numeric" aria-label="Objectif annuel"
            className="w-20 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" />
          <button onClick={() => void saveGoal()} className="rounded-md border border-[var(--border)] px-3 py-1 text-sm hover:bg-[var(--muted)]">Enregistrer</button>
        </div>
      </div>

      {/* Stats annuelles (#146) */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
          <BookMarked size={18} className="mx-auto mb-1 text-[var(--ring)]" />
          <p className="text-2xl font-bold font-mono">{stats.livres_lus}</p>
          <p className="text-xs text-[var(--muted-foreground)]">livres lus</p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-center">
          <p className="text-2xl font-bold font-mono">{stats.pages_lues.toLocaleString('fr-CA')}</p>
          <p className="text-xs text-[var(--muted-foreground)]">pages lues</p>
        </div>
      </div>

      {/* Par genre */}
      {genres.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <p className="mb-3 text-sm font-semibold">Par genre</p>
          <div className="space-y-2">
            {genres.map(([g, n]) => (
              <div key={g} className="flex items-center gap-2">
                <span className="w-28 shrink-0 truncate text-xs text-[var(--muted-foreground)]">{g}</span>
                <div className="h-4 flex-1 overflow-hidden rounded bg-[var(--muted)]">
                  <div className="h-full rounded bg-[var(--ring)]" style={{ width: `${(n / maxGenre) * 100}%` }} />
                </div>
                <span className="w-6 shrink-0 text-right text-xs font-mono">{n}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommandations (#149) */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p className="mb-3 flex items-center gap-1.5 text-sm font-semibold"><Sparkles size={15} /> Recommandations</p>
        {reco.length === 0 ? (
          <p className="text-xs text-[var(--muted-foreground)]">Ajoute des livres à « À lire » pour recevoir des suggestions.</p>
        ) : (
          <div className="space-y-2">
            {reco.map((r) => (
              <div key={r.id} className="rounded-lg border border-[var(--border)] p-2.5">
                <p className="text-sm font-medium">{r.titre}</p>
                <p className="text-xs text-[var(--muted-foreground)]">{r.auteur || '—'}</p>
                <p className="mt-1 text-[11px] text-[var(--ring)]">{r.raison}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
