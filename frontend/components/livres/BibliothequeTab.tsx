'use client'

import { useEffect, useState } from 'react'
import { BookOpen, Clock, CheckCircle2, Bookmark } from 'lucide-react'
import { fetchBooks, updateBook } from '@/lib/livres'

type Statut = 'en_cours' | 'a_lire' | 'lu'

type Livre = {
  id: number
  titre: string
  auteur: string
  statut: Statut
  pages_total: number
  pages_lues?: number
  note?: number
  genre: string
}

const STATUT_CONFIG: Record<Statut, { label: string; icon: typeof BookOpen; color: string; bg: string }> = {
  en_cours: { label: 'En cours', icon: Clock, color: '#f59e0b', bg: 'color-mix(in_srgb,#f59e0b_12%,transparent)' },
  a_lire: { label: 'À lire', icon: Bookmark, color: 'var(--ring)', bg: 'color-mix(in_srgb,var(--ring)_10%,transparent)' },
  lu: { label: 'Lu', icon: CheckCircle2, color: 'var(--success)', bg: 'color-mix(in_srgb,var(--success)_10%,transparent)' },
}

const ALL_STATUTS: Statut[] = ['en_cours', 'a_lire', 'lu']

export default function BibliothequeTab() {
  const [livres, setLivres] = useState<Livre[]>([])
  const [filtre, setFiltre] = useState<Statut | 'tous'>('tous')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchBooks().then(d => {
      setLivres(Array.isArray(d) ? d : [])
      setLoading(false)
    })
  }, [])

  const livresFiltres = filtre === 'tous' ? livres : livres.filter((l: any) => l.statut === filtre)

  const counts = {
    en_cours: livres.filter((l: any) => l.statut === 'en_cours').length,
    a_lire: livres.filter((l: any) => l.statut === 'a_lire').length,
    lu: livres.filter((l: any) => l.statut === 'lu').length,
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 stagger">
        {ALL_STATUTS.map(s => {
          const cfg = STATUT_CONFIG[s]
          const Icon = cfg.icon
          return (
            <div key={s} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 card-hover animate-fade-in-up text-center">
              <Icon size={18} className="mx-auto mb-1" style={{ color: cfg.color }} />
              <p className="text-2xl font-bold font-mono">{counts[s]}</p>
              <p className="text-xs text-[var(--muted-foreground)]">{cfg.label}</p>
            </div>
          )
        })}
      </div>

      {/* Filtres */}
      <div className="flex gap-1 flex-wrap animate-fade-in-up">
        <button
          onClick={() => setFiltre('tous')}
          className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-150 cursor-pointer ${
            filtre === 'tous'
              ? 'bg-[var(--foreground)] text-[var(--card)]'
              : 'bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
          }`}
        >
          Tous ({livres.length})
        </button>
        {ALL_STATUTS.map(s => {
          const cfg = STATUT_CONFIG[s]
          return (
            <button
              key={s}
              onClick={() => setFiltre(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-150 cursor-pointer ${
                filtre === s
                  ? 'bg-[var(--foreground)] text-[var(--card)]'
                  : 'bg-[var(--muted)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              {cfg.label} ({counts[s]})
            </button>
          )
        })}
      </div>

      {/* Liste de livres */}
      <div className="space-y-2 stagger">
        {livresFiltres.map(livre => {
          const cfg = STATUT_CONFIG[livre.statut]
          const Icon = cfg.icon
          const pct = livre.pages_lues && livre.pages_total
            ? Math.round((livre.pages_lues / livre.pages_total) * 100)
            : 0

          return (
            <div key={livre.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
              <div className="flex items-start gap-3">
                {/* Icon statut */}
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ background: cfg.bg }}>
                  <Icon size={16} style={{ color: cfg.color }} />
                </div>

                {/* Contenu */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold leading-tight">{livre.titre}</p>
                      <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{livre.auteur}</p>
                    </div>
                    {livre.note && (
                      <div className="flex gap-0.5 flex-shrink-0">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <span key={i} className={`text-xs ${i < livre.note! ? 'text-[#f59e0b]' : 'text-[var(--border)]'}`}>★</span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]">
                      {livre.genre}
                    </span>
                    <span className="text-xs text-[var(--muted-foreground)]">{livre.pages_total} pages</span>
                  </div>

                  {livre.statut === 'en_cours' && livre.pages_lues && (
                    <div className="mt-2">
                      <div className="flex justify-between text-[10px] text-[var(--muted-foreground)] mb-1">
                        <span>Page {livre.pages_lues}</span>
                        <span>{pct}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, background: cfg.color }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
        <p className="text-sm text-[var(--muted-foreground)]">
          Les livres seront synchronisés avec le backend Livres.
        </p>
      </div>
    </div>
  )
}
