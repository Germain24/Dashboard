const BASE = '/api/films-series'

export type WatchStatut = 'a_voir' | 'en_cours' | 'vu'
export type MediaType = 'film' | 'serie'

export type WatchItem = {
  id: number
  type: MediaType
  titre: string
  tmdb_id: number | null
  statut: WatchStatut
  note: number | null
  annee: number | null
  genres: string  // JSON string
  poster_url: string | null
  duree_min: number | null
  nb_saisons: number | null
  nb_episodes_total: number | null
  synopsis: string
  date_vue: string | null
  created_at: string
}

export type SerieProgress = {
  id: number
  watch_item_id: number
  saison: number
  episode_courant: number
  episodes_saison: number | null
  date_derniere_vue: string | null
}

export type WatchStats = {
  films_total: number
  series_total: number
  films_vus: number
  series_vues: number
  vus_annee: number
  temps_estime_heures: number
  annee: number
}

export type TmdbResult = {
  tmdb_id: number
  titre: string
  annee: number | null
  genres: string[]
  poster_url: string | null
  synopsis: string
  type: MediaType
  duree_min?: number
  nb_saisons?: number
  nb_episodes_total?: number
}

const json = (r: Response) => r.json()
const jsonHeaders = { 'Content-Type': 'application/json' }

export const searchTmdb = (q: string, type: MediaType = 'film'): Promise<TmdbResult[]> =>
  fetch(`${BASE}/search?q=${encodeURIComponent(q)}&type=${type}`).then(json)

export const fetchWatchlist = (opts?: { type?: MediaType; statut?: WatchStatut }): Promise<WatchItem[]> => {
  const p = new URLSearchParams()
  if (opts?.type) p.set('type', opts.type)
  if (opts?.statut) p.set('statut', opts.statut)
  const qs = p.toString()
  return fetch(`${BASE}/watchlist${qs ? '?' + qs : ''}`).then(json)
}

export const createWatchItem = (data: Partial<WatchItem> & { titre: string }): Promise<WatchItem> =>
  fetch(`${BASE}/watchlist`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(data),
  }).then(json)

export const updateWatchItem = (id: number, patch: Partial<WatchItem>): Promise<WatchItem> =>
  fetch(`${BASE}/watchlist/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders,
    body: JSON.stringify(patch),
  }).then(json)

export const deleteWatchItem = (id: number): Promise<void> =>
  fetch(`${BASE}/watchlist/${id}`, { method: 'DELETE' }).then(() => undefined)

export const fetchProgress = (id: number): Promise<SerieProgress | Record<string, never>> =>
  fetch(`${BASE}/progress/${id}`).then(json)

export const updateProgress = (
  id: number,
  data: { saison: number; episode_courant: number; episodes_saison?: number; date_derniere_vue?: string }
): Promise<SerieProgress> =>
  fetch(`${BASE}/progress/${id}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(data),
  }).then(json)

export const fetchWatchStats = (): Promise<WatchStats> =>
  fetch(`${BASE}/stats`).then(json)

export function parseGenres(genres: string): string[] {
  try {
    return JSON.parse(genres) as string[]
  } catch {
    return []
  }
}
