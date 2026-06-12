const BASE = '/api/livres'

export type Statut = 'en_cours' | 'a_lire' | 'lu' | 'abandonne'

export type Book = {
  id: number
  titre: string
  auteur: string
  isbn: string | null
  pages: number | null
  statut: Statut
  genre: string
  format: string
  note: number | null
  page_courante: number | null
  date_debut: string | null
  date_fin: string | null
  couverture_url: string | null
}

export type SearchResult = {
  titre: string
  auteur: string
  pages: number | null
  isbn: string | null
  annee: number | null
  couverture_url: string | null
}

export type BookNote = { id: number; book_id: number; page: number | null; contenu: string; tags: string }
export type BookQuote = { id: number; book_id: number; page: number | null; texte: string }

export type AnnualStats = {
  year: number
  livres_lus: number
  pages_lues: number
  par_genre: Record<string, number>
  challenge: { goal: number; livres_lus: number; pct: number; atteint: boolean; restant: number }
}

export type Recommendation = { id: number; titre: string; auteur: string; genre: string; raison: string }

export type Estimate = {
  page_courante: number
  pages: number
  pct: number
  pace_pages_per_min: number
  remaining_minutes: number | null
}

const json = (r: Response) => r.json()
const jsonHeaders = { 'Content-Type': 'application/json' }

export const fetchBooks = (opts?: { statut?: string; sort?: string }): Promise<Book[]> => {
  const p = new URLSearchParams()
  if (opts?.statut) p.set('statut', opts.statut)
  if (opts?.sort) p.set('sort', opts.sort)
  const qs = p.toString()
  return fetch(`${BASE}/books${qs ? '?' + qs : ''}`).then(json)
}

export const createBook = (data: Partial<Book>): Promise<Book> =>
  fetch(`${BASE}/books`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) }).then(json)

export const updateBook = (id: number, data: Partial<Book>): Promise<Book> =>
  fetch(`${BASE}/books/${id}`, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(data) }).then(json)

export const deleteBook = (id: number) =>
  fetch(`${BASE}/books/${id}`, { method: 'DELETE' })

export const searchBooks = (q: string): Promise<SearchResult[]> =>
  fetch(`${BASE}/search?q=${encodeURIComponent(q)}`).then(json)

export const fetchAnnualStats = (year?: number): Promise<AnnualStats> =>
  fetch(`${BASE}/stats/annual${year ? '?year=' + year : ''}`).then(json)

export const fetchRecommendations = (): Promise<Recommendation[]> =>
  fetch(`${BASE}/recommendations`).then(json)

export const fetchReadingGoal = (): Promise<{ annual_goal: number }> =>
  fetch(`${BASE}/reading-goal`).then(json)

export const setReadingGoal = (annual_goal: number): Promise<{ annual_goal: number }> =>
  fetch(`${BASE}/reading-goal`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ annual_goal }) }).then(json)

export const fetchEstimate = (id: number): Promise<Estimate> =>
  fetch(`${BASE}/books/${id}/estimate`).then(json)

export const fetchNotes = (id: number): Promise<BookNote[]> =>
  fetch(`${BASE}/books/${id}/notes`).then(json)

export const createNote = (id: number, contenu: string, page: number | null) =>
  fetch(`${BASE}/books/${id}/notes`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ contenu, page, tags: [] }) }).then(json)

export const deleteNote = (id: number) =>
  fetch(`${BASE}/notes/${id}`, { method: 'DELETE' })

export const fetchQuotes = (id: number): Promise<BookQuote[]> =>
  fetch(`${BASE}/books/${id}/quotes`).then(json)

export const createQuote = (id: number, texte: string, page: number | null) =>
  fetch(`${BASE}/books/${id}/quotes`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ texte, page }) }).then(json)

export const deleteQuote = (id: number) =>
  fetch(`${BASE}/quotes/${id}`, { method: 'DELETE' })

export const createReadingSession = (
  id: number, data: { date: string; duree_minutes: number; page_debut?: number | null; page_fin?: number | null },
) =>
  fetch(`${BASE}/books/${id}/sessions`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) }).then(json)


export const syncFromJson = (): Promise<{ added: number; updated: number; source: string }> =>
  fetch(`${BASE}/sync-from-json`, { method: 'POST' }).then(json)
