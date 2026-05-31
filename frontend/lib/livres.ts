const BASE = '/api/livres'
export const fetchBooks = (statut?: string) =>
  fetch(`${BASE}/books${statut ? '?statut=' + statut : ''}`).then(r => r.json())
export const fetchStats = () => fetch(`${BASE}/stats`).then(r => r.json())
export const createBook = (data: any) =>
  fetch(`${BASE}/books`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }).then(r => r.json())
export const updateBook = (id: number, data: any) =>
  fetch(`${BASE}/books/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }).then(r => r.json())
export const lookupIsbn = (isbn: string) =>
  fetch(`${BASE}/books/from-isbn?isbn=${isbn}`, { method: 'POST' }).then(r => r.json())
