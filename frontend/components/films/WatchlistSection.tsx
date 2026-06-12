'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Plus, Star, Search, X, Clapperboard, Tv, Check, Clock, Bookmark, Eye } from 'lucide-react'
import type { WatchItem, WatchStatut, MediaType, TmdbResult } from '@/lib/films'
import { parseGenres, searchTmdb } from '@/lib/films'
import {
  useWatchlist,
  useAddWatchItem,
  useUpdateWatchItem,
  useDeleteWatchItem,
  useWatchStats,
} from '@/lib/queries/films'
import { Skeleton } from '@/components/ui/skeleton'

const STATUT_CONFIG: Record<WatchStatut, { label: string; icon: typeof Eye; color: string }> = {
  a_voir:   { label: 'À voir',    icon: Bookmark, color: 'var(--ring)' },
  en_cours: { label: 'En cours',  icon: Clock,    color: '#f59e0b' },
  vu:       { label: 'Vu',        icon: Check,    color: 'var(--success)' },
}

const ALL_STATUTS: WatchStatut[] = ['a_voir', 'en_cours', 'vu']

function StarRating({ note, onSet }: { note: number | null; onSet?: (n: number) => void }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <button
          key={i}
          type="button"
          disabled={!onSet}
          onClick={(e) => { e.stopPropagation(); onSet?.(i + 1) }}
          className={`text-sm ${onSet ? 'cursor-pointer' : 'cursor-default'} ${
            i < (note ?? 0) ? 'text-[#f59e0b]' : 'text-[var(--border)]'
          }`}
        >★</button>
      ))}
    </div>
  )
}

