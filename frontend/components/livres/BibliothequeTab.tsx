'use client'

import { useState } from 'react'
import { BookOpen, Clock, CheckCircle2, Bookmark } from 'lucide-react'

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

const MOCK_LIVRES: Livre[] = [
  { id: 1, titre: 'Atomic Habits', auteur: 'James Clear', statut: 'en_cours', pages_total: 320, pages_lues: 180, genre: 'Développement personnel' },
  { id: 2, titre: 'The Psychology of Money', auteur: 'Morgan Housel', statut: 'lu', pages_total: 256, pages_lues: 256, note: 5, genre: 'Finance' },
  { id: 3, titre: 'Deep Work', auteur: 'Cal Newport', statut: 'a_lire', pages_total: 304, genre: 'Productivité' },
  { id: 4, titre: 'Thinking, Fast and Slow', auteur: 'Daniel Kahneman', statut: 'lu', pages_total: 499, pages_lues: 499, note: 4, genre: 'Psychologie' },
  { id: 5, titre: 'The Lean Startup', auteur: 'Eric Ries', statut: 'a_lire', pages_total: 336, genre: 'Business' },
  { id: 6, titre: '1984', auteur: 'George Orwell', statut: 'lu', pages_total: 328, pages_lues: 328, note: 5, genre: 'Fiction' },
]

const STATUT_CONFIG: Record<Statut, { label: string; icon: typeof BookOpen; color: string; bg: string }> = {
  en_cours: { label: 'En cours', icon: Clock, color: '#f59e0b', bg: 'color-mix(in_srgb,#f59e0b_12%,transparent)' },
  a_lire: { label: 'À lire', icon: Bookmark, color: 'var(--ring)', bg: 'color-mix(in_srgb,var(--ring)_10%,transparent)' },
  lu: { label: 'Lu', icon: CheckCircle2, color: 'var(--success)', bg: 'color-mix(in_srgb,var(--success)_10%,transparent)' },
}

const ALL_STATUTS: Statut[] = ['en_cours', 'a_lire', 'lu']

export default function BibliothequeTab() {
  const [filtre, setFiltre] = useState<Statut | 'tous'>('tous')

  const livresFiltres = filtre === 'tous' ? MOCK_LIVRES : MOCK_LIVRES.filter(l => l.statut === filtre)

  const counts = {
    en_cours: MOCK_LIVRES.filter(l => l.statut === 'en_cours').length,
    a_lire: MOCK_LIVRES.filter(l => l.statut === 'a_lire').length,
    lu: MOCK_LIVRES.filter(l => l.statut === 'lu').length,
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
          Tous ({MOCK_LIVRES.length})
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