function AddModal({
  mediaType,
  onClose,
}: {
  mediaType: MediaType
  onClose: () => void
}) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<TmdbResult[]>([])
  const [searching, setSearching] = useState(false)
  const [manualMode, setManualMode] = useState(false)
  const [manualTitre, setManualTitre] = useState('')
  const addMutation = useAddWatchItem()

  const handleSearch = async () => {
    if (!q.trim()) return
    setSearching(true)
    const res = await searchTmdb(q, mediaType).catch(() => [])
    setResults(res)
    setSearching(false)
    if (res.length === 0) setManualMode(true)
  }

  const addFromTmdb = (r: TmdbResult) => {
    addMutation.mutate(
      {
        type: mediaType,
        titre: r.titre,
        tmdb_id: r.tmdb_id,
        annee: r.annee,
        poster_url: r.poster_url,
        synopsis: r.synopsis,
        duree_min: r.duree_min ?? null,
        nb_saisons: r.nb_saisons ?? null,
        nb_episodes_total: r.nb_episodes_total ?? null,
        genres: r.genres as unknown as string,
      },
      {
        onSuccess: () => { toast.success(`${r.titre} ajouté.`); onClose() },
        onError: () => toast.error('Erreur lors de l\'ajout.'),
      }
    )
  }

  const addManual = () => {
    if (!manualTitre.trim()) return
    addMutation.mutate(
      { type: mediaType, titre: manualTitre },
      {
        onSuccess: () => { toast.success(`${manualTitre} ajouté.`); onClose() },
        onError: () => toast.error('Erreur lors de l\'ajout.'),
      }
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--card)] rounded-xl border border-[var(--border)] p-5 w-full max-w-md shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Ajouter un {mediaType === 'film' ? 'film' : 'une série'}</h2>
          <button onClick={onClose} className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><X size={18} /></button>
        </div>

        <div className="flex gap-2 mb-3">
          <input
            className="flex-1 border border-[var(--border)] bg-[var(--background)] rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
            placeholder="Rechercher via TMDB..."
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-3 py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            <Search size={15} />
          </button>
        </div>

        {searching && <p className="text-sm text-[var(--muted-foreground)]">Recherche…</p>}

        {results.length > 0 && (
          <div className="space-y-2 max-h-64 overflow-y-auto mb-3">
            {results.map(r => (
              <button
                key={r.tmdb_id}
                onClick={() => addFromTmdb(r)}
                className="w-full flex gap-3 p-2 rounded-lg hover:bg-[var(--muted)] text-left transition-colors"
              >
                {r.poster_url ? (
                  <img src={r.poster_url} alt={r.titre} className="w-10 h-14 object-cover rounded" />
                ) : (
                  <div className="w-10 h-14 bg-[var(--muted)] rounded flex items-center justify-center">
                    {mediaType === 'film' ? <Clapperboard size={16} /> : <Tv size={16} />}
                  </div>
                )}
                <div>
                  <p className="text-sm font-medium">{r.titre}</p>
                  {r.annee && <p className="text-xs text-[var(--muted-foreground)]">{r.annee}</p>}
                </div>
              </button>
            ))}
          </div>
        )}

        {(manualMode || results.length === 0) && q && !searching && (
          <div className="border-t border-[var(--border)] pt-3">
            <p className="text-xs text-[var(--muted-foreground)] mb-2">Ajout manuel :</p>
            <div className="flex gap-2">
              <input
                className="flex-1 border border-[var(--border)] bg-[var(--background)] rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
                placeholder="Titre"
                value={manualTitre}
                onChange={e => setManualTitre(e.target.value)}
              />
              <button
                onClick={addManual}
                disabled={!manualTitre.trim()}
                className="px-3 py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >Ajouter</button>
            </div>
          </div>
        )}

        {!q && (
          <div className="border-t border-[var(--border)] pt-3">
            <p className="text-xs text-[var(--muted-foreground)] mb-2">Ou directement :</p>
            <div className="flex gap-2">
              <input
                className="flex-1 border border-[var(--border)] bg-[var(--background)] rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
                placeholder="Titre (ajout manuel)"
                value={manualTitre}
                onChange={e => setManualTitre(e.target.value)}
              />
              <button
                onClick={addManual}
                disabled={!manualTitre.trim()}
                className="px-3 py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >Ajouter</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function ItemCard({
  item,
  showProgress,
}: {
  item: WatchItem
  showProgress?: boolean
}) {
  const updateMutation = useUpdateWatchItem()
  const deleteMutation = useDeleteWatchItem()
  const [expanded, setExpanded] = useState(false)

  const setStatut = (statut: WatchStatut) => {
    const patch: Partial<WatchItem> = { statut }
    if (statut === 'vu' && !item.date_vue) {
      patch.date_vue = new Date().toISOString().split('T')[0]
    }
    updateMutation.mutate({ id: item.id, patch }, {
      onError: () => toast.error('Mise à jour échouée.')
    })
  }

  const setNote = (note: number) => {
    updateMutation.mutate({ id: item.id, patch: { note } }, {
      onError: () => toast.error('Note non sauvegardée.')
    })
  }

  const genres = parseGenres(item.genres)
  const cfg = STATUT_CONFIG[item.statut]
  const Icon = cfg.icon

  return (
    <div className="flex gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)] transition-colors">
      {item.poster_url ? (
        <img src={item.poster_url} alt={item.titre} className="w-12 h-16 object-cover rounded-lg flex-shrink-0" />
      ) : (
        <div className="w-12 h-16 bg-[var(--muted)] rounded-lg flex items-center justify-center flex-shrink-0">
          {item.type === 'film' ? <Clapperboard size={18} className="text-[var(--muted-foreground)]" /> : <Tv size={18} className="text-[var(--muted-foreground)]" />}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">{item.titre}</p>
            <div className="flex items-center gap-2 mt-0.5">
              {item.annee && <span className="text-xs text-[var(--muted-foreground)]">{item.annee}</span>}
              {genres.length > 0 && (
                <span className="text-xs text-[var(--muted-foreground)]">{genres[0]}</span>
              )}
              {item.type === 'serie' && item.nb_saisons && (
                <span className="text-xs text-[var(--muted-foreground)]">{item.nb_saisons} saison{item.nb_saisons > 1 ? 's' : ''}</span>
              )}
              {item.type === 'film' && item.duree_min && (
                <span className="text-xs text-[var(--muted-foreground)]">{item.duree_min} min</span>
              )}
            </div>
          </div>
          <button
            onClick={() => deleteMutation.mutate(item.id, { onError: () => toast.error('Suppression échouée.') })}
            className="text-[var(--muted-foreground)] hover:text-[var(--destructive)] flex-shrink-0"
            aria-label="Supprimer"
          ><X size={14} /></button>
        </div>

        <div className="flex items-center gap-2 mt-2">
          <div className="flex gap-1">
            {ALL_STATUTS.map(s => {
              const c = STATUT_CONFIG[s]
              const I = c.icon
              return (
                <button
                  key={s}
                  onClick={() => setStatut(s)}
                  title={c.label}
                  className={`p-1 rounded-md transition-colors ${
                    item.statut === s
                      ? 'text-[var(--background)]'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]'
                  }`}
                  style={item.statut === s ? { backgroundColor: c.color } : {}}
                ><I size={13} /></button>
              )
            })}
          </div>
          <StarRating note={item.note} onSet={setNote} />
        </div>
      </div>
    </div>
  )
}

export default function WatchlistSection({ mediaType }: { mediaType: MediaType }) {
  const [filtre, setFiltre] = useState<WatchStatut | 'tous'>('tous')
  const [showAdd, setShowAdd] = useState(false)

  const listQ = useWatchlist({ type: mediaType })
  const statsQ = useWatchStats()
  const items: WatchItem[] | null = listQ.isError ? [] : listQ.data ?? null

  if (items === null) {
    return <div className="space-y-2 max-w-xl">{[0, 1, 2].map(i => <Skeleton key={i} className="h-24" />)}</div>
  }

  const counts: Record<WatchStatut | 'tous', number> = {
    tous: items.length,
    a_voir: items.filter(i => i.statut === 'a_voir').length,
    en_cours: items.filter(i => i.statut === 'en_cours').length,
    vu: items.filter(i => i.statut === 'vu').length,
  }

  const filtered = filtre === 'tous' ? items : items.filter(i => i.statut === filtre)
  const stats = statsQ.data

  return (
    <div className="max-w-xl space-y-5">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: mediaType === 'film' ? 'Films vus' : 'Séries vues', value: mediaType === 'film' ? stats.films_vus : stats.series_vues },
            { label: `Vus en ${stats.annee}`, value: stats.vus_annee },
            { label: 'Temps estimé', value: `${stats.temps_estime_heures}h` },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-center">
              <p className="text-xl font-bold">{value}</p>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filtres */}
      <div className="flex gap-1 flex-wrap">
        {(['tous', ...ALL_STATUTS] as const).map(s => {
          const cfg = s === 'tous' ? null : STATUT_CONFIG[s]
          const Icon = cfg?.icon
          return (
            <button
              key={s}
              onClick={() => setFiltre(s)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filtre === s
                  ? 'bg-[color-mix(in_srgb,var(--ring)_12%,transparent)] text-[var(--ring)] font-medium'
                  : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]'
              }`}
            >
              {Icon && <Icon size={13} />}
              {s === 'tous' ? 'Tous' : STATUT_CONFIG[s].label}
              <span className="text-xs opacity-70">({counts[s]})</span>
            </button>
          )
        })}
        <button
          onClick={() => setShowAdd(true)}
          className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)] rounded-lg font-medium hover:bg-[color-mix(in_srgb,var(--ring)_18%,transparent)] transition-colors"
        >
          <Plus size={13} /> Ajouter
        </button>
      </div>

      {/* Liste */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <div className="mb-3">{mediaType === 'film' ? <Clapperboard size={32} className="mx-auto opacity-40" /> : <Tv size={32} className="mx-auto opacity-40" />}</div>
          <p className="text-sm">Aucun {mediaType === 'film' ? 'film' : 'série'} ici.</p>
          <button onClick={() => setShowAdd(true)} className="mt-2 text-sm text-[var(--ring)] hover:underline">Ajouter le premier</button>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(item => <ItemCard key={item.id} item={item} />)}
        </div>
      )}

      {showAdd && <AddModal mediaType={mediaType} onClose={() => setShowAdd(false)} />}
    </div>
  )
}
